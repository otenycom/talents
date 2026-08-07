#!/usr/bin/env python3
"""neutralize — the in-box, fail-closed de-fanging runner for a cloned Oteny Talent.

A *clone* is a real prod tenant stood up from another tenant's captured state so an
author can test a new Talent version against true data. That state is dangerous: it may
carry live credentials, a seam pointed at PRODUCTION (CrewRadar `/json/2/`, an Outlook
mailbox), and registered cron jobs that DM the real owner or file a real government form.
Before a clone is ever allowed to serve a single turn it must be **neutralized** — every
outbound action disabled and every seam repointed at staging/fixtures.

This is the neutralize analog of ``migrate.py``: ONE reusable runner keyed on each
Talent's ``neutralize.yaml`` (the ordered, declared list of de-fanging steps). It is run
by the CONTROL PLANE at clone time (over the node exec/SSH path, gateway NOT serving) —
not by the agent — so every step it runs is DETERMINISTIC. It records completion in a
DATA-PLANE marker (``~/.hermes/data/<bot>/neutralize.json``) that ``check_neutralize.py``
gates the gateway start on: a clone whose marker is missing or incomplete is REFUSED to
serve (fail-closed — a silent neutralize miss at scale would fire thousands of real
emails/filings).

Three step kinds (a superset of migrate's sql|checklist — neutralize also disarms crons,
which live in ``jobs.json``, not the db):

  * ``sql``      — run against the Talent's sqlite db (scrub a credential row, repoint a
                   seam table). Idempotent (detect-then-act); the control plane runs it.
  * ``crons``    — disable the named outbound cron jobs in ``~/.hermes/cron/jobs.json``
                   (the clone must never message the real owner / re-fire a real filing).
                   Deterministic file op; the control plane runs it.
  * ``checklist``— anything that genuinely needs the agent/operator (rare at clone time);
                   run by following ``references/neutralize.md``, then recorded with
                   ``--mark``.

Usage (the bundle ships an identical copy at ``<bot>/scripts/neutralize.py``):

    python3 neutralize.py --status [--json]   # NEUTRALIZE: ok | pending — <id> (<kind>), …
    python3 neutralize.py --all               # run every pending DETERMINISTIC step (sql+crons)
    python3 neutralize.py --apply <id>        # run one deterministic step + mark it
    python3 neutralize.py --mark <id>         # record an agent/operator-run (checklist) step done

By default the manifest is ``<script_dir>/../neutralize.yaml``. Home roots resolve through
the same env overrides as ``selfcheck.py``/``migrate.py`` (HH_HOME / HH_HERMES_HOME /
HERMES_HOME) so tests and a relocated overlay stay hermetic. Exit code is always 0 when
the operation ran (the readiness is in the output, gated by ``check_neutralize.py``); a
deterministic step that *fails to apply* leaves it PENDING, so the boot gate stays closed.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - PyYAML is always present on Hermes
    yaml = None


# --------------------------------------------------------------------------- #
# path resolution (env-overridable so tests are hermetic) — mirrors migrate.py #
# --------------------------------------------------------------------------- #
def _home() -> Path:
    return Path(os.environ.get("HH_HOME") or Path.home())


def _hermes_home() -> Path:
    env = os.environ.get("HH_HERMES_HOME") or os.environ.get("HERMES_HOME")
    return Path(env) if env else _home() / ".hermes"


def _default_manifest() -> Path:
    return Path(__file__).resolve().parent.parent / "neutralize.yaml"


def _jobs_path() -> Path:
    return _hermes_home() / "cron" / "jobs.json"


def _load_yaml(path: Path):
    if yaml is None:
        raise RuntimeError("PyYAML is required to read neutralize.yaml")
    if not path.exists():
        return None
    with path.open() as fh:
        return yaml.safe_load(fh)


def load_manifest(manifest_path: Path | None = None) -> dict:
    """The Talent's declared neutralize steps (``neutralize.yaml``)."""
    path = Path(manifest_path) if manifest_path else _default_manifest()
    data = _load_yaml(path) or {}
    data.setdefault("steps", [])
    return data


def declared(manifest: dict) -> list[dict]:
    """The declared neutralize steps, in order — each a dict with at least ``id``."""
    return [s for s in manifest.get("steps", []) if isinstance(s, dict) and s.get("id")]


# --------------------------------------------------------------------------- #
# applied marker — DATA PLANE, never the overlay (survives converge/restore)   #
# --------------------------------------------------------------------------- #
def _marker_path(bot: str) -> Path:
    return _hermes_home() / "data" / bot / "neutralize.json"


