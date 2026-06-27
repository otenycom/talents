"""P4 — the in-box neutralize runner + the fail-closed boot gate.

A clone of a real tenant's state must be DE-FANGED (outbound crons disabled, seams
repointed) before it serves a turn. ``neutralize.py`` runs the declared deterministic
steps control-plane-side; ``check_neutralize.py`` refuses the gateway start unless the
data-plane marker shows every step applied (fail-closed). These tests prove:

  * the runner applies sql/crons steps idempotently + records the marker;
  * the gate is fail-closed (NOT-READY when the marker is missing or any step pending);
  * the shipped per-bundle copies are byte-identical to the canonical (drift test);
  * flatbelly's neutralize.yaml disarms its three outbound DM crons.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest
import yaml

from _talents import CATALOG, SHARED, load, sandbox_env

FLATBELLY = CATALOG / "oteny-flatbelly-talent"
STOCK = CATALOG / "oteny-stock-talent"
SHOPBOT = CATALOG / "oteny-shopbot-talent"
TRAVEL = CATALOG / "oteny-travel-talent"

neu = load(SHARED / "neutralize.py", "neu_canon")
gate = load(SHARED / "check_neutralize.py", "gate_canon")


def _sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# --------------------------------------------------------------------------- #
# drift — every shipped copy is byte-identical to the canonical                #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("bundle", [FLATBELLY, STOCK, SHOPBOT, TRAVEL])
def test_shipped_neutralize_scripts_match_canonical(bundle):
    for name in ("neutralize.py", "check_neutralize.py"):
        assert _sha(bundle / "scripts" / name) == _sha(SHARED / name), f"{bundle.name}/{name} drift"


# --------------------------------------------------------------------------- #
# the runner — deterministic steps + idempotent marker                         #
# --------------------------------------------------------------------------- #
def _manifest(tmp_path: Path, steps: list[dict], *, db="food.db", bot="oteny-flatbelly-talent"):
    p = tmp_path / "neutralize.yaml"
    p.write_text(yaml.safe_dump({"bot": bot, "db": db, "steps": steps}, sort_keys=False))
    return p


def _seed_jobs(root: Path, bot: str, names: list[str]):
    jp = root / ".hermes" / "cron" / "jobs.json"
    jp.parent.mkdir(parents=True, exist_ok=True)
    jp.write_text(json.dumps({"jobs": [{"name": n, "enabled": True} for n in names]}, indent=2))
    return jp


def test_crons_step_disables_named_jobs(tmp_path, monkeypatch):
    sandbox_env(monkeypatch, tmp_path)
    jp = _seed_jobs(tmp_path, "oteny-flatbelly-talent",
                    ["daily morning log", "weekly dashboard", "unrelated keepalive"])
    man = _manifest(tmp_path, [{"id": "0001_crons", "kind": "crons",
                                "crons": {"disable": ["daily morning log", "weekly dashboard"]}}])
    rc = neu.main(["--manifest", str(man), "--all"])
    assert rc == 0
    jobs = {j["name"]: j for j in json.loads(jp.read_text())["jobs"]}
    assert jobs["daily morning log"]["enabled"] is False
    assert jobs["weekly dashboard"]["enabled"] is False
    assert jobs["unrelated keepalive"]["enabled"] is True       # only named jobs disarmed
    assert neu.all_applied(man) is True                          # marker recorded


def test_sql_step_runs_against_talent_db(tmp_path, monkeypatch):
    sandbox_env(monkeypatch, tmp_path)
    db = tmp_path / ".hermes" / "data" / "oteny-flatbelly-talent" / "food.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db)
    con.executescript("CREATE TABLE seam(url TEXT); INSERT INTO seam VALUES ('https://prod/json/2');")
    con.commit(); con.close()
    man = _manifest(tmp_path, [{"id": "0001_seam", "kind": "sql",
                                "sql": "UPDATE seam SET url='https://staging/json/2';"}])
    assert neu.main(["--manifest", str(man), "--all"]) == 0
    con = sqlite3.connect(db)
    assert con.execute("SELECT url FROM seam").fetchone()[0] == "https://staging/json/2"
    con.close()
    assert neu.all_applied(man) is True


def test_all_is_idempotent(tmp_path, monkeypatch):
    sandbox_env(monkeypatch, tmp_path)
    _seed_jobs(tmp_path, "oteny-flatbelly-talent", ["daily morning log"])
    man = _manifest(tmp_path, [{"id": "0001_crons", "kind": "crons",
                                "crons": {"disable": ["daily morning log"]}}])
    neu.main(["--manifest", str(man), "--all"])
    # second run re-applies cleanly, marker unchanged, still all-applied
    assert neu.main(["--manifest", str(man), "--all"]) == 0
    assert neu.all_applied(man) is True


def test_checklist_step_stays_pending_until_marked(tmp_path, monkeypatch):
    sandbox_env(monkeypatch, tmp_path)
    man = _manifest(tmp_path, [{"id": "0001_manual", "kind": "checklist",
                                "ref": "references/neutralize.md"}])
    neu.main(["--manifest", str(man), "--all"])         # --all does NOT run checklist
    assert neu.all_applied(man) is False                # still pending → gate stays closed
    neu.main(["--manifest", str(man), "--mark", "0001_manual"])
    assert neu.all_applied(man) is True


# --------------------------------------------------------------------------- #
# the gate — fail-closed                                                        #
# --------------------------------------------------------------------------- #
def test_gate_not_ready_when_marker_missing(tmp_path, monkeypatch, capsys):
    sandbox_env(monkeypatch, tmp_path)
    _seed_jobs(tmp_path, "oteny-flatbelly-talent", ["daily morning log"])
    man = _manifest(tmp_path, [{"id": "0001_crons", "kind": "crons",
                                "crons": {"disable": ["daily morning log"]}}])
    rc = gate.main(["--manifest", str(man), "--json"])
    assert rc == gate.EXIT_NOT_READY                     # never-neutralized → refuse to serve
    report = json.loads(capsys.readouterr().out)
    assert report["ready"] is False and report["pending"][0]["id"] == "0001_crons"


def test_gate_ready_after_neutralize(tmp_path, monkeypatch):
    sandbox_env(monkeypatch, tmp_path)
    _seed_jobs(tmp_path, "oteny-flatbelly-talent", ["daily morning log"])
    man = _manifest(tmp_path, [{"id": "0001_crons", "kind": "crons",
                                "crons": {"disable": ["daily morning log"]}}])
    neu.main(["--manifest", str(man), "--all"])
    assert gate.main(["--manifest", str(man)]) == 0      # READY only after every step applied


def test_gate_ready_when_no_manifest(tmp_path):
    # A Talent with no neutralize.yaml has nothing to de-fang → trivially READY (the lint
    # is what forces an outbound-action Talent to ship one).
    assert gate.main(["--manifest", str(tmp_path / "absent.yaml")]) == 0


def test_gate_fail_closed_on_unreadable_manifest(tmp_path, monkeypatch):
    sandbox_env(monkeypatch, tmp_path)
    bad = tmp_path / "neutralize.yaml"
    bad.write_text(":\n  - not: [valid")                 # malformed YAML
    rc = gate.main(["--manifest", str(bad)])
    assert rc == gate.EXIT_NOT_READY                     # any read error is fail-closed


# --------------------------------------------------------------------------- #
# flatbelly's real manifest                                                     #
# --------------------------------------------------------------------------- #
def test_flatbelly_neutralize_disarms_its_three_outbound_crons(tmp_path, monkeypatch):
    sandbox_env(monkeypatch, tmp_path)
    declared = yaml.safe_load((FLATBELLY / "neutralize.yaml").read_text())
    disable = declared["steps"][0]["crons"]["disable"]
    jp = _seed_jobs(tmp_path, "oteny-flatbelly-talent", disable + ["keepalive (not a DM)"])
    neu.main(["--manifest", str(FLATBELLY / "neutralize.yaml"), "--all"])
    jobs = {j["name"]: j for j in json.loads(jp.read_text())["jobs"]}
    for name in disable:
        assert jobs[name]["enabled"] is False, name
    assert gate.main(["--manifest", str(FLATBELLY / "neutralize.yaml")]) == 0
