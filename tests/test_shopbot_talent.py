"""Unit tests for ShopBot (the grocery-list Talent).

Proves the authored bundle works end-to-end without a VM: the profile parses, the schema
seeds the aisle walk order + store aliases, selfcheck reaches READY once set up, and the
shop.py CLI backbone does the real work — store parsing + alias learning, model/-c
categories, lowest-vacant stable IDs, unique-per-store upsert, and the grouped (default
store first, then aisle walk order) render with names + qty-1 hidden.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

import yaml

from _talents import CATALOG, SHARED, load, sandbox_env

SHOPBOT = CATALOG / "oteny-shopbot-talent"
_TABLES = {"items", "store_aliases", "categories"}


def _init(db: Path) -> None:
    con = sqlite3.connect(db)
    con.executescript((SHOPBOT / "scripts" / "init.sql").read_text())
    con.commit()
    con.close()


def _data_dir(root: Path) -> Path:
    d = root / ".hermes" / "data" / "oteny-shopbot-talent"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _setup(root: Path, *, default_store="Supermarket") -> Path:
    """A ready sandbox: db + profile; returns the data dir."""
    d = _data_dir(root)
    _init(d / "shopping.db")
    (d / "profile.yaml").write_text(
        f"default_store: {default_store}\nlanguage: en\ntimezone: Europe/Amsterdam\n")
    return d


def _rows(db: Path, where="1=1"):
    con = sqlite3.connect(db); con.row_factory = sqlite3.Row
    rows = [dict(r) for r in con.execute(f"SELECT * FROM items WHERE {where} ORDER BY id")]
    con.close()
    return rows


# --------------------------------------------------------------- bundle shape
def test_agent_profile_parses_and_is_single_skill():
    prof = yaml.safe_load((SHOPBOT / "agent-profile.yaml").read_text())
    assert prof["bot"] == "oteny-shopbot-talent"
    assert prof["display_name"] == "ShopBot"
    assert prof["skills"] == ["oteny-shopbot-talent"]
    assert prof["routing"]["signature"] == "oteny-shopbot-talent"


def test_init_sql_seeds_aisles_and_aliases_idempotently(tmp_path):
    db = tmp_path / "shopping.db"
    _init(db)
    con = sqlite3.connect(db)
    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert _TABLES <= tables
    cats = con.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
    aliases = con.execute("SELECT COUNT(*) FROM store_aliases").fetchone()[0]
    # walk order is real: Produce sorts before Dairy before Other
    order = [r[0] for r in con.execute(
        "SELECT name FROM categories ORDER BY sort_order")]
    con.close()
    assert cats >= 10 and aliases >= 15
    assert order.index("Produce") < order.index("Dairy") < order.index("Other")
    _init(db)  # idempotent
    con = sqlite3.connect(db)
    assert con.execute("SELECT COUNT(*) FROM categories").fetchone()[0] == cats
    con.close()


# --------------------------------------------------------------- selfcheck
def test_selfcheck_ready_when_set_up(tmp_path, monkeypatch):
    sandbox_env(monkeypatch, tmp_path)
    d = _setup(tmp_path)
    (d / "memory.md").write_text("# memory\n")
    (tmp_path / ".hermes" / "memories").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".hermes" / "memories" / "USER.md").write_text("# identity\n")
    skills = tmp_path / ".hermes" / "skills" / "talents"
    skills.mkdir(parents=True, exist_ok=True)
    (skills / "oteny-shopbot-talent").symlink_to(SHOPBOT)
    sc = load(SHARED / "selfcheck.py", "sc_shop")
    rep = sc.run(SHOPBOT / "required_artifacts.yaml")
    assert rep["ready"] is True, rep["missing"]


def test_selfcheck_not_ready_without_profile(tmp_path, monkeypatch):
    sandbox_env(monkeypatch, tmp_path)
    _init(_data_dir(tmp_path) / "shopping.db")  # db only, no profile
    sc = load(SHARED / "selfcheck.py", "sc_shop2")
    assert sc.run(SHOPBOT / "required_artifacts.yaml")["ready"] is False


# --------------------------------------------------------------- shop.py CLI
def _shop(monkeypatch, tmp_path):
    sandbox_env(monkeypatch, tmp_path)
    return load(SHOPBOT / "scripts" / "shop.py", "shop_cli")


def test_add_parses_store_in_text_and_learns_it(tmp_path, monkeypatch):
    shop = _shop(monkeypatch, tmp_path)
    _setup(tmp_path)
    shop.main(["add", "aardbei bij banketbakker", "-c", "Bakery", "-u", "Ries"])
    db = _data_dir(tmp_path) / "shopping.db"
    row = _rows(db)[0]
    assert row["name"] == "Aardbei" and row["store"] == "Banketbakker"
    assert row["category"] == "Bakery" and row["status"] == "pending"
    # the new structured store was LEARNED into store_aliases
    con = sqlite3.connect(db)
    learned = con.execute(
        "SELECT canonical FROM store_aliases WHERE alias='banketbakker'").fetchone()
    con.close()
    assert learned and learned[0] == "Banketbakker"


def test_add_resolves_seeded_alias_and_default_store(tmp_path, monkeypatch):
    shop = _shop(monkeypatch, tmp_path)
    _setup(tmp_path, default_store="Albert Heijn")
    shop.main(["add", "melk", "-s", "ah", "-c", "Dairy"])       # alias ah -> Albert Heijn
    shop.main(["add", "bananen", "-c", "Produce"])              # no store -> default
    rows = {r["name"]: r for r in _rows(_data_dir(tmp_path) / "shopping.db")}
    assert rows["Melk"]["store"] == "Albert Heijn"
    assert rows["Bananen"]["store"] == "Albert Heijn"


def test_add_is_unique_per_store_upsert(tmp_path, monkeypatch):
    shop = _shop(monkeypatch, tmp_path)
    _setup(tmp_path)
    shop.main(["add", "oat milk", "-q", "2", "-c", "Dairy"])
    shop.main(["add", "oat milk", "-q", "3", "-c", "Dairy"])    # re-add → update qty, same row
    rows = _rows(_data_dir(tmp_path) / "shopping.db")
    assert len(rows) == 1 and rows[0]["quantity"] == "3" and rows[0]["id"] == 1


def test_check_drops_off_and_lowest_vacant_id_recycles(tmp_path, monkeypatch):
    shop = _shop(monkeypatch, tmp_path)
    _setup(tmp_path)
    for n in ("eggs", "bread", "milk"):
        shop.main(["add", n, "-c", "Other"])                   # ids 1,2,3
    shop.main(["remove", "2"])                                  # free id 2
    shop.main(["add", "peas", "-c", "Frozen"])                 # should reuse id 2
    db = _data_dir(tmp_path) / "shopping.db"
    peas = next(r for r in _rows(db) if r["name"] == "Peas")
    assert peas["id"] == 2
    shop.main(["check", "1"])                                   # eggs bought → off the list
    pending = [r["name"] for r in _rows(db, "status='pending'")]
    assert "Eggs" not in pending and "Peas" in pending


def test_list_groups_default_store_first_then_aisle_walk_order(tmp_path, monkeypatch, capsys):
    shop = _shop(monkeypatch, tmp_path)
    _setup(tmp_path, default_store="Albert Heijn")
    shop.main(["add", "spinach", "-c", "Produce"])             # AH (default), Produce(10)
    shop.main(["add", "milk", "-q", "1", "-c", "Dairy"])       # AH, Dairy(30), qty1 hidden
    shop.main(["add", "steak bij Butcher", "-c", "Meat & Fish"])  # specialty store
    capsys.readouterr()
    shop.main(["list"])
    out = capsys.readouterr().out
    assert out.index("Albert Heijn") < out.index("Butcher")    # default store first
    assert out.index("Produce") < out.index("Dairy")           # aisle walk order
    assert "Milk" in out and "x1" not in out                   # qty 1 hidden
    assert "added_by" not in out and "Ries" not in out         # names not shown


# --------------------------------------------------------------- legacy import
def _legacy_db(path: Path) -> None:
    """A stand-in for the stock grocery-tracker's ~/grocery_list/grocery.db."""
    con = sqlite3.connect(path)
    con.executescript(
        "CREATE TABLE grocery_items (id INTEGER PRIMARY KEY, item TEXT, quantity TEXT,"
        " added_by TEXT, status TEXT, created_at TEXT, completed_at TEXT, category TEXT,"
        " store TEXT);"
        "CREATE TABLE store_aliases (alias TEXT PRIMARY KEY, canonical_name TEXT);")
    con.executemany(
        "INSERT INTO grocery_items (item,quantity,added_by,status,category,store) "
        "VALUES (?,?,?,?,?,?)", [
            ("Spinazie", "1", "Angela", "pending", "Groente & fruit", "AH"),
            ("Melk", "2", "Ries", "pending", "Zuivel (melk, yoghurt)", "AH"),
            ("Paling", "1", "Ries", "pending", "Vis & schaal- en schelpdieren", "Hanos"),
            ("Brood", "1", "Angela", "completed", "Bakkerij (brood)", "Supermarkt"),
            ("Mystery", "1", "Angela", "pending", "Onbekend", "Supermarkt"),
        ])
    con.execute("INSERT INTO store_aliases VALUES ('ah','AH')")
    con.commit(); con.close()


