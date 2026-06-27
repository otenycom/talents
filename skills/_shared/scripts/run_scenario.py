#!/usr/bin/env python3
"""run_scenario — the deterministic behavioral-test player for an Oteny Talent.

A Talent author writes behavioral tests *inside the bundle* (``tests/scenarios/*.yaml``)
and runs them two ways from ONE runner:

  * ``--backend mock`` (this file, default) — DETERMINISTIC and OFFLINE: it stands up a
    hermetic sandbox home, seeds the Talent's data plane (profile + db + prior-shape
    rows + migration marker), then for each turn EXECUTES the scenario's canned
    tool-calls (a ``sql`` statement, a declared ``script``, or a ``migrate`` apply)
    against that sandbox and asserts the resulting **state** (db rows) is what the
    Talent's own machinery should produce. No LLM, no network — so CI runs it free on
    every push. Routing/reply/trace assertions are LIVE-ONLY here (the mock can't judge
    natural-language behaviour); they are recorded as ``SKIP`` and proven by the live
    backend.
  * ``--backend live`` — drives the real bot and reads the trace from the gateway-log
    markers (built alongside the live E2E loop; not implemented in this file yet).

Mock mode proves the PROTOCOL and the Talent's deterministic data layer (its SQL /
scripts / in-box migrations produce the right state), exactly the layer that breaks
silently across a version bump. The natural-language layer (does the model route to the
right skill, does it phrase the reply well) is the live backend's job.

This is a shared, canonical runner — like ``selfcheck.py`` / ``migrate.py`` it has ONE
home in ``_shared/scripts/`` and is run from CI/dev, not baked onto a tenant box (it
lives under the bundle's un-delivered ``tests/`` tree), so it is not copied per-bundle.

Usage:
    python3 run_scenario.py [--backend mock] <scenario.yaml> [<scenario.yaml> ...]
    python3 run_scenario.py --bundle <dir> <scenario.yaml>     # override bundle resolution
    python3 run_scenario.py --json <scenario.yaml>             # full JSON DTO (default human + JSON)

Exit code is non-zero iff any assertion failed (so CI gates on it). The full result DTO
is always printed to stdout; human-readable progress goes to stderr.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sqlite3
import sys
import tempfile
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - PyYAML is always present on Hermes / in CI
    yaml = None


def _log(msg: str) -> None:
    print(msg, file=sys.stderr)


def _load_yaml(path: Path):
    if yaml is None:
        raise RuntimeError("PyYAML is required to read scenarios/manifests")
    with Path(path).open() as fh:
        return yaml.safe_load(fh)


# --------------------------------------------------------------------------- #
# bundle resolution                                                            #
# --------------------------------------------------------------------------- #
def resolve_bundle(scenario_path: Path, override: str | None = None) -> Path:
    """The bundle a scenario belongs to.

    Convention: a scenario lives at ``<bundle>/tests/scenarios/<name>.yaml`` so the
    bundle is two parents up. ``--bundle`` overrides for an out-of-tree scenario.
    """
    if override:
        return Path(override).resolve()
    p = scenario_path.resolve()
    # <bundle>/tests/scenarios/x.yaml -> parents[2] = <bundle>
    cand = p.parents[2] if len(p.parents) >= 3 else p.parent
    return cand


def _bundle_script(bundle: Path, *names: str) -> Path | None:
    """First existing ``scripts/<name>`` in the bundle (bundle copy wins), else the
    shared canonical copy. Used for migrate.py / selfcheck.py."""
    for name in names:
        cand = bundle / "scripts" / name
        if cand.is_file():
            return cand
    shared = Path(__file__).resolve().parent
    for name in names:
        cand = shared / name
        if cand.is_file():
            return cand
    return None


def _resolve_db_name(bundle: Path, scenario: dict) -> str | None:
    """The Talent's sqlite db filename — explicit ``seed.db``, else the manifest's
    sqlite_db artifact basename, else ``migrations.yaml`` ``db:``."""
    seed = scenario.get("seed") or {}
    if seed.get("db"):
        return seed["db"]
    man = bundle / "required_artifacts.yaml"
    if man.is_file():
        data = _load_yaml(man) or {}
        for a in data.get("artifacts", []):
            if a.get("kind") == "sqlite_db" and a.get("path"):
                return Path(a["path"]).name
    mig = bundle / "migrations.yaml"
    if mig.is_file():
        data = _load_yaml(mig) or {}
        if data.get("db"):
            return data["db"]
    return None


# --------------------------------------------------------------------------- #
# sandbox home (hermetic — mirrors selfcheck/migrate env overrides)            #
# --------------------------------------------------------------------------- #
class Sandbox:
    def __init__(self, root: Path, bot: str, bundle: Path):
        self.root = root
        self.bot = bot
        self.bundle = bundle
        self.hermes = root / ".hermes"
        self.data_dir = self.hermes / "data" / bot
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.hermes / "memories").mkdir(parents=True, exist_ok=True)
        (self.hermes / "cron").mkdir(parents=True, exist_ok=True)
        # Place the bundle where the on-box path resolves (selfcheck present_if_file,
        # scripts that read ~/.hermes/skills/talents/<bot>/...). A symlink is enough —
        # scripts only READ their own bundle files.
        skills = self.hermes / "skills" / "talents"
        skills.mkdir(parents=True, exist_ok=True)
        link = skills / bot
        if not link.exists():
            try:
                link.symlink_to(bundle, target_is_directory=True)
            except OSError:  # pragma: no cover - fallback for filesystems w/o symlink
                import shutil
                shutil.copytree(bundle, link)

    @property
    def env(self) -> dict:
        return {
            **os.environ,
            "HH_HOME": str(self.root),
            "HH_HERMES_HOME": str(self.hermes),
            "HERMES_HOME": str(self.hermes),
        }

    def db_path(self, db_name: str) -> Path:
        return self.data_dir / db_name


# --------------------------------------------------------------------------- #
# seeding                                                                       #
# --------------------------------------------------------------------------- #
def _apply_sql_file(db: Path, sql_text: str) -> None:
    con = sqlite3.connect(str(db))
    try:
        con.executescript(sql_text)
        con.commit()
    finally:
        con.close()


def seed(sb: Sandbox, scenario: dict, db_name: str | None) -> list[str]:
    """Stand up the Talent's data plane from ``seed:``; return a list of notes."""
    notes: list[str] = []
    seed_cfg = scenario.get("seed") or {}

    # 1. schema — explicit seed.init_sql, else auto-detect scripts/init.sql.
    if db_name:
        db = sb.db_path(db_name)
        init_sql = seed_cfg.get("init_sql")
        init_path = None
        if init_sql:
            init_path = sb.bundle / init_sql
        elif (sb.bundle / "scripts" / "init.sql").is_file():
            init_path = sb.bundle / "scripts" / "init.sql"
        if init_path and init_path.is_file():
            _apply_sql_file(db, init_path.read_text())
            notes.append(f"init schema from {init_path.name}")

    # 2. profile.yaml from seed.profile.
    if seed_cfg.get("profile") is not None:
        (sb.data_dir / "profile.yaml").write_text(
            yaml.safe_dump(seed_cfg["profile"], sort_keys=False))
        notes.append("wrote profile.yaml")

    # 3. domain memory.md from seed.memory.
    if seed_cfg.get("memory") is not None:
        (sb.data_dir / "memory.md").write_text(str(seed_cfg["memory"]))
        notes.append("wrote memory.md")

    # 4. shared identity USER.md (so a baseline box selfchecks READY) from seed.user_md.
    if seed_cfg.get("user_md") is not None:
        (sb.hermes / "memories" / "USER.md").write_text(str(seed_cfg["user_md"]))
        notes.append("wrote USER.md")

    # 5. prior-shape rows from seed.sql (the legacy-state the migration reconciles).
    if seed_cfg.get("sql") and db_name:
        _apply_sql_file(sb.db_path(db_name), str(seed_cfg["sql"]))
        notes.append("applied seed.sql prior-shape rows")

    # 6. cron jobs marker from seed.cron_jobs (list of job names, for selfcheck).
    if seed_cfg.get("cron_jobs") is not None:
        jobs = {"jobs": [{"name": n} for n in seed_cfg["cron_jobs"]]}
        (sb.hermes / "cron" / "jobs.json").write_text(json.dumps(jobs, indent=2))
        notes.append(f"seeded {len(seed_cfg['cron_jobs'])} cron job(s)")

    # 7. migration marker — 'baseline' marks all current applied (born-current box);
    #    a list pre-marks specific ids; absent/'legacy' leaves NO marker (every
    #    declared migration pending — the upgrade-from-prod case).
    migs = seed_cfg.get("migrations")
    migrate_py = _bundle_script(sb.bundle, "migrate.py")
    if migs == "baseline" and migrate_py:
        _run_py(sb, migrate_py, ["--baseline", "--manifest", str(sb.bundle / "migrations.yaml")])
        notes.append("baselined migrations")
    elif isinstance(migs, list) and migrate_py:
        for mid in migs:
            _run_py(sb, migrate_py, ["--mark", str(mid),
                                     "--manifest", str(sb.bundle / "migrations.yaml")])
        notes.append(f"pre-marked migrations {migs}")
    return notes


