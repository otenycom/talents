#!/usr/bin/env python3
"""list_view — render the live shopping list grouped by store -> aisle, in walk order.

The deterministic backbone of "what's left": one read-only query that emits the active
list grouped by store, then by the store's own section walk order (lower sort_order
first), so the bot's reply reads top-to-bottom as you move through the store and never
backtracks. The model only formats this output for Telegram; it never re-orders or
recites the list from memory (the hard grounding rule).

Usage:
    python3 list_view.py                 # active list, grouped by store -> aisle
    python3 list_view.py --bought        # recently bought (last 20), for re-adds
    python3 list_view.py --json          # machine-readable (the same grouping)

Pure / read-only / side-effect-free. Exit code is always 0 (a non-zero would make the
LLM's terminal call look failed). Paths resolve through the same env overrides as
selfcheck.py so a relocated overlay / tests stay hermetic.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

_BOT = "oteny-shopbot-talent"


def _home() -> Path:
    return Path(os.environ.get("HH_HOME") or Path.home())


def _hermes_home() -> Path:
    env = os.environ.get("HH_HERMES_HOME") or os.environ.get("HERMES_HOME")
    return Path(env) if env else _home() / ".hermes"


def _db_path() -> Path:
    return _hermes_home() / "data" / _BOT / "shopping.db"


def _connect(db: Path) -> sqlite3.Connection | None:
    if not db.exists():
        return None
    con = sqlite3.connect(str(db))
    con.row_factory = sqlite3.Row
    return con


def active_groups(con: sqlite3.Connection) -> list[dict]:
    """Active items grouped store -> section (walk order), each item with qty + adder."""
    rows = con.execute(
        """
        SELECT i.id, i.name, i.quantity, i.added_by,
               COALESCE(st.name, '(no store)')      AS store,
               COALESCE(se.name, 'Other')           AS section,
               COALESCE(se.sort_order, 999)         AS sort_order,
               COALESCE(st.is_default, 0)           AS is_default
        FROM items i
        LEFT JOIN stores   st ON st.id = i.store_id
        LEFT JOIN sections se ON se.id = i.section_id
        WHERE i.status = 'active'
        ORDER BY is_default DESC, store, sort_order, section, i.name
        """
    ).fetchall()
    stores: dict[str, dict] = {}
    for r in rows:
        store = stores.setdefault(r["store"], {"store": r["store"], "sections": {}})
        sec = store["sections"].setdefault(r["section"], [])
        item = {"name": r["name"]}
        if r["quantity"]:
            item["quantity"] = r["quantity"]
        if r["added_by"]:
            item["added_by"] = r["added_by"]
        sec.append(item)
    return [
        {"store": s["store"],
         "sections": [{"section": name, "items": items}
                      for name, items in s["sections"].items()]}
        for s in stores.values()
    ]


def recent_bought(con: sqlite3.Connection, limit: int = 20) -> list[dict]:
    rows = con.execute(
        "SELECT name, quantity, bought_by, bought_at FROM items "
        "WHERE status = 'bought' ORDER BY bought_at DESC, id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def _print_active(groups: list[dict]) -> None:
    total = sum(len(s["items"]) for g in groups for s in g["sections"])
    if not groups:
        print("ACTIVE LIST: (empty — nothing to buy)")
        return
    print(f"ACTIVE LIST ({total} item(s)) — in aisle order:")
    for g in groups:
        print(f"# {g['store']}")
        for s in g["sections"]:
            line = ", ".join(
                it["name"] + (f" x{it['quantity']}" if it.get("quantity") else "")
                for it in s["items"]
            )
            print(f"  {s['section']}: {line}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="OtenyShopBotTalent list view")
    ap.add_argument("--bought", action="store_true", help="recently bought items")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    con = _connect(_db_path())
    if con is None:
        out = {"ready": False, "reason": "no database yet"}
        print(json.dumps(out) if args.json else "no shopping.db yet — run first-run setup")
        return 0
    try:
        if args.bought:
            data = recent_bought(con)
            if args.json:
                print(json.dumps({"bought": data}, indent=2))
            else:
                print("RECENTLY BOUGHT:")
                for r in data:
                    q = f" x{r['quantity']}" if r["quantity"] else ""
                    who = f" — {r['bought_by']}" if r["bought_by"] else ""
                    print(f"  {r['name']}{q}{who}")
            return 0
        groups = active_groups(con)
        if args.json:
            print(json.dumps({"active": groups}, indent=2))
        else:
            _print_active(groups)
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
