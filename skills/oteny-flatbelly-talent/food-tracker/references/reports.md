# food-tracker — Reports & Read Queries

Canonical catalog of read queries. Schema in `datamodel.md`; write playbooks in
`playbooks.md`. DB path: `~/.hermes/data/oteny-flatbelly-talent/food.db`. Goal weight and protein target
are read from `~/.hermes/data/oteny-flatbelly-talent/profile.yaml` — substitute `<profile.goal_weight_kg>`
and `<profile.protein_target_g>`, never a baked number.

## ⚠️ Two hard rules while reporting

1. **No vibe-served facts.** Run the query in the *same turn*. Never quote a
   number/delta/trend from memory.
2. **Morning-only filter for weight trends.** Anything fitting a slope must filter to
   `COALESCE(period,'morning') = 'morning'` — the canonical, language-independent
   column, never the free-text `notes`.

## 1. Today: meals + totals + leucine compliance

```sql
SELECT meal_type, food, calories, protein_g, leucine_g
  FROM meals WHERE date=date('now')
  ORDER BY CASE meal_type WHEN 'breakfast' THEN 1 WHEN 'lunch' THEN 2
                          WHEN 'snack' THEN 3 WHEN 'dinner' THEN 4 END, id;
```
```sql
SELECT meal_type, ROUND(SUM(calories),0) AS kcal, ROUND(SUM(protein_g),1) AS p_g,
       ROUND(SUM(leucine_g),2) AS leu_g,
       CASE WHEN SUM(leucine_g) >= 2.5 THEN 'OK' ELSE 'LOW' END AS mps
  FROM meals WHERE date=date('now') GROUP BY meal_type ORDER BY meal_type;
```
```sql
SELECT ROUND(SUM(calories),0) AS kcal, ROUND(SUM(protein_g),1) AS p_g,
       ROUND(SUM(carbs_g),1) AS c_g, ROUND(SUM(fat_g),1) AS f_g,
       ROUND(SUM(leucine_g),2) AS leu_g FROM meals WHERE date=date('now');
```

**Framing rules:** before ~18:00 local call it "so far today" and show "X g protein
to go for the <profile.protein_target_g> g target"; after the window closes call it
"day total" and surface deficits and leucine misses. Render OK/LOW as ✅/⚠️ only in
the reply, never inside the SQL.

## 2. Today: full-picture dashboard (every table joined on date)

```sql
SELECT d.date,
  (SELECT weight_kg FROM weight w WHERE w.date=d.date)              AS weight_kg,
  (SELECT ROUND(SUM(calories),0)  FROM meals m WHERE m.date=d.date) AS kcal_in,
  (SELECT ROUND(SUM(protein_g),1) FROM meals m WHERE m.date=d.date) AS protein_g,
  (SELECT ROUND(SUM(leucine_g),2) FROM meals m WHERE m.date=d.date) AS leucine_g,
  d.steps, d.active_kcal, d.sleep_consistency_score AS sleep_score, d.eating_window_hours,
  (SELECT GROUP_CONCAT(workout_type||'/'||COALESCE(duration_minutes,'?')||'min', ', ')
     FROM workouts wk WHERE wk.date=d.date)                         AS workouts,
  (SELECT waist_cm FROM waist wa WHERE wa.date=d.date)              AS waist_cm
FROM daily_metrics d WHERE d.date=date('now');
```

## 3. Weight trend — full-period + 7-day slopes (morning-only)

Always report **both** windows. Sustained fat loss settles around **0.5–1.0% of body
weight per week** (≈ `current_kg × 0.005` to `× 0.01`); leaner bodies and recomposition
sit at the lower end. Compare the printed kg/week against that personalized band, not a
fixed kg target.

```python
import sqlite3, os
from datetime import date
DB = os.path.expanduser("~/.hermes/data/oteny-flatbelly-talent/food.db")
GOAL = <profile.goal_weight_kg>
con = sqlite3.connect(DB)
rows = con.execute("""
    SELECT date, weight_kg FROM weight
    WHERE COALESCE(period,'morning') = 'morning'
    ORDER BY date ASC""").fetchall()

def slope(data):
    if len(data) < 2: return None
    xs = [(date.fromisoformat(d) - date.fromisoformat(data[0][0])).days for d,_ in data]
    ys = [w for _,w in data]
    n=len(xs); mx=sum(xs)/n; my=sum(ys)/n
    return sum((x-mx)*(y-my) for x,y in zip(xs,ys)) / sum((x-mx)**2 for x in xs)

full, last7, last30 = slope(rows), slope(rows[-7:]), slope(rows[-30:])
current = rows[-1][1]
eta = (current - GOAL) / -last7 if last7 and last7 < 0 else None
print(f"current: {current} kg ({rows[-1][0]})")
print(f"full-period: {full*7:+.2f} kg/week  ({full*30.44:+.2f} kg/month, n={len(rows)})")
print(f"last-30-day: {last30*7:+.2f} kg/week")
print(f"last-7-day:  {last7*7:+.2f} kg/week")
if eta: print(f"ETA to {GOAL} kg at last-7 pace: {eta:.0f} days")
```

