#!/usr/bin/env python3
"""import_legacy — one-time rescue of a legacy grocery list into ShopBot.

A tenant who used the stock Hermes `grocery-tracker` skill has a list at
`~/grocery_list/grocery.db` (outside `~/.hermes`, so it is NOT in any snapshot). When
ShopBot takes over, first-run runs this to import that list into ShopBot's snapshotted
store (`~/.hermes/data/oteny-shopbot-talent/shopping.db`) so the household keeps every item.

- **Idempotent + safe**: imports only when the target list is EMPTY (never double-imports,
  never clobbers a list ShopBot already owns); a missing legacy db is a clean no-op.
- Maps the legacy Dutch aisle names → ShopBot's canonical English sections (the model
  localises the display); keeps item/quantity/store/status/added_by/timestamps + the
  household's learned store aliases (their names win over the seed).

    python3 import_legacy.py            # ~/grocery_list/grocery.db -> ShopBot's db
    python3 import_legacy.py --legacy PATH --target PATH

Read-only on the legacy db. Exit 0 always (outcome in the printed text)."""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

_BOT = "oteny-shopbot-talent"

# Legacy Dutch aisle (matched by prefix, the live names carry parentheticals) -> ShopBot
# canonical English section (categories table). Anything unmatched → Other (never silent SQL
# error). Mirrors the live grocery-tracker categories.py groupings.
_DUTCH_CAT = [
    ("groente", "Produce"), ("fruit", "Produce"),
    ("bakkerij", "Bakery"), ("brood", "Bakery"),
    ("zuivel", "Dairy"),
    ("kaas", "Deli"), ("vleeswaren", "Deli"),
    ("vlees", "Meat & Fish"), ("gevogelte", "Meat & Fish"),
    ("vis", "Meat & Fish"),
    ("diepvries", "Frozen"),
    ("kruidenierswaren", "Pantry"), ("voorraadkast", "Pantry"),
    ("dranken", "Drinks"), ("frisdrank", "Drinks"),
    ("snack", "Snacks"), ("snoep", "Snacks"),
    ("huishouden", "Household"),
    ("verzorging", "Personal care"), ("persoonlijke", "Personal care"),
]


def _home() -> Path:
    return Path(os.environ.get("HH_HOME") or Path.home())


def _hermes_home() -> Path:
    env = os.environ.get("HH_HERMES_HOME") or os.environ.get("HERMES_HOME")
    return Path(env) if env else _home() / ".hermes"


def _default_legacy() -> Path:
    return _home() / "grocery_list" / "grocery.db"


def _default_target() -> Path:
    return _hermes_home() / "data" / _BOT / "shopping.db"


def _map_category(dutch: str | None) -> str:
    low = (dutch or "").strip().lower()
    if not low or low.startswith("overig"):
        return "Other"
    for needle, canon in _DUTCH_CAT:
        if needle in low:
            return canon
    return "Other"


def migrate(legacy: Path, target: Path) -> dict:
    if not legacy.exists():
        return {"imported": 0, "reason": "no legacy grocery.db", "skipped": True}
    tgt = sqlite3.connect(str(target))
    try:
        have = {r[0] for r in tgt.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if "items" not in have:
            return {"imported": 0, "reason": "ShopBot db not initialised (run init.sql first)",
                    "skipped": True}
        if tgt.execute("SELECT COUNT(*) FROM items").fetchone()[0] > 0:
            return {"imported": 0, "reason": "ShopBot list already has items", "skipped": True}

        src = sqlite3.connect(f"file:{legacy}?mode=ro", uri=True)
        src.row_factory = sqlite3.Row
        rows = src.execute(
            "SELECT id, item, quantity, added_by, status, created_at, completed_at, "
            "category, store FROM grocery_items").fetchall()
        for r in rows:
            if not (r["item"] or "").strip():
                continue                         # skip a malformed legacy row (no name)
            status = r["status"] if r["status"] in ("pending", "completed") else "pending"
            cat = _map_category(r["category"])
            # COALESCE added_at — added_at is NOT NULL; a legacy row may have no created_at.
            tgt.execute(
                "INSERT OR IGNORE INTO items (id, name, quantity, category, store, status, "
                "added_by, added_at, completed_at) "
                "VALUES (?,?,?,?,?,?,?, COALESCE(?, datetime('now')), ?)",
                (r["id"], r["item"], r["quantity"] or "1", cat, r["store"] or "Supermarket",
                 status, r["added_by"], r["created_at"], r["completed_at"]))
        # count actual inserts from the db (not attempts), so the receipt is honest
        n_items = tgt.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        cats = dict(tgt.execute("SELECT category, COUNT(*) FROM items GROUP BY category"))
        # Carry over the household's learned store aliases (their canonical wins over seeds).
        n_alias = 0
        try:
            for a in src.execute("SELECT alias, canonical_name FROM store_aliases"):
                tgt.execute("INSERT OR REPLACE INTO store_aliases (alias, canonical) "
                            "VALUES (?, ?)", (a[0], a[1]))
                n_alias += 1
        except sqlite3.Error:
            pass
        src.close()
        tgt.commit()
        return {"imported": n_items, "aliases": n_alias, "by_category": cats, "skipped": False}
    finally:
        tgt.close()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Import a legacy grocery list into ShopBot")
    ap.add_argument("--legacy", default=str(_default_legacy()))
    ap.add_argument("--target", default=str(_default_target()))
    args = ap.parse_args(argv)
    res = migrate(Path(args.legacy), Path(args.target))
    if res["skipped"]:
        print(f"import_legacy: nothing to do — {res['reason']}")
    else:
        print(f"import_legacy: imported {res['imported']} item(s) + {res['aliases']} store "
              f"alias(es); by aisle: {res['by_category']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
