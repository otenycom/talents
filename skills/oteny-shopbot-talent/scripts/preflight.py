#!/usr/bin/env python3
"""preflight — the ONE per-turn context call for OtenyShopBotTalent.

Collapses the per-turn preamble into a single read-only call so a normal turn never
pays for a fan-out of probes (first-run guard, clock, "db reachable?", "what's on the
list?", memory). Run it first on every turn:

    python3 ~/.hermes/skills/talents/oteny-shopbot-talent/scripts/preflight.py

It prints, in a compact parseable block:
  * READY  — a THREE-VALUED proxy for "can I manage the list now?": READY (db + tables +
             profile fields), NOT-READY (a user-state gap → load references/first-run.md), or
             UNKNOWN (an ENVIRONMENT fault — a present-but-unreadable profile / corrupt db →
             report it and STOP; NEVER onboard). selfcheck.py stays the detailed authority.
  * NOW    — local time (so a "weekly nudge" or "on the way home" reads correctly).
  * PROFILE— the few fields needed every turn (default store, household, language, tz).
  * LIST   — active item count + per-store breakdown (grounding: never recite from memory;
             use list_view.py for the full aisle-ordered render).
  * MEMORY — per-bot durable preferences (favourite stores, brands, recurring buys).

Pure / read-only / side-effect-free. Exit code is always 0. Paths resolve through the
same env overrides as selfcheck.py so a relocated overlay / tests stay hermetic.
"""
from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - py>=3.9 on Hermes
    ZoneInfo = None


