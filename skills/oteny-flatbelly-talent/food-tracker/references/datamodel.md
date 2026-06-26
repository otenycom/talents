# food-tracker — Data Model Reference

Canonical reference for the SQLite schema at `~/.hermes/data/oteny-flatbelly-talent/food.db`.
For *how* to write/read, see `playbooks.md` and `reports.md`. The DB path is the
namespaced per-tenant location — resolve it from the one constant, never hardcode a
home directory.

## Tables at a glance

| Table | Cardinality | Unique key | What goes here |
|---|---|---|---|
| `meals` | many per day | none (id only) | One row per food item eaten |
| `weight` | 1 per day | `date` | Daily fasted weight (morning preferred — see hard rule) |
| `daily_metrics` | 1 per day | `date` | Sleep score, steps, eating window, active kcal, behavior flags |
| `workouts` | many per day | none (id only) | One row per training session |
| `waist` | 1 per day | `date` | Waist circumference + WHtR (generated) |

## Columns (canonical)

The **executable** schema is the single shipped file `../../scripts/init.sql` (applied
idempotently at first-run: `sqlite3 …/food.db < …/scripts/init.sql`). Never paste a
`CREATE TABLE` block — this doc describes the columns; `init.sql` creates them.

**`meals`** (many per day; `idx_meals_date` on `date`)
- `id` PK · `date` TEXT `YYYY-MM-DD` · `meal_type` ∈ breakfast/lunch/dinner/snack ·
  `food` TEXT · `calories` INT · `protein_g`/`carbs_g`/`fat_g`/`leucine_g` REAL ·
  `notes` TEXT (quote the assumption used).

**`weight`** (1 per day; `date` UNIQUE)
- `id` PK · `date` · `weight_kg` REAL · `period` ∈ {`morning`,`evening`,NULL}
  (canonical, language-independent — the morning-only trend filter relies on it, **not**
  on `notes`) · `notes` TEXT (free text, NOT time-of-day).

**`daily_metrics`** (1 per day; `date` UNIQUE; `idx_daily_metrics_date`)
- `id` PK · `date` · `steps` INT · `first_meal_time`/`last_meal_time`/`bedtime`/
  `wake_time` TEXT `HH:MM` · `eating_window_hours`/`sleep_hours` REAL ·
  `sleep_consistency_score` INT (composite Apple Watch 0–100 — see ⚠️ below) ·
  `alcohol`/`processed_foods` INT 0/1 flags · `dark_berries_cups` REAL ·
  `active_kcal` INT (Apple Watch active energy) · `notes` TEXT.

**`workouts`** (many per day; `idx_workouts_date`)
- `id` PK · `date` · `workout_type` ∈ resistance/hiit/walk · `duration_minutes` INT ·
  `muscle_groups` TEXT ('full body' | 'push' | 'pull' | 'legs' | 'zone 2' | …) ·
  `notes` TEXT.

**`waist`** (1 per day; `date` UNIQUE; `idx_waist_date`)
- `id` PK · `date` · `waist_cm` REAL · `height_cm` REAL (from `profile.height_cm`) ·
  `whtr` REAL generated `waist_cm / height_cm` STORED · `notes` TEXT. Target band **< 0.5**.

## ⚠️ Column conflations to know

### `daily_metrics.sleep_consistency_score` stores the **composite** Apple Watch sleep score (0–100), not the bedtime sub-score
The column was named for the /30 bedtime sub-score but is used for the composite.
**Always include `notes`** spelling out "composite Apple Watch sleep score N (band)"
so analytics can distinguish. A proper fix is a dedicated `sleep_score INTEGER`
column; flag it if analytics need it.

### `daily_metrics.active_kcal` is the Apple Watch active-energy reading
Total daily expenditure on top of BMR. **Not** TDEE. Don't confuse with
`meals.calories` (intake side).

## What goes where — input → table decision tree

When the tenant pastes mixed content (a typical message is `date / weight / sleep /
meals`), parse each line and route:

