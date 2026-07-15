"""Unit tests for OtenyFlatBellyTalent's per-turn preflight probe (latency rework).

`preflight.py` collapses the old multi-call triage preamble (setup guard + clock +
DB-reachable + today's rows + `cat memory.md`) into ONE read-only call — the change
that took a cold meal-entry turn from ~67 model calls to ~5. These tests pin that
contract: READY only when db+tables+profile are present, and the single block carries
the clock, profile targets, today's rows, and the durable memory.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from _talents import CATALOG, load, sandbox_env

pf = load(CATALOG / "oteny-flatbelly-talent" / "scripts" / "preflight.py", "pf_preflight")


def _force_belt_without_pyyaml(monkeypatch):
    """Make preflight's shared belt behave as if PyYAML is absent (the cold-container case,
    hh00046): a fresh selfcheck module with ``yaml=None`` wired in as preflight's ``_belt``."""
    belt = load(CATALOG / "oteny-flatbelly-talent" / "scripts" / "selfcheck.py",
                "pf_belt_nopyyaml")
    belt.yaml = None
    belt._belt_emitted = False
    monkeypatch.setattr(pf, "_belt", lambda: belt)

_TABLES = ["meals", "weight", "daily_metrics", "workouts", "waist"]
_PROFILE = (
    "goal_weight_kg: 85\nstart_weight_kg: 100\nheight_cm: 178\nage: 47\n"
    "sex: male\nlanguage: nl\ntimezone: Europe/Amsterdam\n"
    "protein_target_g: 185\nleucine_threshold_g: 2.5\n"
)


def _data_dir(root: Path) -> Path:
    d = root / ".hermes" / "data" / "oteny-flatbelly-talent"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _make_db(path: Path, *, tables=_TABLES, today_meal=False):
    ddl = {
        "meals": "CREATE TABLE meals(id INTEGER PRIMARY KEY, date TEXT, meal_type TEXT,"
                 " food TEXT, calories INT, protein_g REAL, leucine_g REAL)",
        "weight": "CREATE TABLE weight(id INTEGER PRIMARY KEY, date TEXT, weight_kg REAL,"
                  " period TEXT, notes TEXT)",
        "daily_metrics": "CREATE TABLE daily_metrics(id INTEGER PRIMARY KEY, date TEXT,"
                         " steps INT, sleep_consistency_score INT, sleep_hours REAL, active_kcal INT)",
        "workouts": "CREATE TABLE workouts(id INTEGER PRIMARY KEY, date TEXT, workout_type TEXT,"
                    " duration_minutes INT, muscle_groups TEXT)",
        "waist": "CREATE TABLE waist(id INTEGER PRIMARY KEY, date TEXT, waist_cm REAL,"
                 " height_cm REAL, whtr REAL)",
    }
    con = sqlite3.connect(path)
    for t in tables:
        con.execute(ddl[t])
    if today_meal:
        con.execute("INSERT INTO meals(date, meal_type, food, calories, protein_g, leucine_g)"
                    " VALUES (date('now'),'breakfast','3 eggs',250,18,1.57)")
    con.commit()
    con.close()


def test_ready_surfaces_clock_profile_today_memory(tmp_path, monkeypatch, capsys):
    sandbox_env(monkeypatch, tmp_path)
    d = _data_dir(tmp_path)
    _make_db(d / "food.db", today_meal=True)
    (d / "profile.yaml").write_text(_PROFILE)
    (d / "memory.md").write_text("- prefers Dutch food names\n")
    assert pf.main() == 0
    out = capsys.readouterr().out
    assert "READY: yes" in out
    assert "tz=Europe/Amsterdam" in out          # clock with profile tz (hard rule 3)
    assert "protein_target_g=185" in out          # targets in hand, no separate read
    assert "language=nl" in out
    assert "3 eggs" in out                          # today's row surfaced
    assert "prefers Dutch food names" in out        # durable memory surfaced


def test_not_ready_without_profile(tmp_path, monkeypatch, capsys):
    sandbox_env(monkeypatch, tmp_path)
    d = _data_dir(tmp_path)
    _make_db(d / "food.db")
    assert pf.main() == 0
    out = capsys.readouterr().out
    assert "READY: no" in out
    assert "profile(file missing)" in out


