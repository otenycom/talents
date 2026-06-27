"""Unit tests for ShopBot (the grocery-list Talent).

Proves the authored bundle works end-to-end without a VM: the profile parses, the schema
creates its tables idempotently + seeds the generic aisle reference, selfcheck reaches
READY once set up, list_view groups the active list by store -> aisle in walk order, and
the (opt-in) weekly-nudge cron planner pins model + provider.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

import yaml

from _talents import CATALOG, SHARED, load, sandbox_env

SHOPBOT = CATALOG / "oteny-shopbot-talent"
_TABLES = {"stores", "sections", "items", "item_sections"}


def _init(db: Path) -> None:
    con = sqlite3.connect(db)
    con.executescript((SHOPBOT / "scripts" / "init.sql").read_text())
    con.commit()
    con.close()


def _data_dir(root: Path) -> Path:
    d = root / ".hermes" / "data" / "oteny-shopbot-talent"
    d.mkdir(parents=True, exist_ok=True)
    return d


def test_agent_profile_parses_and_is_single_skill():
    prof = yaml.safe_load((SHOPBOT / "agent-profile.yaml").read_text())
    assert prof["bot"] == "oteny-shopbot-talent"
    assert prof["display_name"] == "ShopBot"
    assert prof["skills"] == ["oteny-shopbot-talent"]
    assert prof["routing"]["signature"] == "oteny-shopbot-talent"


def test_init_sql_creates_tables_idempotently_and_seeds_aisles(tmp_path):
    db = tmp_path / "shopping.db"
    _init(db)
    con = sqlite3.connect(db)
    tables = {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert _TABLES <= tables
    seeds = con.execute("SELECT COUNT(*) FROM item_sections").fetchone()[0]
    con.close()
    assert seeds >= 40                       # generic keyword -> aisle reference seeded
    _init(db)                                # idempotent: re-run raises nothing
    con = sqlite3.connect(db)
    again = con.execute("SELECT COUNT(*) FROM item_sections").fetchone()[0]
    con.close()
    assert again == seeds                    # INSERT OR IGNORE -> no duplicates


def test_selfcheck_reaches_ready_when_set_up(tmp_path, monkeypatch):
    sandbox_env(monkeypatch, tmp_path)
    d = _data_dir(tmp_path)
    _init(d / "shopping.db")
    (d / "profile.yaml").write_text(
        "default_store: Albert Heijn\nlanguage: en\ntimezone: Europe/Amsterdam\n")
    (d / "memory.md").write_text("# memory\n")
    (tmp_path / ".hermes" / "memories").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".hermes" / "memories" / "USER.md").write_text("# identity\n")
    # The bundle is delivered at ~/.hermes/skills/talents/<bot>/ — mirror that so the
    # `tools` artifact (list_view.py present_if_file) resolves, as it does on a real VM.
    skills = tmp_path / ".hermes" / "skills" / "talents"
    skills.mkdir(parents=True, exist_ok=True)
    (skills / "oteny-shopbot-talent").symlink_to(SHOPBOT)
    sc = load(SHARED / "selfcheck.py", "sc_shop")
    rep = sc.run(SHOPBOT / "required_artifacts.yaml")
    assert rep["ready"] is True, rep["missing"]


def test_selfcheck_not_ready_without_profile(tmp_path, monkeypatch):
    sandbox_env(monkeypatch, tmp_path)
    d = _data_dir(tmp_path)
    _init(d / "shopping.db")                  # db only, no profile
    sc = load(SHARED / "selfcheck.py", "sc_shop2")
    rep = sc.run(SHOPBOT / "required_artifacts.yaml")
    assert rep["ready"] is False


def test_list_view_groups_by_store_then_aisle_walk_order(tmp_path, monkeypatch):
    sandbox_env(monkeypatch, tmp_path)
    d = _data_dir(tmp_path)
    db = d / "shopping.db"
    _init(db)
    con = sqlite3.connect(db)
    con.execute("INSERT INTO stores (id,name,is_default) VALUES (1,'Albert Heijn',1)")
    con.execute("INSERT INTO sections (id,store_id,name,sort_order) VALUES"
                " (1,1,'Produce',10),(2,1,'Dairy',30)")
    con.execute("INSERT INTO items (name,quantity,store_id,section_id,added_by,status) VALUES"
                " ('oat milk','2',1,2,'Sam','active'),"        # Dairy (sort 30)
                " ('spinach','',1,1,'You','active'),"          # Produce (sort 10)
                " ('eggs','12',1,2,'You','bought')")           # bought -> off the active list
    con.commit()
    con.close()
    lv = load(SHOPBOT / "scripts" / "list_view.py", "lv_shop")
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    groups = lv.active_groups(con)
    con.close()
    assert len(groups) == 1 and groups[0]["store"] == "Albert Heijn"
    sections = [s["section"] for s in groups[0]["sections"]]
    assert sections == ["Produce", "Dairy"]          # walk order (sort_order asc)
    names = [it["name"] for s in groups[0]["sections"] for it in s["items"]]
    assert names == ["spinach", "oat milk"]          # bought 'eggs' excluded


def test_weekly_nudge_cron_pins_model_and_provider(tmp_path):
    pc = load(SHOPBOT / "scripts" / "provision_cron.py", "pc_shop")
    profile = {"timezone": "Europe/Amsterdam", "reminders": {"weekly_shop": "Sat 09:00"}}
    p = pc.plan(profile, str(tmp_path / "nojobs.json"),
                model="assistant", provider="router", ref=datetime(2026, 7, 1))
    assert len(p["to_create"]) == 1
    job = p["to_create"][0]
    assert job["name"] == "OtenyShopBotTalent weekly shop nudge"
    assert job["model"] == "assistant" and job["provider"] == "router"
    assert job["schedule"] == "0 7 * * 6"            # Sat 09:00 CEST -> 07:00 UTC, dow=6


def test_no_weekly_nudge_when_unset(tmp_path):
    pc = load(SHOPBOT / "scripts" / "provision_cron.py", "pc_shop2")
    assert pc.build_specs({"timezone": "Europe/Amsterdam"}) == []        # reminders absent
    assert pc.build_specs({"reminders": {"weekly_shop": ""}}) == []       # blank disables
