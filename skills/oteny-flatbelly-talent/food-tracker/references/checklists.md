# food-tracker — Per-Intent Checklists (the operator manual)

Step-by-step for **one message**, after the master triage in
[`SKILL.md`](../SKILL.md) ("Every message — triage first") has classified the intent.
Follow the matching section top to bottom — **don't skip steps, don't improvise**.
These checklists *orchestrate* the mechanics: SQL writes are in
[`playbooks.md`](playbooks.md), read queries in [`reports.md`](reports.md), the schema
in [`datamodel.md`](datamodel.md). When a step says "§N" it means that file's section.

**Every checklist obeys the three hard rules** (full text in `SKILL.md`): ① no
vibe-served facts — read the DB this turn and quote the numbers; ② trends use
morning-only weights; ③ check time-of-day before calling the day "done". And every
write follows the **one-sqlite3-call-per-INSERT, verify-with-a-separate-SELECT** rule
(`playbooks.md` §0/§14).

---

## §1 MEAL ENTRY  (the most common path)

**A. Data entry**
1. Split the message into individual food **items + quantities** (e.g. "3 eggs and
   100g tuna" = two items).
2. For each item, estimate `calories / protein_g / carbs_g / fat_g` from the **Macro
   defaults** table (or a tenant **shorthand**, `SKILL.md`), and compute
   `leucine_g = protein_g × ratio` from the **Leucine estimation** table.
3. Set `meal_type` by **time of day** (pre-flight clock): before ~18:00 default
   `snack`/`lunch`, **never `dinner`**; after ~18:00 or if stated, `dinner`.
4. Write **one INSERT per item** (`playbooks.md` §1/§2), each with the assumption in
   `notes`. One `sqlite3` call per statement — never chain INSERT+SELECT.
5. **Verify** with a separate SELECT (`playbooks.md` §14).

**B. Analysis**
6. Query **today's totals** and the **per-meal leucine compliance** (`reports.md`
   §1/§5, or the leucine query in `SKILL.md`).
7. Compare to targets: `profile.protein_target_g` (how many g protein still to go) and
   the **leucine threshold per protein-anchored meal** (which meals cleared, which are
   LOW).
8. Apply hard rule ③: before ~18:00 frame as **"so far today"** with "X g protein to
   go"; do not declare a deficit or "day total".

**C. Reply**
9. Compact, Telegram-friendly; **macros spelled out** (`82 g protein`, never `82 g P`).
10. **Quote the source numbers** you just read (hard rule ①).
11. **Pitch jargon to how settled the tenant is** (`glossary.md` fade ladder): newcomers
    get plain words + why it matters; settling tenants the term + a short tag; settled
    regulars the term bare. Never a bare `leucine 6.7 g ✅` to a newcomer; drop to plain
    words if they ask.
12. If a meal is LOW on leucine or protein is behind, give **one** concrete lever (a
    whey scoop, eggs, Greek yoghurt, a slice of chicken). Render `OK`/`LOW` as ✅/⚠️
    only in the reply, never inside SQL.
13. Reply in the tenant's language.

## §2 WEIGHT ENTRY
1. Classify **morning vs evening** from the tenant's words in any language → set
   `period` (`playbooks.md` §4/§5). Unstated + fasted ⇒ `morning`.
2. Write it (UPSERT on `date`); an evening reading must **not** overwrite a morning one.
3. **Only if morning:** recompute the trend (`reports.md` §3, morning-only filter) —
   report the delta vs the **prior morning** (quote both numbers, e.g. "107.5 → 106.9 =
   −0.6 kg") and both the full-period and last-7-day slopes.
4. Sanity: a swing faster than ~1.5% of body weight/week in week 4+ is water /
   under-eating — flag, don't celebrate it. Never compute a trend on evening weights.
5. Reply with the number + trend, in the tenant's language.

## §3 SLEEP ENTRY
1. Write the composite Apple-Watch **sleep score (0–100)** to
   `daily_metrics.sleep_consistency_score` (`playbooks.md` §6); store
   `sleep_hours`/`bedtime`/`wake_time` too if a sub-score is given.
2. Reply with the score's band and **one** sleep lever (consistent bedtime ±30 min,
   7.5–8h). Tie it to the goal: **sleep is the highest VAT lever** — short/irregular
   sleep raises visceral fat (`fat-loss-protocol`).