def test_not_ready_when_tables_missing(tmp_path, monkeypatch, capsys):
    sandbox_env(monkeypatch, tmp_path)
    d = _data_dir(tmp_path)
    _make_db(d / "food.db", tables=["meals"])        # 4 required tables absent
    (d / "profile.yaml").write_text(_PROFILE)
    assert pf.main() == 0
    out = capsys.readouterr().out
    assert "READY: no" in out
    assert "db_tables=" in out


def test_empty_box_is_robust(tmp_path, monkeypatch, capsys):
    sandbox_env(monkeypatch, tmp_path)                # nothing created
    assert pf.main() == 0                              # never raises / never non-zero
    out = capsys.readouterr().out
    assert "READY: no" in out
    assert "db(file missing)" in out


# --------------------------------------------------------------------------- #
# Readiness contract v2 (D-g): the stdlib belt + three-valued READY/NOT-READY/ #
# UNKNOWN, and the removal of the "…then onboarding" prime (the hh00046 fix).  #
# --------------------------------------------------------------------------- #

def test_ready_with_pyyaml_absent_uses_stdlib_belt(tmp_path, monkeypatch, capsys):
    """A1: with NO PyYAML in system python3, preflight still parses a complete profile via
    the shared belt and prints READY: yes — never NOT-READY on the parse (the incident)."""
    sandbox_env(monkeypatch, tmp_path)
    d = _data_dir(tmp_path)
    _make_db(d / "food.db")
    (d / "profile.yaml").write_text(_PROFILE)
    _force_belt_without_pyyaml(monkeypatch)
    assert pf.main() == 0
    out = capsys.readouterr().out
    assert "READY: yes" in out


def test_unreadable_profile_is_unknown_never_onboards(tmp_path, monkeypatch, capsys):
    """A1: a present-but-unparseable profile is an ENV fault → UNKNOWN, never NOT-READY, and
    the output carries NO onboarding/first-run hint (the false-onboarding link)."""
    sandbox_env(monkeypatch, tmp_path)
    d = _data_dir(tmp_path)
    _make_db(d / "food.db")
    # A folded block scalar: PyYAML parses it, but the stdlib belt rejects it → UNREADABLE
    # once PyYAML is forced absent (exactly the cold-box shape).
    (d / "profile.yaml").write_text(
        "desc: >\n  a folded block scalar\n  the stdlib belt won't parse\n")
    _force_belt_without_pyyaml(monkeypatch)
    assert pf.main() == 0
    out = capsys.readouterr().out
    assert "UNKNOWN" in out
    assert "READY: no" not in out              # never the NOT-READY (first-run) verdict
    assert "onboard" not in out.lower()        # no onboarding prime on an env fault
    assert "report this and stop" in out.lower()   # the sanctioned UNKNOWN guidance
    assert "run intake" not in out.lower() or "do not" in out.lower()  # never steer to intake


def test_corrupt_db_is_unknown_and_exits_zero(tmp_path, monkeypatch, capsys):
    """A corrupt db is an env fault → UNKNOWN, and preflight still exits 0 (never a crash
    that makes the terminal call look failed)."""
    sandbox_env(monkeypatch, tmp_path)
    d = _data_dir(tmp_path)
    (d / "food.db").write_bytes(b"this is not a sqlite database at all")
    (d / "profile.yaml").write_text(_PROFILE)
    assert pf.main() == 0
    out = capsys.readouterr().out
    assert "UNKNOWN" in out


def test_non_dict_profile_is_unknown_not_crash(tmp_path, monkeypatch, capsys):
    """A valid-YAML but NON-MAPPING profile (a list/scalar) is a shape fault → UNKNOWN + exit 0,
    never an AttributeError on `profile.get` (the always-exit-0 contract)."""
    sandbox_env(monkeypatch, tmp_path)
    d = _data_dir(tmp_path)
    _make_db(d / "food.db")
    (d / "profile.yaml").write_text("- just\n- a list\n")   # valid YAML, wrong shape
    assert pf.main() == 0                                    # never crashes
    out = capsys.readouterr().out
    assert "UNKNOWN" in out
    assert "not a mapping" in out


def test_not_ready_has_no_onboarding_prime(tmp_path, monkeypatch, capsys):
    """D-g: the '…then onboarding' prime is removed — a genuine NOT-READY (first-run) points
    to the declared setup file, never the word 'onboarding'."""
    sandbox_env(monkeypatch, tmp_path)
    d = _data_dir(tmp_path)
    _make_db(d / "food.db")                    # db ok, profile absent → NOT-READY
    assert pf.main() == 0
    out = capsys.readouterr().out
    assert "READY: no" in out
    assert "onboarding" not in out.lower()
