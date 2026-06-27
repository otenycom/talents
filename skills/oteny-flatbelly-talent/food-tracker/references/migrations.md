# Migrations — reconciling the food.db when the Talent is upgraded

A new version of this Talent can change the *shape* of the `food.db` it owns. A converge
swaps the files but leaves the live db untouched, so the agent reconciles the db **in-box**
from the ordered list in `migrations.yaml`. This is automatic and safe: on every load the
preflight/selfcheck surfaces a `MIGRATIONS: pending — …` line, and the food-tracker triage
runs the pending migrations **before** it plans the turn (even on an already-set-up box).

Run the deterministic ones with the declared runner; never hand-edit the db.

```
python3 ~/.hermes/skills/talents/oteny-flatbelly-talent/scripts/migrate.py --status
python3 ~/.hermes/skills/talents/oteny-flatbelly-talent/scripts/migrate.py --apply 0002_food_macros
```

`--apply` runs an `sql` migration and records it; it is idempotent, so re-running an
already-applied one is a safe no-op. A migration that needs your judgement (a `checklist`
kind — e.g. re-planning cron jobs, which only you can do via the cronjob tool) is run by
following its section here and then recorded with `migrate.py --mark <id>`.

## 0002_food_macros (sql)

Adds a `food_macros` rollup table — one row per day holding that day's total `protein_g`,
`carbs_g`, `fat_g`, and `calories` — and backfills it from the existing `meals` rows. This
lets a macro question read one summarized row per day instead of re-summing meals each turn.
It is additive: the `meals`, `weight`, `daily_metrics`, `workouts`, and `waist` tables and
all their rows are preserved untouched. Apply it with `migrate.py --apply 0002_food_macros`.