def test_import_legacy_maps_aisles_and_is_idempotent(tmp_path, monkeypatch):
    sandbox_env(monkeypatch, tmp_path)
    d = _setup(tmp_path)
    legacy = tmp_path / "grocery_list" / "grocery.db"
    legacy.parent.mkdir(parents=True)
    _legacy_db(legacy)
    imp = load(SHOPBOT / "scripts" / "import_legacy.py", "imp_shop")
    res = imp.migrate(legacy, d / "shopping.db")
    assert res["imported"] == 5 and not res["skipped"]
    rows = {r["name"]: r for r in _rows(d / "shopping.db")}
    assert rows["Spinazie"]["category"] == "Produce" and rows["Spinazie"]["store"] == "AH"
    assert rows["Melk"]["category"] == "Dairy"
    assert rows["Paling"]["category"] == "Meat & Fish"
    assert rows["Brood"]["category"] == "Bakery" and rows["Brood"]["status"] == "completed"
    assert rows["Mystery"]["category"] == "Other"          # unknown Dutch aisle → Other
    # the household's learned alias carried over (their canonical 'AH' wins over the seed)
    con = sqlite3.connect(d / "shopping.db")
    assert con.execute("SELECT canonical FROM store_aliases WHERE alias='ah'").fetchone()[0] == "AH"
    con.close()
    # idempotent: a second run does nothing (list already has items)
    assert imp.migrate(legacy, d / "shopping.db")["skipped"] is True


def test_import_legacy_noop_without_legacy_db(tmp_path, monkeypatch):
    sandbox_env(monkeypatch, tmp_path)
    d = _setup(tmp_path)
    imp = load(SHOPBOT / "scripts" / "import_legacy.py", "imp_shop2")
    assert imp.migrate(tmp_path / "nope.db", d / "shopping.db")["skipped"] is True


# --------------------------------------------------------------- cron (unchanged)
def test_weekly_nudge_cron_pins_model_and_provider(tmp_path):
    pc = load(SHOPBOT / "scripts" / "provision_cron.py", "pc_shop")
    profile = {"timezone": "Europe/Amsterdam", "reminders": {"weekly_shop": "Sat 09:00"}}
    p = pc.plan(profile, str(tmp_path / "nojobs.json"),
                model="assistant", provider="router", ref=datetime(2026, 7, 1))
    assert len(p["to_create"]) == 1
    job = p["to_create"][0]
    assert job["model"] == "assistant" and job["provider"] == "router"
    assert job["schedule"] == "0 7 * * 6"