Anything faster than ~1.5% of body weight per week (≈ `current_kg × 0.015`) in week 4+
is mostly water or under-eating — flag it.

## 4. Week summary (last 7 days)

```sql
SELECT date, ROUND(SUM(calories),0) AS kcal, ROUND(SUM(protein_g),1) AS p_g,
       ROUND(SUM(leucine_g),2) AS leu_g, COUNT(*) AS items
  FROM meals WHERE date >= date('now','-6 day') GROUP BY date ORDER BY date;
```
```sql
SELECT date, weight_kg, notes FROM weight
  WHERE date >= date('now','-6 day') AND COALESCE(period,'morning') = 'morning'
  ORDER BY date;
```

## 5. Leucine compliance — % of meal groups clearing the threshold (rolling 14 days)

```sql
WITH per_meal AS (
  SELECT date, meal_type, SUM(leucine_g) AS leu FROM meals
   WHERE date >= date('now','-13 day') GROUP BY date, meal_type)
SELECT date, COUNT(*) AS meal_groups,
       SUM(CASE WHEN leu >= 2.5 THEN 1 ELSE 0 END) AS clearing,
       ROUND(100.0*SUM(CASE WHEN leu >= 2.5 THEN 1 ELSE 0 END)/COUNT(*),0) || '%' AS pct
  FROM per_meal GROUP BY date ORDER BY date;
```

## 6. Protein pace (front-loading check)

```sql
SELECT meal_type, ROUND(AVG(p_per_day),1) AS avg_protein_g FROM (
  SELECT date, meal_type, SUM(protein_g) AS p_per_day FROM meals
    WHERE date >= date('now','-13 day') GROUP BY date, meal_type) GROUP BY meal_type;
```

## 7. Eating window over time

```sql
SELECT date, first_meal_time, last_meal_time, eating_window_hours FROM daily_metrics
  WHERE eating_window_hours IS NOT NULL AND date >= date('now','-13 day') ORDER BY date;
```

## 8. Sleep trend

```sql
SELECT date, sleep_consistency_score AS score, sleep_hours, notes FROM daily_metrics
  WHERE date >= date('now','-13 day') AND sleep_consistency_score IS NOT NULL ORDER BY date DESC;
```
```sql
SELECT ROUND(AVG(sleep_consistency_score),1) AS avg_score,
  SUM(CASE WHEN sleep_consistency_score >= 90 THEN 1 ELSE 0 END) AS very_high,
  SUM(CASE WHEN sleep_consistency_score BETWEEN 80 AND 89 THEN 1 ELSE 0 END) AS high,
  SUM(CASE WHEN sleep_consistency_score BETWEEN 60 AND 79 THEN 1 ELSE 0 END) AS ok_,
  SUM(CASE WHEN sleep_consistency_score < 60 THEN 1 ELSE 0 END) AS low
FROM daily_metrics WHERE date >= date('now','-13 day');
```

## 9. Workout frequency

```sql
SELECT workout_type, COUNT(*) AS sessions, ROUND(SUM(duration_minutes)/60.0,1) AS hours
  FROM workouts WHERE date >= date('now','-13 day') GROUP BY workout_type;
```

## 10. Multi-week protocol progress ("where am I in the campaign")

```sql
WITH morning AS (SELECT date, weight_kg FROM weight
   WHERE COALESCE(period,'morning') = 'morning')
SELECT (SELECT weight_kg FROM morning ORDER BY date ASC LIMIT 1)  AS start_kg,
       (SELECT date      FROM morning ORDER BY date ASC LIMIT 1)  AS start_date,
       (SELECT weight_kg FROM morning ORDER BY date DESC LIMIT 1) AS current_kg,
       ROUND((SELECT weight_kg FROM morning ORDER BY date ASC LIMIT 1)
           - (SELECT weight_kg FROM morning ORDER BY date DESC LIMIT 1),1) AS total_drop_kg;
```

Pair with today's waist (if logged) and, when the tenant has supplied a
`health-baseline.md`, their own milestones (e.g. an expected liver-marker improvement
at a milestone weight) — never a baked lab value.

## 11. Quick DB health-check queries

```sql
SELECT date, weight_kg, period, notes FROM weight
  WHERE period = 'evening' ORDER BY date DESC LIMIT 20;
```
```sql
SELECT date, meal_type, food, protein_g FROM meals WHERE leucine_g IS NULL ORDER BY date DESC LIMIT 20;
```
```sql
SELECT 'meals' t, COUNT(*) FROM meals
UNION ALL SELECT 'weight', COUNT(*) FROM weight
UNION ALL SELECT 'daily_metrics', COUNT(*) FROM daily_metrics
UNION ALL SELECT 'workouts', COUNT(*) FROM workouts
UNION ALL SELECT 'waist', COUNT(*) FROM waist;
```