def _read_applied(bot: str) -> set[str]:
    p = _marker_path(bot)
    if not p.exists():
        return set()  # a never-neutralized box → every declared step is pending (fail-closed)
    try:
        return set(json.loads(p.read_text()).get("applied", []))
    except (json.JSONDecodeError, OSError):
        return set()


def _write_applied(bot: str, applied: set[str]) -> None:
    p = _marker_path(bot)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps({"applied": sorted(applied)}, indent=2))
    tmp.replace(p)


def pending(manifest: dict, applied: set[str]) -> list[dict]:
    return [s for s in declared(manifest) if s["id"] not in applied]


def pending_for(manifest_path: Path | None = None) -> list[dict]:
    manifest = load_manifest(manifest_path)
    bot = manifest.get("bot") or ""
    return pending(manifest, _read_applied(bot)) if bot else declared(manifest)


def all_applied(manifest_path: Path | None = None) -> bool:
    """True iff every declared step is recorded applied — the gate ``check_neutralize``
    asserts before allowing a gateway start. A Talent with NO neutralize.yaml has no
    steps, so it is trivially all-applied (nothing to de-fang)."""
    return not pending_for(manifest_path)


def _format_status(pend: list[dict]) -> str:
    """The single line the boot gate / status surfaces."""
    if not pend:
        return "NEUTRALIZE: ok"
    parts = ", ".join(f"{s['id']} ({s.get('kind', 'checklist')})" for s in pend)
    return ("NEUTRALIZE: pending — " + parts +
            "  => run `neutralize.py --all` (deterministic) then follow references/neutralize.md")


def status_line(manifest_path: Path | None = None) -> str:
    """Importable, never-raises status line."""
    try:
        return _format_status(pending_for(manifest_path))
    except Exception:
        return "NEUTRALIZE: pending — (unreadable manifest; fail-closed)"


# --------------------------------------------------------------------------- #
# actions                                                                      #
# --------------------------------------------------------------------------- #
def _mark(bot: str, ids: list[str]) -> dict:
    applied = _read_applied(bot)
    added = [i for i in ids if i not in applied]
    applied |= set(ids)
    _write_applied(bot, applied)
    return {"result": "MARKED", "added": added, "applied": sorted(applied)}


def _apply_sql(manifest: dict, step: dict) -> dict:
    bot = manifest.get("bot") or ""
    sid = step["id"]
    sql = step.get("sql")
    if not sql:
        return {"result": "ERROR", "id": sid, "reason": "sql step has no `sql` body"}
    db_name = step.get("db") or manifest.get("db")
    db = _hermes_home() / "data" / bot / db_name if db_name else None
    if db is None or not db.exists():
        return {"result": "ERROR", "id": sid, "reason": f"db not found at {db}"}
    con = sqlite3.connect(str(db))
    try:
        con.executescript(sql)
        con.commit()
    except sqlite3.OperationalError as e:
        # idempotent: a re-run after a crash must not fail on an already-applied change
        if not any(k in str(e).lower() for k in ("duplicate column", "already exists",
                                                  "no such")):
            return {"result": "ERROR", "id": sid, "reason": f"sql failed: {e}"}
    finally:
        con.close()
    _mark(bot, [sid])
    return {"result": "APPLIED", "id": sid, "kind": "sql"}


