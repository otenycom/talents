"""Unit tests for the FlatBelly weekly-dashboard render script (generate.py).

generate.py is the one dashboard script pinned to a PRODUCTION cron (``OtenyFlatBellyTalent
weekly dashboard``) yet it shipped with zero tests — the riskiest script with the weakest
coverage (plan §8a). This covers:

  (a) the matplotlib-absent DEGRADE path — the safety net added when the platform matplotlib
      provisioning landed (plan §8b): a box without matplotlib must exit 2, not crash; and
  (b) a render smoke when matplotlib IS present (the real weekly-cron output).

The degrade test runs stdlib-only (no matplotlib), which is the whole point — before the
import guard, this module could not even be imported without matplotlib installed.
"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta

import pytest

from _talents import CATALOG, load

GEN = CATALOG / "oteny-flatbelly-talent" / "weight-progress-dashboard" / "scripts" / "generate.py"


def _seed(tmp_path):
    """A minimal food.db (≥2 morning weights) + a profile with a goal — enough for a render."""
    db = tmp_path / "food.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE weight(id INTEGER PRIMARY KEY, date TEXT, weight_kg REAL,"
                " period TEXT, notes TEXT)")
    base = date.today() - timedelta(days=14)
    for i in range(6):
        con.execute("INSERT INTO weight (date, weight_kg, period) VALUES (?, ?, 'morning')",
                    ((base + timedelta(days=i * 2)).isoformat(), 100.0 - i * 0.4))
    con.commit()
    con.close()
    prof = tmp_path / "profile.yaml"
    prof.write_text("goal_weight_kg: 85\n")
    return db, prof


def test_dashboard_degrades_without_matplotlib(monkeypatch):
    """Safety net (plan §8b): plt is None (matplotlib not provisioned) → main() returns 2, no
    crash. The weekly cron then registers FAILED (ops sees a dead feature) rather than raising
    a raw ImportError. Runs stdlib-only."""
    gen = load(GEN, "fb_generate_degrade")
    monkeypatch.setattr(gen, "plt", None)
    assert gen.main([]) == 2


def test_dashboard_renders(tmp_path):
    """When matplotlib IS present, the weekly cron actually produces a PNG (generate.py's
    first render coverage). Skipped where matplotlib is absent — the platform provisions it
    on the tenant; this asserts the render path itself is sound."""
    pytest.importorskip("matplotlib")
    gen = load(GEN, "fb_generate_render")
    db, prof = _seed(tmp_path)
    out = tmp_path / "out"
    rc = gen.main(["--db", str(db), "--profile", str(prof), "--out-dir", str(out)])
    assert rc == 0
    pngs = list(out.glob("oteny_belly_progress_*.png"))
    assert len(pngs) == 1 and pngs[0].stat().st_size > 0
