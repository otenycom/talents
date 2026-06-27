#!/usr/bin/env python3
"""preflight — the ONE per-turn context call for OtenyShopBotTalent.

Collapses the per-turn preamble into a single read-only call so a normal turn never
pays for a fan-out of probes (first-run guard, clock, "db reachable?", "what's on the
list?", memory). Run it first on every turn:

    python3 ~/.hermes/skills/talents/oteny-shopbot-talent/scripts/preflight.py

It prints, in a compact parseable block:
  * READY  — fast proxy for "can I manage the list now?" (db + tables + profile fields).
             When `no`, run the full selfcheck.py for the detailed missing list, then
             first-run. (selfcheck stays the authority; this is the cheap fast-path.)
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
    import yaml
except ImportError:  # pragma: no cover - PyYAML is always present on Hermes
    yaml = None

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - py>=3.9 on Hermes
    ZoneInfo = None

_BOT = "oteny-shopbot-talent"
_DB_TABLES = ["stores", "sections", "items", "item_sections"]
_PROFILE_REQUIRED = ["default_store", "language", "timezone"]
_PROFILE_SHOW = ["name", "default_store", "household", "language", "timezone", "reminders"]


def _home() -> Path:
    return Path(os.environ.get("HH_HOME") or Path.home())


def _hermes_home() -> Path:
    env = os.environ.get("HH_HERMES_HOME") or os.environ.get("HERMES_HOME")
    return Path(env) if env else _home() / ".hermes"


def _data_dir() -> Path:
    return _hermes_home() / "data" / _BOT


def _load_yaml(path: Path):
    if yaml is None or not path.exists():
        return None
    try:
        with path.open() as fh:
            return yaml.safe_load(fh)
    except Exception:
        return None


def _db_tables(db: Path) -> set[str]:
    if not db.exists():
        return set()
    con = sqlite3.connect(str(db))
    try:
        return {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    except sqlite3.Error:
        return set()
    finally:
        con.close()


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
            "SELECT COUNT(*) FROM items WHERE status='active'").fetchone()[0]
        rows = con.execute(
            "SELECT COALESCE(st.name,'(no store)') AS store, COUNT(*) AS n "
            "FROM items i LEFT JOIN stores st ON st.id = i.store_id "
            "WHERE i.status='active' GROUP BY store ORDER BY n DESC"
        ).fetchall()
        by_store = ", ".join(f"{r[0]}: {r[1]}" for r in rows) or "—"
        return f"LIST: {total} active ({by_store}) — use list_view.py for aisle order"
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


def _readiness(db: Path, profile_path: Path,
               profile: dict | None) -> tuple[bool, list[str]]:
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
        unset = [f for f in _PROFILE_REQUIRED if profile.get(f) in (None, "", [])]
        if unset:
            missing.append(f"profile_fields={unset}")
    return (not missing), missing


def main() -> int:
    data_dir = _data_dir()
    db = data_dir / "shopping.db"
    profile_path = data_dir / "profile.yaml"
    profile = _load_yaml(profile_path)

    ready, missing = _readiness(db, profile_path, profile)

    print(f"=== OtenyShopBotTalent preflight ({_BOT}) ===")
    if ready:
        print("READY: yes")
    else:
        print(f"READY: no  (missing: {'; '.join(missing)})")
        print("  => run selfcheck.py for the full list, then first-run; "
              "do NOT manage the list until READY.")
    print(_now_line(profile))
    print(_profile_line(profile))
    print(_list_line(db))
    print(_memory_block(data_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
