"""selfcheck must NEVER hard-fail on a cold tenant whose system python3 lacks PyYAML.

Regression for the prod grind (measured 2026-07-14): `selfcheck.py` raised
``RuntimeError("PyYAML is required …")`` — violating its own "always exit 0"
contract — so the model looped on ``uv pip install pyyaml`` (13 tenants /
64 sessions). The fix vendors a pure-stdlib YAML reader as a FALLBACK, engaged
only when ``import yaml`` fails. These tests pin:

  1. the fallback reads our manifests + profile.yaml byte-identically to PyYAML;
  2. with PyYAML absent, selfcheck still returns a correct verdict and exits 0,
     with no traceback and no "PyYAML is required" message.
"""
from __future__ import annotations

import io
import json
import sqlite3
import contextlib
from pathlib import Path

import pytest
import yaml

from _talents import CATALOG, SHARED, load

# The ONLY files selfcheck's _load_yaml reads on a tenant: the manifest + profile.yaml.
# (agent-profile.yaml is read by the deployer, where PyYAML is always present, and uses
# block scalars the minimal reader deliberately does not implement.)
READ_FILES = sorted(CATALOG.glob("*/required_artifacts.yaml")) + \
    sorted(CATALOG.glob("*/profile/profile.yaml.template"))

# Realistic first-run profile.yaml outputs (colons-in-quotes, unicode, flow maps/lists).
BATTERY = [
    'name: "Ries Vriend"\nsex: "m"\nage: 44\nheight_cm: 183\n'
    'start_weight_kg: 92.5\ngoal_weight_kg: 82.0\nlanguage: "en"\n'
    'timezone: "Europe/Amsterdam"\nreminders:\n  morning: "08:00"\n'
    '  evening: "20:00"\nmilestones: [{label: "liver check", weight_kg: 97.5}]\n'
    'terms_accepted: true\nshorthands: {oats: "80g oats + 30g whey"}\n',
    'name: "José: the tester"\nnote: "see http://example.com/x#frag here"\n'
    'city: "São Paulo"\nempty: ""\nzero: 0\nflt: 0.0\nflag: false\n'
    'listy: []\nmapy: {}\n',
    'home_city: Amsterdam\nhome_timezone: Europe/Amsterdam\n'
    'language: en\ndefault_currency: EUR\n',
]


@pytest.fixture(scope="module")
def sc():
    return load(SHARED / "selfcheck.py", "sc_stdlib")


@pytest.mark.parametrize("path", READ_FILES, ids=lambda p: str(p.relative_to(CATALOG)))
def test_fallback_reader_matches_pyyaml(sc, path):
    text = path.read_text()
    assert sc._minimal_yaml_load(text) == yaml.safe_load(text)


@pytest.mark.parametrize("text", BATTERY, ids=range(len(BATTERY)))
def test_fallback_reader_matches_pyyaml_battery(sc, text):
    assert sc._minimal_yaml_load(text) == yaml.safe_load(text)


def test_load_yaml_uses_fallback_when_pyyaml_absent(sc, monkeypatch, tmp_path):
    """_load_yaml must not touch PyYAML when it is None — the stdlib path reads the file."""
    monkeypatch.setattr(sc, "yaml", None)
    p = tmp_path / "profile.yaml"
    p.write_text('language: "en"\nage: 0\ngoal_weight_kg: 82.0\n')
    assert sc._load_yaml(p) == {"language": "en", "age": 0, "goal_weight_kg": 82.0}


def test_unparseable_file_degrades_to_none_never_raises(sc, monkeypatch, tmp_path):
    """A construct the minimal reader can't handle must degrade to None, not a traceback."""
    monkeypatch.setattr(sc, "yaml", None)
    p = tmp_path / "profile.yaml"
    p.write_text("description: >\n  a folded block scalar\n  spanning two lines\n")
    assert sc._load_yaml(p) is None  # caught → None, no exception


@pytest.mark.parametrize(
    "manifest", sorted(CATALOG.glob("*/required_artifacts.yaml")),
    ids=lambda p: p.parent.name)
def test_cold_tenant_selfcheck_runs_clean(sc, manifest, monkeypatch, tmp_path):
    """With PyYAML absent, run() on a bare sandbox → NOT-READY, and it RAN (no raise)."""
    monkeypatch.setattr(sc, "yaml", None)
    monkeypatch.setenv("HH_HOME", str(tmp_path))
    monkeypatch.setenv("HH_HERMES_HOME", str(tmp_path / ".hermes"))
    (tmp_path / ".hermes").mkdir(parents=True)
    rep = sc.run(manifest)
    assert rep["ready"] is False
    assert rep["bot"] == manifest.parent.name


def test_cold_tenant_main_exits_zero_without_traceback(sc, monkeypatch, tmp_path):
    """The whole point: the terminal call never LOOKS like a failure on a cold box."""
    monkeypatch.setattr(sc, "yaml", None)
    monkeypatch.setenv("HH_HOME", str(tmp_path))
    monkeypatch.setenv("HH_HERMES_HOME", str(tmp_path / ".hermes"))
    (tmp_path / ".hermes").mkdir(parents=True)
    manifest = CATALOG / "oteny-flatbelly-talent" / "required_artifacts.yaml"
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = sc.main(["--manifest", str(manifest)])
    out = buf.getvalue()
    assert rc == 0
    assert "NOT-READY" in out
    assert "Traceback" not in out
    assert "PyYAML is required" not in out  # the old hard-fail message is gone


def test_cold_tenant_ready_when_artifacts_present(sc, monkeypatch, tmp_path):
    """A fully set-up FlatBelly tenant still verifies READY with PyYAML absent."""
    monkeypatch.setattr(sc, "yaml", None)
    hermes = tmp_path / ".hermes"
    data = hermes / "data" / "oteny-flatbelly-talent"
    data.mkdir(parents=True)
    (hermes / "memories").mkdir(parents=True)
    con = sqlite3.connect(data / "food.db")
    for t in ("meals", "weight", "daily_metrics", "workouts", "waist"):
        con.execute(f"CREATE TABLE {t}(id INTEGER)")
    con.commit()
    con.close()
    (data / "profile.yaml").write_text(
        'goal_weight_kg: 82.0\nstart_weight_kg: 92.5\nheight_cm: 183\n'
        'age: 44\nsex: "m"\nlanguage: "en"\ntimezone: "Europe/Amsterdam"\n')
    (hermes / "memories" / "USER.md").write_text("# identity\nRies\n")
    (data / "memory.md").write_text("domain\n")
    (hermes / "cron").mkdir(parents=True)
    (hermes / "cron" / "jobs.json").write_text(json.dumps({"jobs": [
        {"name": "OtenyFlatBellyTalent daily morning log"},
        {"name": "OtenyFlatBellyTalent daily evening log"},
        {"name": "OtenyFlatBellyTalent weekly dashboard"}]}))
    tool = (hermes / "skills" / "talents" / "oteny-flatbelly-talent" /
            "weight-progress-dashboard" / "scripts")
    tool.mkdir(parents=True)
    (tool / "generate.py").write_text("# dashboard\n")
    monkeypatch.setenv("HH_HOME", str(tmp_path))
    monkeypatch.setenv("HH_HERMES_HOME", str(hermes))
    rep = sc.run(CATALOG / "oteny-flatbelly-talent" / "required_artifacts.yaml")
    assert rep["ready"] is True, rep["missing"]
