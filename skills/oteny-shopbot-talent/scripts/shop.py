#!/usr/bin/env python3
"""shop.py — the single CLI backbone for OtenyShopBotTalent's shared grocery list.

The model drives ONE command per action (the reliable pattern on the weak tier, proven by
the real-world household list this Talent generalises): the script owns store-parsing,
aisle categorisation, stable-ID assignment and the grouped render, so the model only has to
pick the verb. All writes go through here; the .md never issues raw SQL.

    shop.py add "<item>" [-q QTY] [-u USER] [-c CATEGORY] [-s STORE]
    shop.py list [--all] [--json]      # active list, grouped by store -> aisle (walk order)
    shop.py check  <id|name> [-u USER] # mark bought (drops off the active list)
    shop.py uncheck <id|name>          # back to pending
    shop.py move   <id|name> <store>   # route to a different store
    shop.py remove <id|name>           # no longer needed (not "bought")

Conventions captured from real use:
- A store may be spoken IN the item ("melk bij AH", "AH: melk") — parsed + alias-resolved;
  a new structured store ("... bij slager") is LEARNED. Default = the profile's default_store.
- Category is the model's call (pass -c with a canonical aisle); a small map is the fallback,
  and an item is NEVER dumped in "Other" silently — the model reasons it.
- IDs are the lowest vacant positive int (stable, low, friendly while shopping). UNIQUE
  (name, store): re-adding an item updates its qty and flips it back to pending.
- The list hides who-added and hides quantity 1; bought items fall off the active view.

Read-only paths resolve through HH_HOME/HH_HERMES_HOME like selfcheck/preflight, so a
relocated overlay / tests stay hermetic. Exit code is always 0 (a non-zero makes the LLM's
terminal call look failed); outcomes are in the printed text.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - PyYAML is always present on Hermes
    yaml = None

_BOT = "oteny-shopbot-talent"
# Fallback keyword -> canonical aisle (the model normally passes -c; this catches misses).
_CATEGORY_MAP = {
    "Produce": ["banana", "apple", "spinach", "lettuce", "tomato", "onion", "potato",
                "carrot", "avocado", "pepper", "cucumber", "lemon", "berries", "fruit"],
    "Bakery": ["bread", "sourdough", "bun", "bagel", "croissant", "roll"],
    "Dairy": ["milk", "yoghurt", "yogurt", "butter", "cheese", "egg", "cream"],
    "Meat & Fish": ["chicken", "beef", "mince", "pork", "salmon", "fish", "tofu", "bacon"],
    "Pantry": ["rice", "pasta", "flour", "sugar", "oil", "beans", "cereal", "coffee",
               "tea", "peanut butter", "sauce", "spice", "tin", "can"],
    "Frozen": ["peas", "ice cream", "pizza", "frozen"],
    "Drinks": ["water", "juice", "soda", "beer", "wine", "cola"],
    "Household": ["dish soap", "detergent", "toilet paper", "kitchen roll", "foil", "bin bag"],
    "Personal care": ["shampoo", "toothpaste", "soap", "deodorant"],
}
# "<item> bij/naar/at <store>" (suffix) — Dutch + English prepositions.
_SUFFIX_RE = re.compile(r"^(.*?)\s+(?:bij|naar|at|@)\s+([^,]+?)\s*$", re.I)
# "<store>: <item>" or "<store> - <item>" (heading).
_HEADING_RE = re.compile(r"^([A-Za-z][\w &'-]{1,24})\s*[:\-]\s+(.+)$")


def _home() -> Path:
    return Path(os.environ.get("HH_HOME") or Path.home())


def _hermes_home() -> Path:
    env = os.environ.get("HH_HERMES_HOME") or os.environ.get("HERMES_HOME")
    return Path(env) if env else _home() / ".hermes"


def _data_dir() -> Path:
    return _hermes_home() / "data" / _BOT


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(str(_data_dir() / "shopping.db"))
    con.row_factory = sqlite3.Row
    return con


def _default_store() -> str:
    prof = _data_dir() / "profile.yaml"
    if yaml and prof.exists():
        try:
            data = yaml.safe_load(prof.read_text()) or {}
            if data.get("default_store"):
                return str(data["default_store"])
        except Exception:
            pass
    return "Supermarket"


def _resolve_store(con: sqlite3.Connection, spoken: str, *, learn: bool) -> str:
    """Map a spoken store to its canonical name via store_aliases; learn a new one."""
    spoken = spoken.strip()
    row = con.execute("SELECT canonical FROM store_aliases WHERE alias = ?",
                      (spoken.lower(),)).fetchone()
    if row:
        return row["canonical"]
    canonical = spoken.title()
    if learn:  # a structured "bij <store>" we haven't seen → remember it
        con.execute("INSERT OR IGNORE INTO store_aliases (alias, canonical) VALUES (?, ?)",
                    (spoken.lower(), canonical))
    return canonical


def _parse_store(con: sqlite3.Connection, text: str) -> tuple[str, str | None]:
    """Split a store off the item text ("melk bij AH" / "AH: melk"). Returns
    (clean_item, canonical_store_or_None). Only a STRUCTURED match learns a new store."""
    m = _SUFFIX_RE.match(text)
    if m and m.group(1).strip():
        return m.group(1).strip(), _resolve_store(con, m.group(2), learn=True)
    m = _HEADING_RE.match(text)
    if m:
        return m.group(2).strip(), _resolve_store(con, m.group(1), learn=True)
    return text.strip(), None


def _guess_category(name: str) -> str:
    low = name.lower()
    for cat, words in _CATEGORY_MAP.items():
        if any(w in low for w in words):
            return cat
    return "Other"


def _lowest_vacant_id(con: sqlite3.Connection) -> int:
    used = {r["id"] for r in con.execute("SELECT id FROM items")}
    i = 1
    while i in used:
        i += 1
    return i


def _find(con: sqlite3.Connection, token: str) -> sqlite3.Row | None:
    """Resolve an id or a (fuzzy, singular/plural) name to one active/pending row."""
    token = token.strip()
    if token.isdigit():
        return con.execute("SELECT * FROM items WHERE id = ?", (int(token),)).fetchone()
    rows = con.execute(
        "SELECT * FROM items WHERE status != 'removed' AND "
        "(LOWER(name) = LOWER(?) OR LOWER(name) LIKE LOWER(?) OR LOWER(?) LIKE LOWER(name||'%'))"
        " ORDER BY (status='pending') DESC, id LIMIT 1",
        (token, token + "%", token)).fetchone()
    return rows


def cmd_add(con, args) -> str:
    name, store = _parse_store(con, args.text)
    if args.store:
        store = _resolve_store(con, args.store, learn=True)
    store = store or _default_store()
    name = name.strip().capitalize()
    category = args.category or _guess_category(name)
    qty = (args.quantity or "1").strip() or "1"
    existing = con.execute(
        "SELECT id, status FROM items WHERE LOWER(name)=LOWER(?) AND LOWER(store)=LOWER(?)",
        (name, store)).fetchone()
    if existing:
        con.execute("UPDATE items SET quantity=?, category=?, status='pending', "
                    "completed_at=NULL, added_by=COALESCE(?, added_by) WHERE id=?",
                    (qty, category, args.user, existing["id"]))
        iid = existing["id"]
        verb = "Updated"
    else:
        iid = _lowest_vacant_id(con)
        con.execute("INSERT INTO items (id, name, quantity, category, store, status, added_by)"
                    " VALUES (?, ?, ?, ?, ?, 'pending', ?)",
                    (iid, name, qty, category, store, args.user))
        verb = "Added"
    con.commit()
    q = "" if qty == "1" else f" x{qty}"
    return f"{verb} #{iid}: {name}{q} → {category} at {store}"


def _status_change(con, args, status: str, msg: str) -> str:
    row = _find(con, args.token)
    if not row:
        return f"Not found: {args.token!r}"
    completed = "datetime('now')" if status == "completed" else "NULL"
    by = getattr(args, "user", None)
    con.execute(f"UPDATE items SET status=?, completed_at={completed}, "
                f"bought_by=COALESCE(?, bought_by) WHERE id=?", (status, by, row["id"]))
    con.commit()
    left = con.execute("SELECT COUNT(*) FROM items WHERE status='pending'").fetchone()[0]
    return f"{msg}: #{row['id']} {row['name']} · {left} left"


def cmd_move(con, args) -> str:
    row = _find(con, args.token)
    if not row:
        return f"Not found: {args.token!r}"
    store = _resolve_store(con, args.store, learn=True)
    con.execute("UPDATE items SET store=? WHERE id=?", (store, row["id"]))
    con.commit()
    return f"Moved #{row['id']} {row['name']} → {store}"


def cmd_remove(con, args) -> str:
    row = _find(con, args.token)
    if not row:
        return f"Not found: {args.token!r}"
    con.execute("DELETE FROM items WHERE id = ?", (row["id"],))  # hard delete frees the id
    con.commit()
    left = con.execute("SELECT COUNT(*) FROM items WHERE status='pending'").fetchone()[0]
    return f"Removed #{row['id']} {row['name']} · {left} left"


def cmd_clear(con, args) -> str:
    if args.all:
        n = con.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        con.execute("DELETE FROM items")
        scope = "everything"
    else:
        n = con.execute("SELECT COUNT(*) FROM items WHERE status='completed'").fetchone()[0]
        con.execute("DELETE FROM items WHERE status='completed'")
        scope = "bought items"
    con.commit()
    return f"Cleared {n} {scope}"


def cmd_list(con, args) -> str:
    rows = con.execute(
        "SELECT i.id, i.name, i.quantity, i.category, i.store, "
        "COALESCE(c.sort_order, 500) AS so, COALESCE(c.emoji,'•') AS emoji "
        "FROM items i LEFT JOIN categories c ON c.name = i.category "
        "WHERE i.status = 'pending' "
        "ORDER BY (i.store = ?) DESC, i.store, so, i.category, i.id",
        (_default_store(),)).fetchall()
    if args.json:
        return json.dumps([dict(r) for r in rows], ensure_ascii=False)
    if not rows:
        return "List is empty — nothing to buy."
    out, store, cat = [], None, None
    for r in rows:
        if r["store"] != store:
            store, cat = r["store"], None
            out.append(f"\n🛒 {store}")
        if r["category"] != cat:
            cat = r["category"]
            out.append(f"  {r['emoji']} {cat}")
        q = "" if (r["quantity"] or "1") == "1" else f" x{r['quantity']}"
        out.append(f"    {r['id']}. {r['name']}{q}")
    n = len(rows)
    out.append(f"\n{n} item{'s' if n != 1 else ''} · walk top to bottom")
    return "\n".join(out).lstrip("\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="OtenyShopBotTalent shared list")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add"); a.add_argument("text")
    a.add_argument("-q", "--quantity"); a.add_argument("-u", "--user")
    a.add_argument("-c", "--category"); a.add_argument("-s", "--store")
    li = sub.add_parser("list"); li.add_argument("--all", action="store_true")
    li.add_argument("--json", action="store_true")
    ch = sub.add_parser("check"); ch.add_argument("token"); ch.add_argument("-u", "--user")
    un = sub.add_parser("uncheck"); un.add_argument("token")
    mv = sub.add_parser("move"); mv.add_argument("token"); mv.add_argument("store")
    rm = sub.add_parser("remove"); rm.add_argument("token")
    cl = sub.add_parser("clear"); cl.add_argument("--all", action="store_true")
    args = ap.parse_args(argv)

    con = _connect()
    try:
        if args.cmd == "add":
            print(cmd_add(con, args))
        elif args.cmd == "list":
            print(cmd_list(con, args))
        elif args.cmd == "check":
            print(_status_change(con, args, "completed", "Checked off"))
        elif args.cmd == "uncheck":
            print(_status_change(con, args, "pending", "Back on the list"))
        elif args.cmd == "move":
            print(cmd_move(con, args))
        elif args.cmd == "remove":
            print(cmd_remove(con, args))
        elif args.cmd == "clear":
            print(cmd_clear(con, args))
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
