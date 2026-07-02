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

## 0003_cron_localtime (checklist)

Re-registers the three reminder cron jobs. Two things changed and both need the jobs
rebuilt (a converge swaps the Talent files but never re-plans live crons):

1. **Schedule timezone.** Hermes' scheduler evaluates a cron expression in the tenant's
   *configured* timezone (`config.yaml` `timezone:`), **not** UTC. The old planner
   converted the wall-clock time to UTC, so a `20:00` reminder was written as `0 18 * * *`
   and then read as **18:00 local** — firing 2 h early in CEST summer (1 h in winter). The
   planner now writes the schedule in **local wall-clock** verbatim (DST-invariant).
2. **Cost reshape.** The daily morning/evening jobs are now a **single cheap `lite`
   nudge** — no skill load, no DB read, no scripts (the full food-tracker wrap-up runs on
   the tenant's *reply*, via the channel prompt). Each job pins its declared per-job model.

Cron jobs live in `~/.hermes/cron/jobs.json` + the in-process scheduler, not in `food.db`,
so this is a **checklist** you run via the `cronjob` tool — `migrate.py` can't do it. Steps:

1. **Delete** the three existing jobs via the `cronjob` tool (by exact name):
   `OtenyFlatBellyTalent daily morning log`, `OtenyFlatBellyTalent daily evening log`,
   `OtenyFlatBellyTalent weekly dashboard`.
2. **Re-plan** — run the planner; with the old jobs gone it now lists all three as absent
   with the corrected specs:
   ```
   python3 ~/.hermes/skills/talents/oteny-flatbelly-talent/scripts/provision_cron.py --json
   ```
3. **Create** each job in `to_create` via the `cronjob` tool, passing **every** field the
   planner gave (name, the local `schedule`, `skills`, `model`, `provider`, `prompt`, and
   `enabled_toolsets` where present). Do not re-derive or UTC-convert the schedule.
4. **Record** it: `migrate.py --mark 0003_cron_localtime`.
