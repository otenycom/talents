#!/usr/bin/env python3
"""migrate — the in-box, forward-only state-migration runner for an Oteny Talent.

A converge swaps a Talent's FILES data-safely, but it never touches the live state a
Talent owns on the box — its SQLite db, profile/memory/overrides, and (the hard one) its
REGISTERED CRON JOBS, which only the agent can re-plan (the ``cronjob`` tool needs the
live chat origin). So when a new Talent version changes the SHAPE of that state, the agent
reconciles it IN-BOX from a declared, versioned checklist — never an operator hand-editing
the VM.

This is the migration analog of ``selfcheck.py``: ONE reusable runner keyed on each
Talent's ``migrations.yaml`` (the ordered, forward-only list). It tells the agent which
migrations are still PENDING; runs the DETERMINISTIC ones itself (a ``sql`` migration);
and records completion in a DATA-PLANE marker (``~/.hermes/data/<bot>/migrations.json``)
that survives every converge/backup/restore. An AGENT-ASSISTED (``checklist``)
migration — anything needing the LLM or the ``cronjob`` tool — is run by following the
Talent's ``references/migrations.md`` section, then recorded with ``--mark``.

Forward-only + idempotent, exactly like the sidecar migrations but run by the AGENT
on live state, not by the deployer on files:
  * a FRESH box ends first-run with ``--baseline`` (marks every current migration applied
    WITHOUT running it — a box born current has nothing to reconcile);
  * a LEGACY box has no marker, so every declared migration is pending and runs forward;
    each migration is written detect-then-act, so running an already-satisfied one no-ops.

Usage (the bundle ships an identical copy at ``<bot>/scripts/migrate.py``):

    python3 migrate.py --status [--json]   # MIGRATIONS: none | pending — <id> (<kind>), …
    python3 migrate.py --apply <id>        # run a deterministic (sql) migration + mark it
    python3 migrate.py --mark <id>         # record an agent-run (checklist) migration done
    python3 migrate.py --baseline          # mark ALL current migrations applied (fresh first-run)

By default the manifest is ``<script_dir>/../migrations.yaml``. Home roots resolve through
the same env overrides as ``selfcheck.py`` (HH_HOME / HH_HERMES_HOME / HERMES_HOME) so
tests and a relocated overlay stay hermetic. Exit code is always 0 when the operation ran
(a non-zero would make the LLM's terminal call look failed) — the outcome is in the output.
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
# path resolution (env-overridable so tests are hermetic) — mirrors selfcheck  #
# --------------------------------------------------------------------------- #
def _home() -> Path:
    return Path(os.environ.get("HH_HOME") or Path.home())


def _hermes_home() -> Path:
    env = os.environ.get("HH_HERMES_HOME") or os.environ.get("HERMES_HOME")
    return Path(env) if env else _home() / ".hermes"


def _default_manifest() -> Path:
    return Path(__file__).resolve().parent.parent / "migrations.yaml"


def _load_yaml(path: Path):
    if yaml is None:
        raise RuntimeError("PyYAML is required to read migrations.yaml")
    if not path.exists():
        return None
    with path.open() as fh:
        return yaml.safe_load(fh)


def load_manifest(manifest_path: Path | None = None) -> dict:
    """The Talent's ordered, forward-only migration list (``migrations.yaml``)."""
    path = Path(manifest_path) if manifest_path else _default_manifest()
    data = _load_yaml(path) or {}
    data.setdefault("migrations", [])
    return data


def declared(manifest: dict) -> list[dict]:
    """The declared migrations, in order — each a dict with at least ``id``."""
    return [m for m in manifest.get("migrations", []) if isinstance(m, dict) and m.get("id")]


# --------------------------------------------------------------------------- #
# applied marker — DATA PLANE, never the overlay (survives converge/restore)   #
# --------------------------------------------------------------------------- #
def _marker_path(bot: str) -> Path:
    return _hermes_home() / "data" / bot / "migrations.json"


def _read_applied(bot: str) -> set[str]:
    p = _marker_path(bot)
    if not p.exists():
        return set()  # legacy box (no marker) → every declared migration is pending
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
    return [m for m in declared(manifest) if m["id"] not in applied]


def pending_for(manifest_path: Path | None = None) -> list[dict]:
    manifest = load_manifest(manifest_path)
    bot = manifest.get("bot") or ""
    return pending(manifest, _read_applied(bot)) if bot else []


def _format_status(pend: list[dict]) -> str:
    """The single line preflight injects so the agent migrates before it plans."""
    if not pend:
        return "MIGRATIONS: none"
    parts = ", ".join(f"{m['id']} ({m.get('kind', 'checklist')})" for m in pend)
    return ("MIGRATIONS: pending — " + parts +
            "  => load references/migrations.md and run each in order, then continue")