| Input pattern | Table | Column(s) |
|---|---|---|
| `103.7 kg`, `weight 105`, `gewogen 104.3` | `weight` | `weight_kg`, `period='morning'` (default) or `'evening'` (classify from the tenant's words, any language) |
| `sleep 94`, `slaapscore 91` | `daily_metrics` | `sleep_consistency_score` + notes |
| `8500 steps`, `12k stappen` | `daily_metrics` | `steps` |
| `850 active kcal` | `daily_metrics` | `active_kcal` |
| `45min strength`, `60min HIIT`, `walk 30min` | `workouts` | row per session |
| `waist 110cm`, `taille 108` | `waist` | `waist_cm` (+ `height_cm` from profile) |
| any food | `meals` | one row per item (or per shorthand) |
| `alcohol`, `1 glass of wine` | `meals` row **and** `daily_metrics.alcohol=1` |
| `bedtime 23:30 / up 7:00` | `daily_metrics` | `bedtime`, `wake_time`, derive `sleep_hours` |

**Date parsing** (support the tenant's language; Dutch shorthands shown):
- `vandaag`/`today` → `date('now')` (local — check `TZ=<profile.timezone> date`)
- `gisteren`/`yesterday` → `date('now','-1 day')`
- `eergisteren` → `date('now','-2 days')`
- explicit dates ("5 juni" / "June 5") → that date, current year unless it implies a
  flip. Always confirm the parsed date in the reply when it isn't today.

## Conventions

### `meals.notes` — quote your assumption
Record the protein default / grade / portion assumption used, e.g.
`'~15% fat minced beef'`, `'skyr 0% natural'`, `'3×70 kcal boiled + ~40 kcal pan
olive oil, egg leucine 8.7%'`, `'shorthand expansion'`. Makes corrections trivially
`UPDATE`-able.

### `weight.period` — encode time-of-day (canonical, language-independent)
Set `period` to `'morning'` or `'evening'`, classified from the tenant's words in
**any** language ("this morning"/"ochtend"/"matin"/"fasted" → `'morning'`;
"tonight"/"avond"/"after dinner" → `'evening'`). **The morning-only trend filter
relies on this column, not on `notes`** (note text only works in one language). When
unstated, a fasted weigh defaults to `'morning'`; the filter treats NULL as morning.

### `daily_metrics.notes` — always include the band for composite sleep
Required format: `"composite Apple Watch sleep score N (band)"` where band ∈ {Very
Low, Low, OK, High, Very High}. Extras after a `;` separator.

### Upserts everywhere a `date UNIQUE` exists
For `weight`, `daily_metrics`, `waist` always use `ON CONFLICT(date) DO UPDATE SET …`.
Tenants frequently re-log the same day later.

```sql
INSERT INTO weight (date, weight_kg, period, notes) VALUES ('2026-06-05', 103.7, 'morning', 'fasted')
  ON CONFLICT(date) DO UPDATE SET weight_kg=excluded.weight_kg, period=excluded.period, notes=excluded.notes;
```

## Foreign-key map (logical, not enforced)

No FK constraints. The implicit join key is always `date`:
`meals.date` ↔ `daily_metrics.date` ↔ `weight.date` ↔ `workouts.date` ↔ `waist.date`.
For a "complete picture of a day", LEFT JOIN everything on `date`.

## Common derived columns / calcs (compute on read)

| Quantity | Formula | Where |
|---|---|---|
| BMR | Mifflin-St Jeor from `profile.sex/age/height_cm` + current weight | compute; never bake a constant |
| TDEE estimate | BMR + `active_kcal` | per day |
| Kcal balance | `SUM(meals.calories) − TDEE` | daily deficit signal |
| Leucine pass/fail | `SUM(leucine_g) >= profile.leucine_threshold_g` per meal_type | `reports.md` |
| WHtR risk band | <0.5 healthy, 0.5–0.6 elevated, >0.6 high | `waist` generated column |
| Morning-only weight slope | linear regression filtered to `COALESCE(period,'morning')='morning'` | `reports.md` — **hard rule** |

## Adding a new column / migration playbook

1. `ALTER TABLE <t> ADD COLUMN <name> <type>;`
2. Update this schema block and the "Tables at a glance" row.
3. Add at least one INSERT example to `playbooks.md`.
4. Update `reports.md` if the column should appear in summaries.
5. Backfill historical rows where possible.
6. Note the migration date so the conflation/origin is traceable.