def _apply_crons(manifest: dict, step: dict) -> dict:
    """Disable the named outbound cron jobs in ``~/.hermes/cron/jobs.json`` — the core
    'a clone must not fire' guarantee. Detect-then-act: a missing jobs.json or an
    already-absent job is a no-op (the clone simply has no such cron to fire)."""
    bot = manifest.get("bot") or ""
    sid = step["id"]
    cfg = step.get("crons") or {}
    names = list(cfg.get("disable", []))
    if not names:
        return {"result": "ERROR", "id": sid, "reason": "crons step lists no jobs to disable"}
    jp = _jobs_path()
    if not jp.exists():
        # no scheduler file -> nothing outbound to disarm; the step is satisfied.
        _mark(bot, [sid])
        return {"result": "APPLIED", "id": sid, "kind": "crons", "disabled": [], "note": "no jobs.json"}
    try:
        data = json.loads(jp.read_text())
    except (json.JSONDecodeError, OSError) as e:
        return {"result": "ERROR", "id": sid, "reason": f"jobs.json unreadable: {e}"}
    jobs = data.get("jobs", [])
    targets = set(names)
    disabled = []
    for j in jobs:
        if j.get("name") in targets:
            j["enabled"] = False  # Hermes' scheduler skips a job with enabled=false
            j["active"] = False    # belt-and-braces for either schema key
            disabled.append(j.get("name"))
    tmp = jp.with_name(jp.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(jp)
    _mark(bot, [sid])
    return {"result": "APPLIED", "id": sid, "kind": "crons", "disabled": disabled}


def _apply_one(manifest: dict, step: dict) -> dict:
    """Run one DETERMINISTIC step (sql|crons) and mark it. A ``checklist`` step is refused
    here — it needs the agent/operator (record it with --mark after following the ref)."""
    sid = step["id"]
    kind = step.get("kind", "checklist")
    if kind == "sql":
        return _apply_sql(manifest, step)
    if kind == "crons":
        return _apply_crons(manifest, step)
    if kind == "checklist":
        return {"result": "ERROR", "id": sid,
                "reason": (f"'{sid}' is an agent/operator-run (checklist) step — follow "
                           f"{step.get('ref', 'references/neutralize.md')}, then "
                           f"`neutralize.py --mark {sid}`")}
    return {"result": "ERROR", "id": sid, "reason": f"unknown neutralize kind '{kind}'"}


def _apply_all(manifest: dict) -> dict:
    """Run every PENDING deterministic step (sql+crons) in order; leave checklist steps
    pending for the operator. Stops marking a step that fails to apply (so the boot gate
    stays closed) but continues the rest, reporting every outcome."""
    bot = manifest.get("bot") or ""
    applied = _read_applied(bot)
    outcomes, errors, deferred = [], [], []
    for step in declared(manifest):
        if step["id"] in applied:
            continue
        kind = step.get("kind", "checklist")
        if kind == "checklist":
            deferred.append({"id": step["id"], "ref": step.get("ref")})
            continue
        out = _apply_one(manifest, step)
        outcomes.append(out)
        if out["result"] != "APPLIED":
            errors.append(out)
    return {"result": "ALL", "applied": outcomes, "errors": errors,
            "deferred_checklist": deferred,
            "all_applied": all_applied_from(manifest, bot)}


def all_applied_from(manifest: dict, bot: str) -> bool:
    return not pending(manifest, _read_applied(bot))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Oteny Talent in-box neutralize runner")
    ap.add_argument("--manifest", default=None, help="override neutralize.yaml location")
    ap.add_argument("--status", action="store_true", help="list pending steps (default)")
    ap.add_argument("--all", action="store_true", dest="run_all",
                    help="run every pending DETERMINISTIC step (sql+crons)")
    ap.add_argument("--apply", metavar="ID", help="run one deterministic step + mark")
    ap.add_argument("--mark", metavar="ID", help="record an agent/operator-run (checklist) step done")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    manifest = load_manifest(Path(args.manifest) if args.manifest else None)
    bot = manifest.get("bot") or ""

    if args.run_all:
        out = _apply_all(manifest)
    elif args.mark:
        out = _mark(bot, [args.mark])
    elif args.apply:
        step = {s["id"]: s for s in declared(manifest)}.get(args.apply)
        out = (_apply_one(manifest, step) if step is not None
               else {"result": "ERROR", "id": args.apply, "reason": "unknown step id"})
    else:  # default action is --status
        pend = pending(manifest, _read_applied(bot))
        out = {"result": "STATUS", "bot": bot, "ok": not pend, "pending": [
            {"id": s["id"], "kind": s.get("kind", "checklist"),
             "ref": s.get("ref"), "summary": s.get("summary")} for s in pend]}

    if args.json:
        print(json.dumps(out, indent=2))
        return 0
    if out["result"] == "STATUS":
        print(_format_status(out["pending"]))
        for s in out["pending"]:
            line = f"  - {s['id']} ({s['kind']}): {(s.get('summary') or '').strip()}"
            print(line + (f"  -> {s['ref']}" if s.get("ref") else ""))
    elif out["result"] == "ALL":
        print(_format_status(pending(manifest, _read_applied(bot))))
        for o in out["applied"]:
            print(f"  {o['result']}: {o.get('id')} ({o.get('kind', '?')})")
        for d in out["deferred_checklist"]:
            print(f"  DEFERRED(checklist): {d['id']}  -> {d.get('ref')}")
    elif out["result"] == "ERROR":
        print(f"ERROR: {out.get('id', '')}: {out.get('reason', '')}")
    else:
        print(f"{out['result']}: applied={out.get('applied') or out.get('added')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