# --------------------------------------------------------------------------- #
# tool-call execution (the deterministic mock backend)                         #
# --------------------------------------------------------------------------- #
def _run_py(sb: Sandbox, script: Path, args: list[str], stdin: str | None = None):
    return subprocess.run(
        [sys.executable, str(script), *args],
        env=sb.env, input=stdin, capture_output=True, text=True, cwd=str(sb.bundle),
    )


def exec_tool_call(sb: Sandbox, tc: dict, db_name: str | None) -> dict:
    """Execute one canned tool-call deterministically; return a result dict.

    Supported shapes (one key each):
      {sql: "..."}                       run against the Talent db
      {script: "scripts/x.py", args, stdin}   run a DECLARED bundle script
      {migrate: "<id>"}                  apply a deterministic (sql) in-box migration
    """
    if "sql" in tc:
        if not db_name:
            return {"kind": "sql", "ok": False, "reason": "no db for this Talent"}
        try:
            _apply_sql_file(sb.db_path(db_name), str(tc["sql"]))
            return {"kind": "sql", "ok": True}
        except sqlite3.Error as e:
            return {"kind": "sql", "ok": False, "reason": str(e)}

    if "script" in tc:
        script = sb.bundle / tc["script"]
        if not script.is_file():
            return {"kind": "script", "ok": False, "script": tc["script"],
                    "reason": "declared script not found in bundle (registration check failed)"}
        proc = _run_py(sb, script, [str(a) for a in tc.get("args", [])], tc.get("stdin"))
        ok = proc.returncode == 0 or bool(tc.get("allow_fail"))
        return {"kind": "script", "ok": ok, "script": tc["script"],
                "returncode": proc.returncode,
                "stdout": proc.stdout[-4000:], "stderr": proc.stderr[-2000:]}

    if "migrate" in tc:
        migrate_py = _bundle_script(sb.bundle, "migrate.py")
        if not migrate_py:
            return {"kind": "migrate", "ok": False, "reason": "no migrate.py available"}
        proc = _run_py(sb, migrate_py, ["--apply", str(tc["migrate"]), "--json",
                                        "--manifest", str(sb.bundle / "migrations.yaml")])
        out = {}
        try:
            out = json.loads(proc.stdout or "{}")
        except json.JSONDecodeError:
            pass
        ok = out.get("result") == "APPLIED"
        return {"kind": "migrate", "ok": ok, "id": tc["migrate"],
                "result": out.get("result"), "reason": out.get("reason"),
                "stdout": proc.stdout[-2000:]}

    return {"kind": "?", "ok": False, "reason": f"unknown tool-call shape: {sorted(tc)}"}


