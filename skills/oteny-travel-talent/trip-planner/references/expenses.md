# trip-planner — Shared Expenses: log, split, settle up

The `expenses` table is the shared ledger; `scripts/settle_up.py` is the deterministic
who-owes-whom (never compute a balance by hand — hard rule ①). Schema in
[`datamodel.md`](datamodel.md).

## Log an expense (entry → verify → reply)

1. Pull `amount`, `currency` (default `profile.default_currency`), `category`
   (food/transport/lodging/activity/other), `note`, and **who paid** (`payer_member_id`;
   NULL = the owner). Map the payer from the speaker in a group.
2. Decide the **split** (`split_json`):
   - default **`'even'`** — shared equally across every `members` row.
   - **custom** — a JSON object `{"<member_id>": <weight>}` (weights or absolute amounts;
     `settle_up.py` normalizes). e.g. only two of four shared a taxi.
3. Insert — one statement; read the id back.

   ```bash
   sqlite3 ~/.hermes/data/oteny-travel-talent/trips.db "INSERT INTO expenses (trip_id, payer_member_id, amount, currency, category, split_json, note) VALUES (<trip_id>,<payer_id>,84.00,'EUR','food','even','dinner at the market');"
   ```
4. Reply: confirm the logged amount + payer + how it's split, quoting the number.

## Settle up — "who owes whom"

Run the deterministic settler (per-currency; no FX conversion in v1):

```bash
python3 ~/.hermes/skills/talents/oteny-travel-talent/scripts/settle_up.py --trip <trip_id>
```

It prints, per currency, the **total spend** and the **minimal transfers** ("Anna owes
Ben 84.00 EUR"). Reply with those lines verbatim (translate the connective into the
tenant's language). If it reports "all square", say so. A **solo DM trip** has no one to
settle with — report the total spend only.

## Read the ledger

```bash
sqlite3 ~/.hermes/data/oteny-travel-talent/trips.db "SELECT e.id, COALESCE(m.display_name,'owner') AS payer, e.amount, e.currency, e.category, e.note FROM expenses e LEFT JOIN members m ON m.id=e.payer_member_id WHERE e.trip_id=<trip_id> ORDER BY e.id;"
```

## Notes

- **Correct an entry**: `UPDATE expenses SET amount=… WHERE id=<id>;` (guarded by id),
  then re-run `settle_up.py`.
- **Mixed currencies** settle independently — say so rather than silently converting; offer
  to convert at a rate the tenant gives if they want a single figure.
- **Never invent a balance.** Always run `settle_up.py` this turn and quote it; if a member
  map is incomplete, surface that ("I don't know who 'J' is — add them first") rather than
  guessing.
