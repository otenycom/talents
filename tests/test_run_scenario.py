"""Tests for the deterministic scenario player (P1, run_scenario.py --backend mock).

Two concerns, kept separate:
  * the runner MACHINERY is content-agnostic — proven against a tiny synthetic bundle so
    the protocol is decoupled from any real Talent's behaviour;
  * flatbelly's SHIPPED scenarios pass — the reference Talent's data layer + the
    clone-from-prior-state in-box migration, all deterministic and offline.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

from _talents import CATALOG, SHARED, load

rs = load(SHARED / "run_scenario.py", "run_scenario")

FLATBELLY = CATALOG / "oteny-flatbelly-talent"
SCENARIOS = FLATBELLY / "tests" / "scenarios"


# --------------------------------------------------------------------------- #
# the runner machinery — content-agnostic (synthetic bundle)                   #
# --------------------------------------------------------------------------- #
def _synthetic_bundle(root: Path) -> Path:
    """A minimal, content-free Talent bundle: proves the runner tests the PROTOCOL, not
    any real Talent's behaviour (don't re-couple machinery to content)."""
    bundle = root / "oteny-sample-talent"
    (bundle / "scripts").mkdir(parents=True)
    (bundle / "tests" / "scenarios").mkdir(parents=True)
    (bundle / "agent-profile.yaml").write_text("bot: oteny-sample-talent\n")
    (bundle / "required_artifacts.yaml").write_text(
        "bot: oteny-sample-talent\n"
        "artifacts:\n"
        "  - kind: sqlite_db\n"
        "    path: ~/.hermes/data/oteny-sample-talent/sample.db\n"
        "    must_have_tables: [items]\n"
    )
    (bundle / "scripts" / "init.sql").write_text(
        "CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, name TEXT, qty INTEGER);\n"
    )
    return bundle


def _write(path: Path, body: str) -> Path:
    path.write_text(textwrap.dedent(body))
    return path


def test_runner_is_content_agnostic(tmp_path):
    bundle = _synthetic_bundle(tmp_path)
    scenario = _write(bundle / "tests" / "scenarios" / "add_item.yaml", """\
        bot: oteny-sample-talent
        seed:
          db: sample.db
        turns:
          - user: add 5 apples
            expect:
              tool_calls:
                - sql: "INSERT INTO items(name, qty) VALUES ('apples', 5)"
              state:
                - query: "SELECT qty FROM items WHERE name='apples'"
                  equals: 5
    """)
    rep = rs.run_scenario(scenario, "mock")
    assert rep["error"] is None, rep
    assert rep["failed"] == 0 and rep["passed"] == 2, rep


def test_broken_scenario_fails(tmp_path):
    bundle = _synthetic_bundle(tmp_path)
    scenario = _write(bundle / "tests" / "scenarios" / "broken.yaml", """\
        bot: oteny-sample-talent
        seed:
          db: sample.db
        turns:
          - user: add 5 apples
            expect:
              tool_calls:
                - sql: "INSERT INTO items(name, qty) VALUES ('apples', 5)"
              state:
                - query: "SELECT qty FROM items WHERE name='apples'"
                  equals: 999          # WRONG on purpose
    """)
    rep = rs.run_scenario(scenario, "mock")
    assert rep["failed"] >= 1, rep


def test_missing_declared_script_is_a_registration_failure(tmp_path):
    bundle = _synthetic_bundle(tmp_path)
    scenario = _write(bundle / "tests" / "scenarios" / "noscript.yaml", """\
        bot: oteny-sample-talent
        seed:
          db: sample.db
        turns:
          - user: run a tool
            expect:
              tool_calls:
                - script: scripts/does_not_exist.py
    """)
    rep = rs.run_scenario(scenario, "mock")
    assert rep["failed"] == 1, rep


def test_assert_hook_escape_hatch(tmp_path):
    bundle = _synthetic_bundle(tmp_path)
    (bundle / "scripts" / "checks.py").write_text(
        "def macros_present(ctx):\n"
        "    import sqlite3\n"
        "    con = sqlite3.connect(str(ctx['db']))\n"
        "    n = con.execute(\"SELECT COUNT(*) FROM items\").fetchone()[0]\n"
        "    con.close()\n"
        "    assert n == 1, f'expected 1 item, got {n}'\n"
    )
    scenario = _write(bundle / "tests" / "scenarios" / "hook.yaml", """\
        bot: oteny-sample-talent
        seed:
          db: sample.db
        turns:
          - user: add one
            expect:
              tool_calls:
                - sql: "INSERT INTO items(name, qty) VALUES ('x', 1)"
            assert: scripts/checks.py::macros_present
    """)
    rep = rs.run_scenario(scenario, "mock")
    assert rep["failed"] == 0 and rep["passed"] == 2, rep


def test_live_only_scenario_is_skipped(tmp_path):
    bundle = _synthetic_bundle(tmp_path)
    scenario = _write(bundle / "tests" / "scenarios" / "live.yaml", """\
        bot: oteny-sample-talent
        live_only: true
        turns: []
    """)
    rep = rs.run_scenario(scenario, "mock")
    assert rep["skipped"] is True and rep["failed"] == 0


def test_bot_mismatch_is_an_error(tmp_path):
    bundle = _synthetic_bundle(tmp_path)
    scenario = _write(bundle / "tests" / "scenarios" / "mismatch.yaml", """\
        bot: oteny-wrong-talent
        turns: []
    """)
    rep = rs.run_scenario(scenario, "mock")
    assert rep["error"] and "!=" in rep["error"], rep


def test_live_backend_not_yet_implemented(tmp_path):
    bundle = _synthetic_bundle(tmp_path)
    scenario = _write(bundle / "tests" / "scenarios" / "x.yaml",
                      "bot: oteny-sample-talent\nturns: []\n")
    rep = rs.run_scenario(scenario, "live")
    assert rep["failed"] == 1 and "live backend" in (rep["error"] or ""), rep


# --------------------------------------------------------------------------- #
# flatbelly — the reference Talent's shipped scenarios                          #
# --------------------------------------------------------------------------- #
def test_flatbelly_weight_log_scenario_passes():
    rep = rs.run_scenario(SCENARIOS / "weight_log.yaml", "mock")
    assert rep["error"] is None, rep
    assert rep["failed"] == 0, rep
    assert rep["passed"] >= 3            # selfcheck-ready + tool_call + state asserts
    assert rep["skipped_count"] >= 1     # the live-only reply


def test_flatbelly_macros_migration_reconciles_prior_state():
    rep = rs.run_scenario(SCENARIOS / "macros_migration.yaml", "mock")
    assert rep["error"] is None, rep
    assert rep["failed"] == 0, rep
    assert rep["passed"] >= 8, rep       # requires_migration + migrate + 6 state asserts


def test_migration_idempotent_within_one_box(tmp_path):
    # Apply the SAME migration twice against ONE box: detect-then-act keeps the second
    # apply a safe no-op (the row count and totals are unchanged).
    scenario = _write(tmp_path / "twice.yaml", """\
        bot: oteny-flatbelly-talent
        seed:
          sql: >-
            INSERT INTO meals(date, meal_type, food, calories, protein_g)
            VALUES ('2026-06-20', 'lunch', 'x', 100, 10)
        turns:
          - user: migrate twice
            expect:
              tool_calls:
                - migrate: 0002_food_macros
                - migrate: 0002_food_macros
              state:
                - query: "SELECT protein_g FROM food_macros WHERE date='2026-06-20'"
                  equals: 10
                - query: "SELECT COUNT(*) FROM food_macros"
                  equals: 1
    """)
    rep = rs.run_scenario(scenario, "mock", bundle_override=str(FLATBELLY))
    assert rep["failed"] == 0, rep


def test_all_flatbelly_scenarios_pass_via_cli():
    # The literal acceptance criterion: `run_scenario.py tests/scenarios/*.yaml` exits 0.
    paths = sorted(str(p) for p in SCENARIOS.glob("*.yaml"))
    assert paths, "no shipped flatbelly scenarios found"
    assert rs.main(paths) == 0