# --------------------------------------------------------------------------- #
# state assertions (the db-grounded ground truth)                              #
# --------------------------------------------------------------------------- #
def _scalar(db: Path, query: str):
    con = sqlite3.connect(str(db))
    try:
        row = con.execute(query).fetchone()
    finally:
        con.close()
    return row[0] if row else None


def _rows(db: Path, query: str):
    con = sqlite3.connect(str(db))
    try:
        return con.execute(query).fetchall()
    finally:
        con.close()


def _eq(a, b) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return math.isclose(float(a), float(b), rel_tol=1e-9, abs_tol=1e-9)
    return a == b


def assert_state(sb: Sandbox, spec: dict, db_name: str | None) -> dict:
    """Evaluate one state assertion against the Talent db."""
    if not db_name:
        return {"kind": "state", "ok": False, "spec": spec, "reason": "no db for this Talent"}
    db = sb.db_path(db_name)
    if not db.exists():
        return {"kind": "state", "ok": False, "spec": spec, "reason": f"db missing: {db}"}
    try:
        if "table_exists" in spec:
            got = _scalar(db, "SELECT name FROM sqlite_master WHERE type='table' AND "
                              f"name='{spec['table_exists']}'")
            ok = got is not None
            return {"kind": "state", "ok": ok, "spec": spec, "got": got}
        query = spec["query"]
        if "equals" in spec:
            got = _scalar(db, query)
            return {"kind": "state", "ok": _eq(got, spec["equals"]), "spec": spec, "got": got}
        if "count" in spec:
            got = len(_rows(db, query))
            return {"kind": "state", "ok": got == spec["count"], "spec": spec, "got": got}
        if "nonempty" in spec:
            got = len(_rows(db, query))
            want_nonempty = bool(spec["nonempty"])
            return {"kind": "state", "ok": (got > 0) == want_nonempty, "spec": spec, "got": got}
        return {"kind": "state", "ok": False, "spec": spec, "reason": "no assertion verb"}
    except sqlite3.Error as e:
        return {"kind": "state", "ok": False, "spec": spec, "reason": str(e)}