## §4 STEPS ENTRY
1. Write `steps` (+ `active_kcal` if given) to `daily_metrics` (`playbooks.md` §7,
   preserving any existing note).
2. Reply with progress vs the **7–10k step** baseline and the **daily 60-min walk**
   anchor (a 60-min walk ≈ 6–8k steps).

## §5 WORKOUT ENTRY
1. Classify `workout_type` = `resistance` / `hiit` / `walk` (`playbooks.md` §8). Many
   per day allowed.
2. Write it; put detail (muscle groups, distance) in `notes`.
3. Reply: acknowledge it; if it's a **walk ≥ 60 min**, credit the daily-walk anchor; if
   resistance, note the 3×/wk / each-muscle-2× target; nudge the weekly cardio balance
   if a lever is missing.

## §6 WAIST ENTRY  (the primary health metric)
1. Write `waist_cm` with `profile.height_cm` (`playbooks.md` §9); `whtr` auto-computes.
2. Read back the **WHtR**; compare to the **< 0.5** target and to the prior reading.
3. Reply with the WHtR value, what band it's in (< 0.4 too low · 0.4–0.49 healthy ·
   0.5–0.59 raised · ≥ 0.6 high), and the trend — this is the headline success metric,
   above the scale (`fat-loss-protocol` → "Deriving the natural path").

## §7 EXPLAIN  ("explain" / "why" / "what is")
Per `SKILL.md` "Explain mode": ① **anchor to today's actual DB numbers**, not a
textbook; ② reply in the tenant's language — keep the technical word (mTOR/leucine) but
**define it in plain words** (`glossary.md`), never assume they know it; ③ tie the
science to **their** goal; ④ end with **one** concrete next lever. Load
[`fat-loss-protocol`](../../fat-loss-protocol/SKILL.md) for the method, its
`references/why-visceral-fat.md` for "why visceral fat matters", and
`references/research-dossier.md` for a citation. **No vibe-served evidence** — cite or
say "let me check".

## §8 DASHBOARD  ("progress" / "chart" / "dashboard")
1. Run `weight-progress-dashboard/scripts/generate.py` (reads `food.db` + `profile.yaml`).
2. Deliver the PNG by putting `MEDIA:<printed path>` in the reply.
3. Caption per that skill's rules: headline (kg lost + % to goal) + 3–4 bullets; validate
   the 7-day pace is in the **0.5–1.0% of body weight/week** band. Ground every number
   in the DB read (hard rule ①). If < 2 morning weights, send "not enough data yet".

## §9 TALK  (on-topic but no data to log)
A coaching question, an objection, a craving, "I feel stuck". Load
[`flatbelly-coach-voice`](../../flatbelly-coach-voice/SKILL.md) and answer warmly, briefly, in
voice. **Write nothing.** If the tenant volunteered a diagnosis, honor the safety
boundary (`../../references/safety-boundaries.md`) — reflect only what they shared, never
invent a fact, and escalate on a red flag.

---

### After any branch — final check (every reply)
- Did I **read the DB this turn** and quote real numbers? (no vibe-served facts)
- Did I use **morning-only** weights for any trend?
- Did I respect **time-of-day** (no "day total" before the day is done)?
- Did I pitch any jargon (leucine, mTOR, WHtR…) **to how settled the tenant is** — plain
  for newcomers, fading to bare for regulars, and plain again if they ask? (`glossary.md`)
- Is the reply compact, macros spelled out, in the tenant's language, with **one** clear
  next step?
