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

W1 adds a tighter **departure-imminent** loop for the NL live board's track changes:
``--due --imminent`` returns only legs leaving in the next ~50 min, and ``--update`` takes a
structured ``--track`` (the spoor the enriched board returned) so the diff prints
``TRACK CHANGED: '5' -> '9'`` deterministically — the model pushes "your train now departs
spoor 9, not 5" on that, and dedupes (the stored track means a repeat tick is UNCHANGED).

Keeping selection + diff + persistence in a script (not the weak model) is the
deterministic guard against a missed or hallucinated delay. A failed lookup must surface
as an actionable error — NEVER as an empty "all clear" (that silently mis-routes).

    python3 monitor_transport.py --due [--imminent] [--json]
    python3 monitor_transport.py --update --leg 12 --status "delayed 5m" --track 9 --delay 5

Exit code is always 0 (a non-zero would make the LLM's terminal call look failed); the
outcome is in the output. Paths resolve through the same env overrides as preflight.py.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

_BOT = "oteny-travel-talent"
# The monitor window margins — kept in step with provision_cron.py (the planner that
# sizes the cron firing window), so every cron tick has work to do (no idle [SILENT]
# burns). Quarantined numerics.
MONITOR_MARGIN_DAYS = 2    # start watching this many days BEFORE departure
END_MARGIN_DAYS = 1        # keep watching this many days AFTER the trip ends (claims)
# The departure-imminent monitor (W1): the tight window before a booked leg leaves, where a
# track-change / late delay actually matters. Generous enough to survive a VM-vs-trip timezone
# skew (we parse start_ts in the owner's home_timezone), tight enough that nearly every
# off-window tick is a cheap [SILENT].
IMMINENT_AHEAD_MIN = 50    # watch a leg departing within the next ~50 min
IMMINENT_BEHIND_MIN = 15   # ...and up to 15 min after (a track change still matters at boarding)


def _home() -> Path:
    return Path(os.environ.get("HH_HOME") or Path.home())


def _hermes_home() -> Path:
    env = os.environ.get("HH_HERMES_HOME") or os.environ.get("HERMES_HOME")
    return Path(env) if env else _home() / ".hermes"


def _default_db() -> Path:
    return _hermes_home() / "data" / _BOT / "trips.db"


def _tenant_tz() -> str:
    """The owner's home timezone from profile.yaml — so start_ts (stored ISO LOCAL) is
    compared in the right frame for the imminent window. Minimal scan (no yaml dep);
    'UTC' if absent/unreadable."""
    p = _hermes_home() / "data" / _BOT / "profile.yaml"
    try:
        for line in p.read_text().splitlines():
            m = re.match(r"\s*home_timezone:\s*['\"]?([^'\"#\s]+)", line)
            if m:
                return m.group(1)
    except OSError:
        pass
    return "UTC"


def _is_imminent(start_ts, tz_name: str, now_utc: datetime) -> bool:
    """True if `start_ts` (ISO local in `tz_name`) is within
    [now − IMMINENT_BEHIND_MIN, now + IMMINENT_AHEAD_MIN]."""
    if not start_ts:
        return False
    try:
        naive = datetime.fromisoformat(str(start_ts).replace(" ", "T", 1))
        local = naive.replace(tzinfo=ZoneInfo(tz_name))
        delta_min = (local.astimezone(timezone.utc) - now_utc).total_seconds() / 60
    except Exception:  # noqa: BLE001 — a bad ts / unknown zone → just "not imminent"
        return False
    return -IMMINENT_BEHIND_MIN <= delta_min <= IMMINENT_AHEAD_MIN


def _connect(db: Path):
    if not db.exists():
        return None
    con = sqlite3.connect(str(db))
    con.row_factory = sqlite3.Row
    return con


def due_legs(con, imminent: bool = False) -> list[dict]:
    """Monitored legs whose trip window is live today: (start − MONITOR_MARGIN_DAYS) …
    (end + END_MARGIN_DAYS) inclusive.

    The window gate lives in SQL so a too-early cron tick returns nothing (the LLM then
    sends [SILENT]) — that is how a far-future trip costs no model time before its window.
    The bounds mirror the cron firing window provision_cron.py sizes, so an in-window tick
    always has a leg to check.

    ``imminent`` (W1) narrows to legs *departing in the next ~50 min* (the departure-imminent
    monitor that catches a last-second track change). The day-window SQL stays the cheap first
    cut; the minute-precise window is applied in Python in the owner's home timezone (start_ts
    is stored ISO LOCAL), so nearly every off-window imminent tick returns nothing → [SILENT].
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
    legs = [dict(r) for r in rows]
    if imminent:
        tz, now = _tenant_tz(), datetime.now(timezone.utc)
        legs = [r for r in legs if _is_imminent(r.get("start_ts"), tz, now)]
    return legs


def _norm(s) -> str:
    return " ".join(str(s or "").split()).strip().lower()


def update_leg(con, leg_id: int, status: str,
               track: str | None = None, delay_min: int | None = None) -> dict:
    """Persist a freshly-fetched status and report whether it CHANGED vs the stored one.

    Returns a result dict; a missing/unmonitored leg is an actionable ERROR, never a
    silent no-op (the semantic-errors-never-fake-empty-data discipline).

    W1: when ``track`` is given (the departure-imminent monitor), also persist the structured
    ``track``/``delay_min`` and report ``track_changed`` — a deterministic platform/spoor diff
    vs the last seen one (the dedupe + the high-value push signal), so the model pushes on a
    real track change, not on every wording wobble of the free-text status. The plain
    status-only path (the 6h monitor, and pre-migration dbs) never touches the new columns."""
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
    track_changed, prior_track = False, None
    if track is not None:  # the imminent path — track/delay_min columns exist (migration 0002)
        tr = con.execute("SELECT track FROM bookings WHERE id=?", (leg_id,)).fetchone()
        prior_track = tr["track"] if tr else None
        track_changed = bool(track.strip()) and _norm(prior_track) != _norm(track)
        con.execute("UPDATE bookings SET status=?, track=?, delay_min=? WHERE id=?",
                    (status, track, delay_min, leg_id))
    else:
        con.execute("UPDATE bookings SET status=? WHERE id=?", (status, leg_id))
    con.commit()
    return {"result": "CHANGED" if changed else "UNCHANGED", "leg": leg_id,
            "ref": row["booking_ref"] or row["carrier"], "from": prior, "to": status,
            "track_changed": track_changed, "prior_track": prior_track, "track": track}


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
        line = (f"{obj['result']}: leg #{obj['leg']} "
                + (obj.get("reason") or f"{obj.get('from')!r} -> {obj.get('to')!r}"))
        if obj.get("track_changed"):
            line += f"  TRACK CHANGED: {obj.get('prior_track')!r} -> {obj.get('track')!r}"
        print(line)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="OtenyTravelTalent transport monitor backbone")
    ap.add_argument("--db", default=None)
    ap.add_argument("--due", action="store_true", help="list monitored legs due a check")
    ap.add_argument("--imminent", action="store_true",
                    help="with --due: only legs departing in the next ~50 min (W1 push)")
    ap.add_argument("--update", action="store_true", help="record a fetched status")
    ap.add_argument("--leg", type=int, help="booking id (with --update)")
    ap.add_argument("--status", help="the live status text (with --update)")
    ap.add_argument("--track", help="the live platform/spoor (with --update; W1 push diff)")
    ap.add_argument("--delay", type=int, help="the live delay in minutes (with --update)")
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
                _emit(update_leg(con, args.leg, args.status,
                                 track=args.track, delay_min=args.delay), args.json)
        else:  # default action is --due
            _emit(due_legs(con, imminent=args.imminent), args.json)
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
