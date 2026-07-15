#!/usr/bin/env python3
"""preflight — the ONE per-turn context call for OtenyFlatBellyTalent.

The triage used to spend ~5 separate tool calls before it could even classify a
message: the first-run guard, a clock check, a "DB reachable?" probe, a "what's
logged today?" query, and a `cat memory.md`. On a weak runtime model that fan-out
is most of a slow turn. This script answers all of them in **one** read-only call:

    python3 ~/.hermes/skills/talents/oteny-flatbelly-talent/scripts/preflight.py

It prints, in a compact parseable block:
  * READY  — a THREE-VALUED proxy for "can I coach now?": READY (db + tables + profile
             fields), NOT-READY (a user-state gap → load references/first-run.md), or
             UNKNOWN (an ENVIRONMENT fault — a present-but-unreadable profile / corrupt db →
             report it and STOP; NEVER onboard). selfcheck.py stays the detailed authority.
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
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - py>=3.9 on Hermes
    ZoneInfo = None


def _belt():
    """The shared readiness belt (``selfcheck.read_yaml`` + ``UNREADABLE``), loaded from the
    sibling ``selfcheck.py`` by path — the ONE stdlib-first YAML reader every readiness script
    shares, so a cold tenant whose system python3 lacks PyYAML still PARSES profile.yaml (the
    hh00046 incident) instead of mis-reading "can't parse" as "not set up → onboard". Loaded
    by path (not a plain import) so it resolves both when run as a file and under the tests'
    importlib loader."""
    import importlib.util

    p = Path(__file__).resolve().parent / "selfcheck.py"
    spec = importlib.util.spec_from_file_location("oteny_readiness_belt", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

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


def _migrations_line() -> str:
    """Pending in-box migrations, so the triage reconciles the db SHAPE before it plans
    (even on a READY box). Imports the sibling migrate.py by path; never raises — a bundle
    without migrations.yaml / migrate.py just reports none."""
    try:
        import importlib.util

        scripts = Path(__file__).resolve().parent
        manifest = scripts.parent / "migrations.yaml"
        migrate_py = scripts / "migrate.py"
        if not manifest.exists() or not migrate_py.exists():
            return "MIGRATIONS: none"
        spec = importlib.util.spec_from_file_location("flatbelly_migrate", migrate_py)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.status_line(manifest)
    except Exception:
        return "MIGRATIONS: none"


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


def _today_block(db: Path) -> str:
    if not db.exists():
        return "TODAY: (no database yet)"
    out = ["TODAY logged:"]
    con = sqlite3.connect(str(db))
    try:
        try:
            have = {r[0] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
        except sqlite3.Error as exc:
            # A corrupt/locked db must never make the terminal call look failed (always exit 0);
            # readiness already reports it as UNKNOWN above.
            return f"TODAY: (database unreadable: {exc})"
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


def _readiness(db: Path, profile_path: Path, profile_raw, unreadable):
    """THREE-VALUED fast proxy for selfcheck (D-g). Returns ``(verdict, missing, unknown)``
    with ``verdict`` one of ``READY`` / ``NOT-READY`` / ``UNKNOWN``:

      * ``missing`` — user-state gaps (no db/tables/profile/fields) → genuine first-run;
      * ``unknown`` — ENVIRONMENT faults (a present-but-unreadable profile / a corrupt db) →
        the triage must report and STOP, NEVER onboard (the hh00046 false-onboarding link).
    """
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
        # Present but unparseable — an env fault, NOT "no profile yet". UNKNOWN, never
        # NOT-READY: re-running the intake would overwrite a real (unreadable) profile.
        unknown.append("profile(present but unreadable)")
    elif not profile_raw:  # None / {} / [] → absent or empty
        missing.append("profile(file missing)" if not profile_path.exists()
                       else "profile(empty)")
    elif not isinstance(profile_raw, dict):
        # Present + parseable but the WRONG SHAPE (a list/scalar) — a malformed profile is an
        # env/authoring fault, not user state. UNKNOWN (never crash on `.get`, never onboard).
        unknown.append("profile(present but not a mapping)")
    else:
        unset = [f for f in _PROFILE_REQUIRED
                 if profile_raw.get(f) in (None, "", [], 0)]
        if unset:
            missing.append(f"profile_fields={unset}")
    verdict = "UNKNOWN" if unknown else ("NOT-READY" if missing else "READY")
    return verdict, missing, unknown


def main() -> int:
    data_dir = _data_dir()
    db = data_dir / "food.db"
    profile_path = data_dir / "profile.yaml"
    belt = _belt()
    profile_raw = belt.read_yaml(profile_path)
    # For the display helpers a non-dict (None / UNREADABLE) collapses to "no profile".
    profile = profile_raw if isinstance(profile_raw, dict) else None

    verdict, missing, unknown = _readiness(db, profile_path, profile_raw, belt.UNREADABLE)

    print(f"=== OtenyFlatBellyTalent preflight ({_BOT}) ===")
    if verdict == "READY":
        print("READY: yes")
    elif verdict == "UNKNOWN":
        # An ENVIRONMENT fault (a present-but-unreadable profile / a corrupt db), NOT a fresh
        # tenant. Report and STOP — never onboard/coach from an assumed first-run (the exact
        # link that turned the hh00046 env failure into a false welcome). No onboarding hint.
        print(f"UNKNOWN: env problem  ({'; '.join(unknown)})")
        print("  => environment fault, NOT first-run. Do NOT coach or run intake; "
              "report this and stop.")
    else:
        print(f"READY: no  (missing: {'; '.join(missing)})")
        print("  => setup incomplete: load references/first-run.md (declared scripts only); "
              "do NOT coach until READY.")
    print(_migrations_line())
    print(_now_line(profile))
    print(_profile_line(profile))
    print(_today_block(db))
    print(_memory_block(data_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
