# ShopBot — per-intent checklists

The runnable detail behind the master triage. Every change is **one `shop.py` call** —
the script parses the store, picks the aisle, assigns a stable id, and renders the list, so
the decision left to you is just the verb + arguments. Hard runtime rules (obey all):

- **`shop.py` for every change** — never raw SQL, never a `python3 -c`/heredoc (the
  approval gate stalls the bot).
- **Read the list from `shop.py list` in the same turn** before you state it — never recite
  from memory.
- **Pass `-c <aisle>`** on every add (you reason the section) and **`-u <sender>`** so the
  add is attributed (recorded, not displayed).
- A **bare item name only adds / keeps it to-buy — it NEVER checks it off.**

Path: `python3 ~/.hermes/skills/talents/oteny-shopbot-talent/scripts/shop.py` (shown as `shop.py`).

## Add item(s)

1. One item: `shop.py add "oat milk" -q 2 -c Dairy -u Sam`. Quantity optional (omit for 1).
2. A comma list ("eieren, tomaten, brood"): split on commas, `add` each in its own call,
   each with its reasoned `-c`.
3. A store spoken in the message ("aardbei bij banketbakker", "AH: melk"): pass it as part
   of the text — `shop.py add "aardbei bij banketbakker" -c Bakery` — or use `-s`. shop.py
   resolves the alias and **learns** a new structured store.
4. A photo of a product ("koop dit"): identify the item from the image, then `add` it with a
   reasoned `-c`.
5. Re-adding something already on the list just updates its quantity and keeps it to-buy
   (shop.py upserts on name+store) — that is the intended "I need more of this" behaviour.

## Check off (bought)

1. A bare **number** ("7") or "vink X af" / "X gekocht" / "got the X" → `shop.py check 7`
   (or `shop.py check "oat milk" -u Sam`).
2. shop.py matches an id or a fuzzy/singular-plural name; if your name is ambiguous, run
   `shop.py list` and check by **id**.
3. "X moest niet afgevinkt" (it shouldn't have been) → `shop.py uncheck X` to restore it.

## Move to another store

"15 naar AH" / "kaas bij Hanos" (NOT a check-off) → `shop.py move 15 AH` /
`shop.py move kaas Hanos`. shop.py resolves/learns the store.

## Remove (no longer needed)

"haal X eraf" / "we don't need X" → `shop.py remove X` (drops off; not counted as bought).

## Show the list

"wat staat er op de lijst?" / "what's left?" → `shop.py list`. Post it as-is (🛒 store →
aisle → `id. item`), localising the aisle headers; don't add items or re-order.

## Stores & default

- Change the default store: edit `default_store` in `profile.yaml` + `memory.md` (new adds
  without a named store file there).
- shop.py already knows the common chains and learns new structured ones; you never hand-edit
  `store_aliases`.
