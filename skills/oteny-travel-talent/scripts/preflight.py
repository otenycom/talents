#!/usr/bin/env python3
"""preflight — the ONE per-turn context call for OtenyTravelTalent.

The triage would otherwise spend several tool calls before it can classify a message:
the first-run guard, a clock check, "is there an active trip?", "what's on today's
schedule?", "how many todos are open?", "who is in the party?", a `cat memory.md`, and
"is there an overrides.md?". On a weak runtime model that fan-out is most of a slow
turn. This script answers all of them in **one** read-only call:

    python3 ~/.hermes/skills/talents/oteny-travel-talent/scripts/preflight.py

It prints, in a compact parseable block:
  * READY    — fast proxy for "can I plan now?" (db + 6 tables + profile fields).
               When `no`, run the full ``selfcheck.py`` for the detailed missing list,
               then onboarding. (selfcheck stays the authority; this is the cheap path.)
  * NOW      — local time in the tenant's home timezone (re-verify live before any
               leave-by; never frame a departure from a remembered clock).
  * PROFILE  — home_city / home_timezone / language / default_currency / prefs.
  * TRIP     — the active (or soonest upcoming) trip: name, destination, dates, status,
               days-to-go, and whether it is bound to a group.
  * TODAY    — today's itinerary rows for the active trip (no double-scheduling).
  * TODOS    — count of still-open todos for the active trip.
  * ROSTER   — the travel party (group trips only).
  * MEMORY   — the per-bot durable preferences (not auto-loaded by Hermes).
  * OVERRIDES— whether a per-tenant overrides.md exists (the agent must honor it).

Pure / read-only / side-effect-free; safe to run on every turn. Exit code is always 0
(a non-zero would make the LLM's terminal call look failed) — readiness is in the
output, not the exit code. Paths resolve through the same env overrides as selfcheck.py
so a relocated overlay / tests stay hermetic.
"""
from __future__ import annotations

import os
import sqlite3
import sys
from datetime import date, datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - PyYAML is always present on Hermes
    yaml = None

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - py>=3.9 on Hermes
    ZoneInfo = None

_BOT = "oteny-travel-talent"
_DB_TABLES = ["trips", "members", "bookings", "itinerary", "todos", "expenses"]
_PROFILE_REQUIRED = ["home_city", "home_timezone", "language", "default_currency"]
# The fields the concierge wants in hand every turn (shown when present).
_PROFILE_SHOW = [
    "language", "home_timezone", "home_city", "default_currency",
    "traveller_prefs", "reminders",
]


def _home() -> Path:
    return Path(os.environ.get("HH_HOME") or Path.home())


def _hermes_home() -> Path:
    env = os.environ.get("HH_HERMES_HOME") or os.environ.get("HERMES_HOME")
    return Path(env) if env else _home() / ".hermes"


def _data_dir() -> Path:
    return _hermes_home() / "data" / _BOT


def _migrations_line() -> str:
    """The pending-migration gate (see scripts/migrate.py). Surfaced here so the single
    per-turn context call also tells the agent to reconcile any prior-version state
    (e.g. old-shape crons) BEFORE planning. Never raises — a missing runner ⇒ 'none'."""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import migrate  # sibling shared runner
        return migrate.status_line()
    except Exception:
        return "MIGRATIONS: none"


def _load_yaml(path: Path):
    if yaml is None or not path.exists():
        return None
    try:
        with path.open() as fh:
            return yaml.safe_load(fh)
    except Exception:
        return None


def _connect(db: Path):
    return sqlite3.connect(str(db)) if db.exists() else None


