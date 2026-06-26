#!/usr/bin/env python3
"""monitor_transport — the deterministic backbone for OtenyTravelTalent's disruption cron.

A plain script cannot call the `travel` Hermes tool, so the work splits cleanly: this
script does the **deterministic** halves (which legs are due a check, and whether a
freshly-fetched status is a CHANGE), and the LLM does the `travel` call in between. The
monitor cron checklist is therefore:

    1. monitor_transport.py --due          -> the monitored legs whose trip window is live
    2. (LLM) call `travel` for each leg's live status
    3. monitor_transport.py --update --leg <id> --status "<live status>"
                                           -> persists it and prints CHANGED / UNCHANGED
    4. (LLM) message the group/DM ONLY on CHANGED, and offer a reroute

Keeping selection + diff + persistence in a script (not the weak model) is the
deterministic guard against a missed or hallucinated delay. A failed lookup must surface
as an actionable error — NEVER as an empty "all clear" (that silently mis-routes).

    python3 monitor_transport.py --due [--json]
    python3 monitor_transport.py --update --leg 12 --status "delayed 40m, gate B7"

Exit code is always 0 (a non-zero would make the LLM's terminal call look failed); the
outcome is in the output. Paths resolve through the same env overrides as preflight.py.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

_BOT = "oteny-travel-talent"
# The monitor window margins — kept in step with provision_cron.py (the planner that
# sizes the cron firing window), so every cron tick has work to do (no idle [SILENT]
# burns). Quarantined numerics.
MONITOR_MARGIN_DAYS = 2    # start watching this many days BEFORE departure
END_MARGIN_DAYS = 1        # keep watching this many days AFTER the trip ends (claims)


def _home() -> Path:
    return Path(os.environ.get("HH_HOME") or Path.home())


def _hermes_home() -> Path:
    env = os.environ.get("HH_HERMES_HOME") or os.environ.get("HERMES_HOME")
    return Path(env) if env else _home() / ".hermes"


def _default_db() -> Path:
    return _hermes_home() / "data" / _BOT / "trips.db"


def _connect(db: Path):
    if not db.exists():
        return None
    con = sqlite3.connect(str(db))
    con.row_factory = sqlite3.Row
    return con


def due_legs(con) -> list[dict]:
    """Monitored legs whose trip window is live today: (start − MONITOR_MARGIN_DAYS) …
    (end + END_MARGIN_DAYS) inclusive.

    The window gate lives in SQL so a too-early cron tick returns nothing (the LLM then
    sends [SILENT]) — that is how a far-future trip costs no model time before its window.
    The bounds mirror the cron firing window provision_cron.py sizes, so an in-window tick
    always has a leg to check.
    """
    rows = con.execute(
        "SELECT b.id, b.kind, b.title, b.carrier, b.booking_ref, b.from_loc, b.to_loc, "
        "       b.start_ts, b.end_ts, b.status, t.name AS trip_name, t.id AS trip_id "
        "FROM bookings b JOIN trips t ON t.id = b.trip_id "
        "WHERE b.monitor = 1 AND t.status != 'cancelled' "
        "  AND date('now') >= date(t.start_date, ?) "
        "  AND date('now') <= date(COALESCE(t.end_date, t.start_date), ?) "
        "ORDER BY b.start_ts",
        (f"-{MONITOR_MARGIN_DAYS} days", f"+{END_MARGIN_DAYS} days"),
    ).fetchall()
    return [dict(r) for r in rows]


def _norm(s) -> str:
    return " ".join(str(s or "").split()).strip().lower()


def update_leg(con, leg_id: int, status: str) -> dict:
    """Persist a freshly-fetched status and report whether it CHANGED vs the stored one.

    Returns a result dict; a missing/unmonitored leg is an actionable ERROR, never a
    silent no-op (the semantic-errors-never-fake-empty-data discipline)."""
    row = con.execute(
        "SELECT id, monitor, status, carrier, booking_ref FROM bookings WHERE id=?",
        (leg_id,)).fetchone()
    if row is None:
        return {"result": "ERROR", "leg": leg_id, "reason": f"no booking id={leg_id}"}
    if not row["monitor"]:
        return {"result": "ERROR", "leg": leg_id,
                "reason": f"booking id={leg_id} is not monitored (monitor=0)"}
    prior = row["status"]
    changed = _norm(prior) != _norm(status)
    con.execute("UPDATE bookings SET status=? WHERE id=?", (status, leg_id))
    con.commit()
    return {"result": "CHANGED" if changed else "UNCHANGED", "leg": leg_id,
            "ref": row["booking_ref"] or row["carrier"], "from": prior, "to": status}


def _emit(obj, as_json: bool) -> None:
    if as_json:
        print(json.dumps(obj, indent=2))
        return
    if isinstance(obj, list):
        if not obj:
            print("NONE DUE — no monitored legs in an active trip window. Send [SILENT].")
            return
        print(f"{len(obj)} leg(s) due a status check:")
        for r in obj:
            print(f"  • #{r['id']} {r['kind']} {r.get('carrier') or ''} "
                  f"{r.get('booking_ref') or ''}  {r.get('from_loc') or ''}→"
                  f"{r.get('to_loc') or ''}  dep {r.get('start_ts') or '?'}  "
                  f"last_status={r.get('status') or '(none)'}")
    else:
        print(f"{obj['result']}: leg #{obj['leg']} "
              + (obj.get("reason") or f"{obj.get('from')!r} -> {obj.get('to')!r}"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="OtenyTravelTalent transport monitor backbone")
    ap.add_argument("--db", default=None)
    ap.add_argument("--due", action="store_true", help="list monitored legs due a check")
    ap.add_argument("--update", action="store_true", help="record a fetched status")
    ap.add_argument("--leg", type=int, help="booking id (with --update)")
    ap.add_argument("--status", help="the live status text (with --update)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    db = Path(args.db) if args.db else _default_db()
    con = _connect(db)
    if con is None:
        _emit({"result": "ERROR", "leg": args.leg or 0,
               "reason": f"no database at {db}"} if args.update else [], args.json)
        return 0
    try:
        if args.update:
            if args.leg is None or args.status is None:
                _emit({"result": "ERROR", "leg": args.leg or 0,
                       "reason": "--update needs --leg and --status"}, args.json)
            else:
                _emit(update_leg(con, args.leg, args.status), args.json)
        else:  # default action is --due
            _emit(due_legs(con), args.json)
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