def run_assert_hook(sb: Sandbox, ref: str, db_name: str | None) -> dict:
    """The ``assert: scripts/x.py::fn`` escape hatch — import the bundle module and call
    ``fn(ctx)``; truthy/None return passes, a raised AssertionError fails. ``ctx`` gives
    the sandbox paths so a ground-truth assertion (e.g. a /json/2/ check, live only) can
    locate state."""
    try:
        modref, _, fn = ref.partition("::")
        path = sb.bundle / modref
        import importlib.util
        spec = importlib.util.spec_from_file_location(f"assert_{path.stem}", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        ctx = {"home": sb.root, "hermes_home": sb.hermes, "data_dir": sb.data_dir,
               "bot": sb.bot, "bundle": sb.bundle,
               "db": sb.db_path(db_name) if db_name else None}
        getattr(mod, fn)(ctx)
        return {"kind": "assert", "ok": True, "ref": ref}
    except AssertionError as e:
        return {"kind": "assert", "ok": False, "ref": ref, "reason": str(e) or "assertion failed"}
    except Exception as e:  # a broken hook is a test failure, not a runner crash
        return {"kind": "assert", "ok": False, "ref": ref, "reason": f"{type(e).__name__}: {e}"}


def assert_selfcheck(sb: Sandbox, want_ready: bool) -> dict:
    selfcheck = _bundle_script(sb.bundle, "selfcheck.py")
    manifest = sb.bundle / "required_artifacts.yaml"
    if not selfcheck or not manifest.is_file():
        return {"kind": "selfcheck", "ok": False, "reason": "no selfcheck.py / manifest"}
    proc = _run_py(sb, selfcheck, ["--json", "--manifest", str(manifest)])
    try:
        rep = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return {"kind": "selfcheck", "ok": False, "reason": f"bad selfcheck output: {proc.stdout[:200]}"}
    ok = bool(rep.get("ready")) == bool(want_ready)
    return {"kind": "selfcheck", "ok": ok, "want_ready": want_ready,
            "ready": rep.get("ready"), "missing": rep.get("missing")}


# --------------------------------------------------------------------------- #
# the mock backend                                                             #
# --------------------------------------------------------------------------- #
_LIVE_ONLY_KEYS = ("reply", "trace")


def _scenario_is_live_only(scenario: dict) -> bool:
    lo = scenario.get("live_only")
    return lo is True or (isinstance(lo, list) and "scenario" in lo)


def run_scenario(path: Path, backend: str = "mock", bundle_override: str | None = None) -> dict:
    """Run ONE scenario; return a result DTO. Never raises on a test failure (the
    failure is in the DTO + exit code), only on a malformed scenario/runner error."""
    scenario = _load_yaml(path) or {}
    bot = scenario.get("bot")
    bundle = resolve_bundle(path, bundle_override)
    result = {"path": str(path), "bot": bot, "backend": backend,
              "skipped": False, "passed": 0, "failed": 0, "skipped_count": 0,
              "turns": [], "error": None}

    if backend == "live":
        result["error"] = "live backend not implemented in run_scenario.py yet (P6)"
        result["failed"] = 1
        return result

    if _scenario_is_live_only(scenario):
        result["skipped"] = True
        result["skipped_count"] = 1
        return result

    # cross-check the declared bot against the resolved bundle.
    prof = bundle / "agent-profile.yaml"
    if prof.is_file():
        pbot = (_load_yaml(prof) or {}).get("bot")
        if bot and pbot and bot != pbot:
            result["error"] = f"scenario bot '{bot}' != bundle '{pbot}' at {bundle}"
            result["failed"] = 1
            return result
        bot = bot or pbot
        result["bot"] = bot

    db_name = _resolve_db_name(bundle, scenario)

    with tempfile.TemporaryDirectory(prefix="oteny-scenario-") as tmp:
        sb = Sandbox(Path(tmp), bot, bundle)
        seed_notes = seed(sb, scenario, db_name)
        _log(f"  seed: {'; '.join(seed_notes) or '(none)'}")

        # requires_migration: assert the migration is declared + PENDING after seed
        # (a genuine upgrade-from-prior-state, not an already-applied box).
        req = scenario.get("requires_migration")
        if req:
            migrate_py = _bundle_script(sb.bundle, "migrate.py")
            r = _run_py(sb, migrate_py, ["--status", "--json",
                                         "--manifest", str(sb.bundle / "migrations.yaml")])
            try:
                pend = {m["id"] for m in json.loads(r.stdout or "{}").get("pending", [])}
            except json.JSONDecodeError:
                pend = set()
            ok = req in pend
            res = {"kind": "requires_migration", "ok": ok, "id": req, "pending": sorted(pend)}
            result["turns"].append({"user": f"(setup) requires_migration {req}", "results": [res]})
            result["passed" if ok else "failed"] += 1

        # scenario-level selfcheck gate (deterministic protocol proof).
        if "assert_selfcheck_ready" in scenario:
            res = assert_selfcheck(sb, bool(scenario["assert_selfcheck_ready"]))
            result["turns"].append({"user": "(setup) selfcheck", "results": [res]})
            result["passed" if res["ok"] else "failed"] += 1

        for turn in scenario.get("turns", []):
            tres = {"user": turn.get("user", ""), "results": []}
            expect = turn.get("expect") or {}

            # 1. execute canned tool-calls (the deterministic backend).
            for tc in expect.get("tool_calls", []):
                r = exec_tool_call(sb, tc, db_name)
                tres["results"].append(r)
                result["passed" if r["ok"] else "failed"] += 1

            # 2. state assertions (db-grounded ground truth).
            for spec in expect.get("state", []):
                r = assert_state(sb, spec, db_name)
                tres["results"].append(r)
                result["passed" if r["ok"] else "failed"] += 1

            # 3. assert: escape hatch.
            if turn.get("assert"):
                r = run_assert_hook(sb, turn["assert"], db_name)
                tres["results"].append(r)
                result["passed" if r["ok"] else "failed"] += 1

            # 4. live-only expectations -> SKIP (proven by the live backend).
            for key in _LIVE_ONLY_KEYS:
                if key in expect:
                    tres["results"].append({"kind": key, "ok": None, "skipped": "live_only"})
                    result["skipped_count"] += 1

            result["turns"].append(tres)

    return result


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #
def _human(report: dict) -> None:
    for s in report["scenarios"]:
        name = Path(s["path"]).name
        if s["skipped"]:
            _log(f"SKIP {name} (live_only)")
            continue
        if s["error"]:
            _log(f"ERROR {name}: {s['error']}")
            continue
        flag = "PASS" if s["failed"] == 0 else "FAIL"
        _log(f"{flag} {name}  [{s['passed']} ok / {s['failed']} fail / {s['skipped_count']} skip]")
        if s["failed"]:
            for t in s["turns"]:
                for r in t["results"]:
                    if r.get("ok") is False:
                        _log(f"    - {t['user']!r}: {r}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Oteny Talent scenario player")
    ap.add_argument("scenarios", nargs="+", help="scenario YAML files")
    ap.add_argument("--backend", choices=["mock", "live"], default="mock")
    ap.add_argument("--bundle", default=None, help="override bundle dir resolution")
    ap.add_argument("--json", action="store_true", help="print only the JSON DTO")
    args = ap.parse_args(argv)

    scenarios = []
    for sp in args.scenarios:
        try:
            scenarios.append(run_scenario(Path(sp), args.backend, args.bundle))
        except Exception as e:  # a malformed scenario is a hard error for that file
            scenarios.append({"path": sp, "bot": None, "backend": args.backend,
                              "skipped": False, "passed": 0, "failed": 1, "skipped_count": 0,
                              "turns": [], "error": f"{type(e).__name__}: {e}"})

    ok = all(s["failed"] == 0 and not s["error"] for s in scenarios)
    report = {
        "backend": args.backend, "ok": ok, "scenarios": scenarios,
        "summary": {
            "scenarios": len(scenarios),
            "passed": sum(s["passed"] for s in scenarios),
            "failed": sum(s["failed"] for s in scenarios),
            "skipped": sum(s["skipped_count"] for s in scenarios),
        },
    }
    if not args.json:
        _human(report)
    print(json.dumps(report, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
