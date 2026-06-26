#!/usr/bin/env python3
"""preflight — the ONE per-turn context call for OtenyFlatBellyTalent.

The triage used to spend ~5 separate tool calls before it could even classify a
message: the first-run guard, a clock check, a "DB reachable?" probe, a "what's
logged today?" query, and a `cat memory.md`. On a weak runtime model that fan-out
is most of a slow turn. This script answers all of them in **one** read-only call:

    python3 ~/.hermes/skills/talents/oteny-flatbelly-talent/scripts/preflight.py

It prints, in a compact parseable block:
  * READY  — a fast proxy for "can I coach now?" (db + tables + profile fields).
             When `no`, the triage runs the full ``selfcheck.py`` for the detailed
             missing list, then onboarding. (selfcheck stays the authority; this is
             just the cheap fast-path so a normal turn never pays for it.)
  * NOW    — local time (hard rule ③: time-of-day before framing a day "done").
  * PROFILE— the few fields the coach needs every turn (targets, height, language)
             so it never has to separately read profile.yaml.
  * TODAY  — what is already logged today, per table (no double-logging; grounding).
  * MEMORY — the per-bot durable preferences (not auto-loaded by Hermes).

Pure / read-only / side-effect-free; safe to run on every turn. Exit code is
always 0 (a non-zero would make the LLM's terminal call look failed) — readiness
is in the output, not the exit code. Paths resolve through the same env overrides
as selfcheck.py so a relocated overlay / tests stay hermetic.
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

_BOT = "oteny-flatbelly-talent"
_DB_TABLES = ["meals", "weight", "daily_metrics", "workouts", "waist"]
_PROFILE_REQUIRED = [
    "goal_weight_kg", "start_weight_kg", "height_cm", "age", "sex",
    "language", "timezone",
]
# The fields the coach wants in hand every turn (shown when present).
_PROFILE_SHOW = [
    "language", "timezone", "protein_target_g", "leucine_threshold_g",
    "height_cm", "goal_weight_kg", "start_weight_kg", "age", "sex", "reminders",
]
# Which tables to summarise for "today", and the columns that read well compact.
_TODAY = {
    "meals": "meal_type, food, calories, protein_g, leucine_g",
    "weight": "weight_kg, period, notes",
    "daily_metrics": "steps, sleep_consistency_score, sleep_hours, active_kcal",
    "workouts": "workout_type, duration_minutes, muscle_groups",
    "waist": "waist_cm, height_cm, ROUND(whtr,3) AS whtr",
}


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


def _today_block(db: Path) -> str:
    if not db.exists():
        return "TODAY: (no database yet)"
    out = ["TODAY logged:"]
    con = sqlite3.connect(str(db))
    try:
        have = {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        for table, cols in _TODAY.items():
            if table not in have:
                continue
            try:
                rows = con.execute(
                    f"SELECT {cols} FROM {table} WHERE date = date('now') "
                    f"ORDER BY id"
                ).fetchall()
            except sqlite3.Error as exc:
                out.append(f"  {table}: (query error: {exc})")
                continue
            if not rows:
                out.append(f"  {table}: (none)")
            else:
                for r in rows:
                    out.append(f"  {table}: " + " · ".join(
                        "" if v is None else str(v) for v in r))
    finally:
        con.close()
    return "\n".join(out)


def _memory_block(data_dir: Path) -> str:
    mem = data_dir / "memory.md"
    head = f"MEMORY ({mem}):"
    if not mem.exists() or mem.stat().st_size == 0:
        return head + "\n  (empty — no durable preferences recorded yet)"
    text = mem.read_text(errors="replace").strip()
    return head + "\n" + "\n".join("  " + ln for ln in text.splitlines())


def _readiness(db: Path, profile_path: Path, profile: dict | None) -> tuple[bool, list[str]]:
    """Fast proxy for selfcheck: db+tables present and required profile fields set."""
    missing: list[str] = []
    tables = _db_tables(db)
    if not db.exists():
        missing.append("db(file missing)")
    else:
        absent = [t for t in _DB_TABLES if t not in tables]
        if absent:
            missing.append(f"db_tables={absent}")
    if profile is None:
        # Distinguish "no profile yet" (genuine first-run) from "exists but I
        # couldn't parse it" (e.g. PyYAML absent / malformed) so the triage's
        # remediation isn't misled into re-running the intake on a parse blip.
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
    db = data_dir / "food.db"
    profile_path = data_dir / "profile.yaml"
    profile = _load_yaml(profile_path)

    ready, missing = _readiness(db, profile_path, profile)

    print(f"=== OtenyFlatBellyTalent preflight ({_BOT}) ===")
    if ready:
        print("READY: yes")
    else:
        print(f"READY: no  (missing: {'; '.join(missing)})")
        print("  => run selfcheck.py for the full list, then onboarding; "
              "do NOT coach until READY.")
    print(_now_line(profile))
    print(_profile_line(profile))
    print(_today_block(db))
    print(_memory_block(data_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