def _belt():
    """The shared readiness belt (``selfcheck.read_yaml`` + ``UNREADABLE``), loaded from the
    sibling ``selfcheck.py`` by path — the ONE stdlib-first YAML reader every readiness script
    shares, so a cold tenant whose system python3 lacks PyYAML still PARSES profile.yaml
    instead of mis-reading "can't parse" as "not set up → onboard" (the hh00046 incident)."""
    import importlib.util

    p = Path(__file__).resolve().parent / "selfcheck.py"
    spec = importlib.util.spec_from_file_location("oteny_readiness_belt", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_BOT = "oteny-shopbot-talent"
_DB_TABLES = ["items", "store_aliases", "categories"]
_PROFILE_REQUIRED = ["default_store", "language", "timezone"]
_PROFILE_SHOW = ["name", "default_store", "household", "language", "timezone", "reminders"]


def _home() -> Path:
    return Path(os.environ.get("HH_HOME") or Path.home())


def _hermes_home() -> Path:
    env = os.environ.get("HH_HERMES_HOME") or os.environ.get("HERMES_HOME")
    return Path(env) if env else _home() / ".hermes"


def _data_dir() -> Path:
    return _hermes_home() / "data" / _BOT


def _db_probe(db: Path):
    """Three-valued db state: ``"absent"`` (no file → first-run), ``"unreadable"`` (present
    but corrupt/locked → env fault → UNKNOWN), or the set of table names."""
    if not db.exists():
        return "absent"
    try:
        con = sqlite3.connect(str(db))
        try:
            return {r[0] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
        finally:
            con.close()
    except sqlite3.Error:
        return "unreadable"


def _now_line(profile: dict | None) -> str:
    tz_name = (profile or {}).get("timezone") or "UTC"
    tz = None
    if ZoneInfo is not None:
        try:
            tz = ZoneInfo(str(tz_name))
        except Exception:
            tz = None
    now = datetime.now(tz) if tz else datetime.now(timezone.utc)
    shown_tz = tz_name if tz else "UTC (profile tz unknown)"
    return f"NOW: {now:%H:%M %A %Y-%m-%d}  (tz={shown_tz})"


def _profile_line(profile: dict | None) -> str:
    if not profile:
        return "PROFILE: (none yet)"
    parts = [f"{k}={profile[k]}" for k in _PROFILE_SHOW
             if profile.get(k) not in (None, "", [])]
    return "PROFILE: " + (" | ".join(parts) if parts else "(no recognised fields)")


def _list_line(db: Path) -> str:
    if not db.exists():
        return "LIST: (no database yet)"
    con = sqlite3.connect(str(db))
    try:
        have = {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if "items" not in have:
            return "LIST: (no items table yet)"
        total = con.execute(
            "SELECT COUNT(*) FROM items WHERE status='pending'").fetchone()[0]
        rows = con.execute(
            "SELECT COALESCE(store,'(no store)') AS store, COUNT(*) AS n "
            "FROM items WHERE status='pending' GROUP BY store ORDER BY n DESC"
        ).fetchall()
        by_store = ", ".join(f"{r[0]}: {r[1]}" for r in rows) or "—"
        return f"LIST: {total} to buy ({by_store}) — use 'shop.py list' for aisle order"
    except sqlite3.Error as exc:
        return f"LIST: (query error: {exc})"
    finally:
        con.close()


def _memory_block(data_dir: Path) -> str:
    mem = data_dir / "memory.md"
    head = f"MEMORY ({mem}):"
    if not mem.exists() or mem.stat().st_size == 0:
        return head + "\n  (empty — no durable preferences recorded yet)"
    text = mem.read_text(errors="replace").strip()
    return head + "\n" + "\n".join("  " + ln for ln in text.splitlines())


def _readiness(db: Path, profile_path: Path, profile_raw, unreadable):
    """THREE-VALUED fast proxy for selfcheck (D-g). ``(verdict, missing, unknown)`` with
    ``verdict`` one of ``READY`` / ``NOT-READY`` / ``UNKNOWN``: ``missing`` = user-state gaps
    (first-run); ``unknown`` = ENV faults (present-but-unreadable profile / corrupt db) — the
    triage reports and STOPS on those, never onboards (the hh00046 false-onboarding link)."""
    missing: list[str] = []
    unknown: list[str] = []
    db_state = _db_probe(db)
    if db_state == "absent":
        missing.append("db(file missing)")
    elif db_state == "unreadable":
        unknown.append("db(present but unreadable)")
    else:
        absent = [t for t in _DB_TABLES if t not in db_state]
        if absent:
            missing.append(f"db_tables={absent}")
    if profile_raw is unreadable:
        unknown.append("profile(present but unreadable)")
    elif not profile_raw:  # None / {} / [] → absent or empty
        missing.append("profile(file missing)" if not profile_path.exists()
                       else "profile(empty)")
    elif not isinstance(profile_raw, dict):
        # Present + parseable but the WRONG SHAPE (a list/scalar) — a malformed profile is an
        # env/authoring fault, not user state. UNKNOWN (never crash on `.get`, never onboard).
        unknown.append("profile(present but not a mapping)")
    else:
        unset = [f for f in _PROFILE_REQUIRED if profile_raw.get(f) in (None, "", [])]
        if unset:
            missing.append(f"profile_fields={unset}")
    verdict = "UNKNOWN" if unknown else ("NOT-READY" if missing else "READY")
    return verdict, missing, unknown


def main() -> int:
    data_dir = _data_dir()
    db = data_dir / "shopping.db"
    profile_path = data_dir / "profile.yaml"
    belt = _belt()
    profile_raw = belt.read_yaml(profile_path)
    profile = profile_raw if isinstance(profile_raw, dict) else None

    verdict, missing, unknown = _readiness(db, profile_path, profile_raw, belt.UNREADABLE)

    print(f"=== OtenyShopBotTalent preflight ({_BOT}) ===")
    if verdict == "READY":
        print("READY: yes")
    elif verdict == "UNKNOWN":
        # An ENVIRONMENT fault (a present-but-unreadable profile / a corrupt db), NOT a fresh
        # tenant. Report and STOP — never onboard/coach from an assumed first-run. No hint.
        print(f"UNKNOWN: env problem  ({'; '.join(unknown)})")
        print("  => environment fault, NOT first-run. Do NOT manage the list or run intake; "
              "report this and stop.")
    else:
        print(f"READY: no  (missing: {'; '.join(missing)})")
        print("  => setup incomplete: load references/first-run.md (declared scripts only); "
              "do NOT manage the list until READY.")
    print(_now_line(profile))
    print(_profile_line(profile))
    print(_list_line(db))
    print(_memory_block(data_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