def status_line(manifest_path: Path | None = None) -> str:
    """Importable, never-raises status line (preflight calls this)."""
    try:
        return _format_status(pending_for(manifest_path))
    except Exception:
        return "MIGRATIONS: none"


# --------------------------------------------------------------------------- #
# actions                                                                      #
# --------------------------------------------------------------------------- #
def _mark(bot: str, ids: list[str]) -> dict:
    applied = _read_applied(bot)
    added = [i for i in ids if i not in applied]
    applied |= set(ids)
    _write_applied(bot, applied)
    return {"result": "MARKED", "added": added, "applied": sorted(applied)}


def _baseline(manifest: dict) -> dict:
    """Mark every declared migration applied WITHOUT running it (fresh first-run)."""
    bot = manifest.get("bot") or ""
    ids = {m["id"] for m in declared(manifest)}
    applied = _read_applied(bot) | ids
    _write_applied(bot, applied)
    return {"result": "BASELINED", "applied": sorted(applied)}


def _apply_one(manifest: dict, mig: dict) -> dict:
    """Run a DETERMINISTIC (``sql``) migration and mark it. A ``checklist`` migration is
    refused here — it needs the agent (and the ``cronjob`` tool's live origin)."""
    bot = manifest.get("bot") or ""
    mid = mig["id"]
    kind = mig.get("kind", "checklist")
    if kind == "checklist":
        return {"result": "ERROR", "id": mid,
                "reason": (f"'{mid}' is an agent-run (checklist) migration — follow "
                           f"{mig.get('ref', 'references/migrations.md')}, then "
                           f"`migrate.py --mark {mid}`")}
    if kind != "sql":
        return {"result": "ERROR", "id": mid, "reason": f"unknown migration kind '{kind}'"}
    sql = mig.get("sql")
    if not sql:
        return {"result": "ERROR", "id": mid, "reason": "sql migration has no `sql` body"}
    db_name = manifest.get("db")
    db = _hermes_home() / "data" / bot / db_name if db_name else None
    if db is None or not db.exists():
        return {"result": "ERROR", "id": mid, "reason": f"db not found at {db}"}
    con = sqlite3.connect(str(db))
    try:
        # Apply statement-by-statement (NOT executescript, which is all-or-nothing on a re-run):
        # a partial prior apply (e.g. crash between two ALTERs) must let an already-applied
        # statement be skipped while a not-yet-applied one in the same migration still runs.
        # DDL migrations carry no string-literal ';', so a plain split is safe.
        for stmt in sql.split(";"):
            s = stmt.strip()
            if not s:
                continue
            try:
                con.execute(s)
            except sqlite3.OperationalError as e:
                # idempotent PER STATEMENT: an already-applied change is a clean no-op
                if not any(k in str(e).lower() for k in ("duplicate column", "already exists")):
                    raise
        con.commit()
    except sqlite3.OperationalError as e:
        return {"result": "ERROR", "id": mid, "reason": f"sql failed: {e}"}
    finally:
        con.close()
    _mark(bot, [mid])
    return {"result": "APPLIED", "id": mid, "kind": "sql"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Oteny Talent in-box migration runner")
    ap.add_argument("--manifest", default=None, help="override migrations.yaml location")
    ap.add_argument("--status", action="store_true", help="list pending migrations (default)")
    ap.add_argument("--apply", metavar="ID", help="run a deterministic (sql) migration + mark")
    ap.add_argument("--mark", metavar="ID", help="record an agent-run (checklist) migration done")
    ap.add_argument("--baseline", action="store_true", help="mark ALL current migrations applied")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    manifest = load_manifest(Path(args.manifest) if args.manifest else None)
    bot = manifest.get("bot") or ""

    if args.baseline:
        out = _baseline(manifest)
    elif args.mark:
        out = _mark(bot, [args.mark])
    elif args.apply:
        mig = {m["id"]: m for m in declared(manifest)}.get(args.apply)
        out = (_apply_one(manifest, mig) if mig is not None
               else {"result": "ERROR", "id": args.apply, "reason": "unknown migration id"})
    else:  # default action is --status
        pend = pending(manifest, _read_applied(bot))
        out = {"result": "STATUS", "bot": bot, "pending": [
            {"id": m["id"], "kind": m.get("kind", "checklist"),
             "ref": m.get("ref"), "summary": m.get("summary")} for m in pend]}

    if args.json:
        print(json.dumps(out, indent=2))
        return 0
    if out["result"] == "STATUS":
        print(_format_status(out["pending"]))
        for m in out["pending"]:
            line = f"  - {m['id']} ({m['kind']}): {(m.get('summary') or '').strip()}"
            print(line + (f"  -> {m['ref']}" if m.get("ref") else ""))
    elif out["result"] == "ERROR":
        print(f"ERROR: {out.get('id', '')}: {out.get('reason', '')}")
    else:
        print(f"{out['result']}: applied={out.get('applied') or out.get('added')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