def _db_tables(db: Path) -> set[str]:
    con = _connect(db)
    if con is None:
        return set()
    try:
        return {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    except sqlite3.Error:
        return set()
    finally:
        con.close()


def _now(profile: dict | None) -> datetime:
    tz_name = (profile or {}).get("home_timezone") or "UTC"
    tz = None
    if ZoneInfo is not None:
        try:
            tz = ZoneInfo(str(tz_name))
        except Exception:
            tz = None
    return datetime.now(tz) if tz else datetime.now(timezone.utc)


def _now_line(profile: dict | None) -> str:
    tz_name = (profile or {}).get("home_timezone") or "UTC"
    valid = ZoneInfo is not None and _tz_ok(tz_name)
    shown_tz = tz_name if valid else "UTC (profile tz unknown)"
    return f"NOW: {_now(profile):%H:%M %A %Y-%m-%d}  (tz={shown_tz})"


def _tz_ok(tz_name: str) -> bool:
    if ZoneInfo is None:
        return False
    try:
        ZoneInfo(str(tz_name))
        return True
    except Exception:
        return False


def _profile_line(profile: dict | None) -> str:
    if not profile:
        return "PROFILE: (none yet)"
    parts = [f"{k}={profile[k]}" for k in _PROFILE_SHOW
             if profile.get(k) not in (None, "", [], {})]
    return "PROFILE: " + (" | ".join(parts) if parts else "(no recognised fields)")


def _active_trip(con, today: str) -> dict | None:
    """The trip to centre this turn on: an explicitly active trip, else the soonest
    trip still running or upcoming (end_date >= today), else the most recent."""
    cols = "id, name, destination, start_date, end_date, status, group_chat_id"
    try:
        row = con.execute(
            f"SELECT {cols} FROM trips WHERE status='active' "
            "ORDER BY start_date LIMIT 1").fetchone()
        if row is None:
            row = con.execute(
                f"SELECT {cols} FROM trips WHERE status!='cancelled' "
                "AND (end_date IS NULL OR end_date >= ?) "
                "ORDER BY start_date LIMIT 1", (today,)).fetchone()
        if row is None:
            row = con.execute(
                f"SELECT {cols} FROM trips WHERE status!='cancelled' "
                "ORDER BY COALESCE(start_date,'') DESC LIMIT 1").fetchone()
    except sqlite3.Error:
        return None
    if row is None:
        return None
    keys = ["id", "name", "destination", "start_date", "end_date", "status", "group_chat_id"]
    return dict(zip(keys, row))


def _days_to_go(start_date: str | None, today: date) -> str:
    if not start_date:
        return ""
    try:
        d = date.fromisoformat(start_date)
    except ValueError:
        return ""
    delta = (d - today).days
    if delta > 0:
        return f", in {delta}d"
    if delta == 0:
        return ", today"
    return f", started {-delta}d ago"


def _trip_block(con, profile: dict | None) -> tuple[str, dict | None]:
    today = _now(profile).date()
    trip = _active_trip(con, today.isoformat())
    if trip is None:
        return "TRIP: (none yet — start one with the tenant)", None
    bound = "group-bound" if trip.get("group_chat_id") else "DM/solo"
    dest = f" → {trip['destination']}" if trip.get("destination") else ""
    span = ""
    if trip.get("start_date"):
        span = f" {trip['start_date']}..{trip.get('end_date') or '?'}"
    line = (f"TRIP: #{trip['id']} {trip['name']}{dest}{span}  "
            f"[{trip['status']}{_days_to_go(trip.get('start_date'), today)}; {bound}]")
    return line, trip


def _today_block(con, trip: dict | None, profile: dict | None) -> str:
    if trip is None:
        return "TODAY: (no active trip)"
    today = _now(profile).date().isoformat()
    try:
        rows = con.execute(
            "SELECT time, title, place, category FROM itinerary "
            "WHERE trip_id=? AND day_date=? ORDER BY COALESCE(time,'99:99'), id",
            (trip["id"], today)).fetchall()
    except sqlite3.Error as exc:
        return f"TODAY: (query error: {exc})"
    if not rows:
        return "TODAY: (nothing scheduled today)"
    out = ["TODAY scheduled:"]
    for t, title, place, cat in rows:
        bits = [b for b in [t, title, place, cat] if b]
        out.append("  " + " · ".join(str(b) for b in bits))
    return "\n".join(out)


def _todos_block(con, trip: dict | None) -> str:
    if trip is None:
        return "TODOS: (no active trip)"
    try:
        n = con.execute("SELECT COUNT(*) FROM todos WHERE trip_id=? AND done=0",
                        (trip["id"],)).fetchone()[0]
    except sqlite3.Error:
        return "TODOS: (query error)"
    return f"TODOS: {n} open"


def _roster_block(con, trip: dict | None) -> str:
    if trip is None or not trip.get("group_chat_id"):
        return "ROSTER: (DM/solo — no party)"
    try:
        rows = con.execute(
            "SELECT display_name, role, telegram_user FROM members "
            "WHERE trip_id=? ORDER BY id", (trip["id"],)).fetchall()
    except sqlite3.Error:
        return "ROSTER: (query error)"
    if not rows:
        return "ROSTER: (group-bound, no members mapped yet)"
    people = [f"{n}({r}" + (f"={u}" if u else "") + ")" for n, r, u in rows]
    return "ROSTER: " + ", ".join(people)


def _memory_block(data_dir: Path) -> str:
    mem = data_dir / "memory.md"
    head = f"MEMORY ({mem}):"
    if not mem.exists() or mem.stat().st_size == 0:
        return head + "\n  (empty — no durable preferences recorded yet)"
    text = mem.read_text(errors="replace").strip()
    return head + "\n" + "\n".join("  " + ln for ln in text.splitlines())


def _overrides_block(data_dir: Path) -> str:
    """Surface whether a per-tenant override doc exists. The global SOUL rule
    tells the agent to honor it with precedence — preflight just flags its presence so
    the weak model remembers to read+obey it this turn."""
    ov = data_dir / "overrides.md"
    if ov.exists() and ov.stat().st_size > 0:
        return (f"OVERRIDES: yes ({ov}) — READ IT and let its rules take precedence "
                "over the base skill where they conflict.")
    return "OVERRIDES: none"


def _readiness(db: Path, profile_path: Path, profile: dict | None):
    """Fast proxy for selfcheck: db + 6 tables present and required profile fields set."""
    missing: list[str] = []
    tables = _db_tables(db)
    if not db.exists():
        missing.append("db(file missing)")
    else:
        absent = [t for t in _DB_TABLES if t not in tables]
        if absent:
            missing.append(f"db_tables={absent}")
    if profile is None:
        missing.append("profile(file missing)" if not profile_path.exists()
                       else "profile(unreadable)")
    else:
        unset = [f for f in _PROFILE_REQUIRED
                 if profile.get(f) in (None, "", [], 0)]
        if unset:
            missing.append(f"profile_fields={unset}")
    return (not missing), missing


def main() -> int:
    data_dir = _data_dir()
    db = data_dir / "trips.db"
    profile_path = data_dir / "profile.yaml"
    profile = _load_yaml(profile_path)

    ready, missing = _readiness(db, profile_path, profile)

    print(f"=== OtenyTravelTalent preflight ({_BOT}) ===")
    if ready:
        print("READY: yes")
    else:
        print(f"READY: no  (missing: {'; '.join(missing)})")
        print("  => run selfcheck.py for the full list, then onboarding; "
              "do NOT plan until READY.")
    print(_migrations_line())
    print(_now_line(profile))
    print(_profile_line(profile))

    con = _connect(db)
    if con is None:
        print("TRIP: (no database yet)")
        print("TODAY: (no database yet)")
        print("TODOS: (no database yet)")
        print("ROSTER: (no database yet)")
    else:
        try:
            trip_line, trip = _trip_block(con, profile)
            print(trip_line)
            print(_today_block(con, trip, profile))
            print(_todos_block(con, trip))
            print(_roster_block(con, trip))
        finally:
            con.close()
    print(_memory_block(data_dir))
    print(_overrides_block(data_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
