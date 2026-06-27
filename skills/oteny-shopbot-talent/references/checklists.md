# ShopBot — per-intent checklists

The runnable detail behind the master triage. Each is a numbered, literal protocol — the
decision is the checklist, not the model's judgement. Hard runtime rules (obey all):

- **One `sqlite3` invocation per terminal call.** Never chain INSERT + SELECT in one call.
- **Read the list from the database in the same turn** before you state it — never recite
  it from memory. Use `list_view.py` for the aisle-ordered render.
- **Attribute** each add / check-off to the group member who sent the message (`added_by`
  / `bought_by`); in a DM use the owner's name or leave blank.
- Quote item names back as the owner said them; keep numbers exact.

All paths below are under `~/.hermes/skills/talents/oteny-shopbot-talent/scripts/` (scripts)
and `~/.hermes/data/oteny-shopbot-talent/shopping.db` (the db, shown as `$DB`).

## Add one or more items

1. Parse each item into **name** + optional **quantity** (free text: "2", "500 g", "1 bunch").
2. **Store:** the named store if the message says one, else the profile's `default_store`.
   Resolve its id: `sqlite3 $DB "SELECT id FROM stores WHERE name='<store>';"`.
3. **Section:** find the aisle from the generic reference — one call:
   `sqlite3 $DB "SELECT section_name FROM item_sections WHERE '<name lowercased>' LIKE '%'||item_pattern||'%' LIMIT 1;"`.
   Then map that section name to this store's section id:
   `sqlite3 $DB "SELECT id FROM sections WHERE store_id=<sid> AND name='<section_name>';"`.
   No match → leave `section_id` NULL (renders under "Other"); never guess a wrong aisle.
4. **Insert** (one call per item):
   `sqlite3 $DB "INSERT INTO items (name, quantity, store_id, section_id, added_by) VALUES ('oat milk','2',<sid>,<secid>,'Sam');"`.
5. **Confirm**: name → its aisle, the store, and the new active count (from `list_view.py`
   or `SELECT COUNT(*) … WHERE status='active'`). Keep it one short line.

## Set / change a quantity

1. Find the active item: `sqlite3 $DB "SELECT id,name,quantity FROM items WHERE status='active' AND name LIKE '%<name>%';"`.
2. One match → `sqlite3 $DB "UPDATE items SET quantity='<new>' WHERE id=<id>;"`. Several
   matches → ask which one (list them); never update blindly.

## Check off (bought)

1. Find the active item(s) by name (as above).
2. `sqlite3 $DB "UPDATE items SET status='bought', bought_by='<member>', bought_at=datetime('now') WHERE id=<id>;"`.
3. Confirm "checked off" + how many remain. Bought items drop off the active list
   automatically (they stay for the recent-buys view / quick re-add).

## Remove (don't need it after all)

1. Find the active item by name.
2. `sqlite3 $DB "UPDATE items SET status='removed' WHERE id=<id>;"` (drops off active,
   not counted as bought).

## What's left / show the list

1. `python3 .../scripts/list_view.py` — the active list grouped by store → aisle in walk
   order. Post it as-is (Telegram-formatted); do not re-order or add items.
2. "What did we get?" → `list_view.py --bought` (recent buys, for quick re-adds).

## Stores &amp; aisles

- **Add a store:** `INSERT OR IGNORE INTO stores (name) VALUES ('<store>');` then add its
  sections in walk order, one call each:
  `INSERT OR IGNORE INTO sections (store_id, name, sort_order) VALUES (<sid>,'Produce',10);`.
- **Make it the default:** `UPDATE stores SET is_default=0;` then
  `UPDATE stores SET is_default=1 WHERE id=<sid>;` (two calls) — and update `default_store`
  in profile.yaml + memory.md.
- **Reorder an aisle:** `UPDATE sections SET sort_order=<n> WHERE id=<secid>;` (lower =
  earlier in the walk).
