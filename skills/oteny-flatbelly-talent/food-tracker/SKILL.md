---
name: food-tracker
description: "Log meals, weight, macros, sleep, workouts, waist."
version: 1.2.0
author: Oteny
license: MIT
metadata:
  hermes:
    tags: [food, nutrition, weight, macros, leucine, sqlite, tracker, oteny-flatbelly-talent]
    related_skills: [flatbelly-onboarding, fat-loss-protocol, flatbelly-coach-voice, weight-progress-dashboard]
---

# food-tracker (OtenyFlatBellyTalent engine)

The **engine** for the flat-belly coach: daily meal/macro/calorie, weight, sleep,
workout, steps and waist logging in a per-tenant SQLite database at
`~/.hermes/data/oteny-flatbelly-talent/food.db`. This skill carries the triage, the hot
write paths, and the hard rules; the detail lives in `references/` (loaded on demand
via `skill_view(name='food-tracker', file_path='references/<file>')`). The coaching
*voice* is [`flatbelly-coach-voice`](../flatbelly-coach-voice/SKILL.md); the
*method/evidence* is [`fat-loss-protocol`](../fat-loss-protocol/SKILL.md); the
*visual* is [`weight-progress-dashboard`](../weight-progress-dashboard/SKILL.md).

> **The product rule:** this skill carries the **method**; the tenant's
> `~/.hermes/data/oteny-flatbelly-talent/profile.yaml` carries the **person**. Never bake a
> body, a lab value, a goal weight, or a personal shorthand here — read them from the
> profile. Reply in the tenant's language (`profile.language`, default English).

## 🧭 Quick-reference index (load on demand)

The triage + the three hard rules below are all you hold per turn. Everything else
is a `references/` file you pull **only when you hit that need**:

| Need to… | Load |
|---|---|
| **Set the bot up** (selfcheck said NOT-READY) | `references/first-run.md` |
| **Step-by-step per-intent checklist** (sleep/steps/workout/waist/explain/dashboard) | `references/checklists.md` |
| **Exact write SQL** — meal/weight/sleep/workout/waist, correct/undo/bulk import | `references/playbooks.md` |
| **Report queries** — today/week/trend/leucine/sleep/workout/progress | `references/reports.md` |
| **Macro defaults + leucine ratios + the tenant's shorthands** | `references/food-defaults.md` |
| **Plain-language meaning of any jargon** (leucine, mTOR, WHtR…) + the fade ladder | `references/glossary.md` |
| **Full schema + column conflations + input→table routing** | `references/datamodel.md` |
| The fat-loss method + the RCT evidence | [`fat-loss-protocol`](../fat-loss-protocol/SKILL.md) |
| Coaching voice, objection handling, NAFLD framing | [`flatbelly-coach-voice`](../flatbelly-coach-voice/SKILL.md) |
| Medical safety boundary (red flags, disclaimers) | read `~/.hermes/skills/talents/oteny-flatbelly-talent/references/safety-boundaries.md` (a bundle-level file — open it with the file tool; not a `skill_view` target of this skill) |

## 🚦 Every message — triage first (run in order, every time)

Do **not** improvise. (Skip to "Daily reminder role" only when a reminder cron fires.)

1. **One context call.** The per-turn probe returns setup-readiness, the local clock,
   today's logged rows, the tenant's `memory.md` preferences, and the profile targets
   in a **single** declared call:

   ```bash
   python3 ~/.hermes/skills/talents/oteny-flatbelly-talent/scripts/preflight.py
   ```

   - `READY: yes` → you now hold the clock (hard rule ③), today's rows, prefs and
     targets. **Don't** separately `cat` profile/memory, re-check the clock, or re-list
     today — preflight gave you all of it this turn. Go to step 2.
   - `READY: no` → setup is incomplete (a genuine first-run gap). Load
     `references/first-run.md` and follow it (declared scripts only). **Do not coach until READY.**
   - `UNKNOWN: …` → an **environment fault** (a file is present but unreadable, a corrupt db) —
     **NOT** a fresh tenant. **Do NOT onboard, do NOT coach, and do NOT re-run the intake or
     re-create the db** (that would overwrite the owner's real — currently unreadable — data).
     Report the one-line problem to the owner and stop.

2. **Is this for the coach?** **YES** if it mentions: a food/meal/drink, calories or
   macros, a body weight/weigh-in, sleep, steps or active energy, a workout/walk, a
   waist measurement, a health goal, "explain/why/what is", "progress/chart", **or**
   it's a reply to one of my reminders. **NO** (chit-chat, off-topic) → reply briefly
   in-voice, **write nothing**. **Unsure** → ask one short question first.

3. **Classify the intent(s) and handle each, in table order.** MEAL and WEIGHT are
   inlined below; for the rest, load the referenced file **only** for the intent you hit:

   | The message contains… | Intent | How |
   |---|---|---|
   | a food / meal / drink eaten | MEAL | **§MEAL below** |
   | a body weight / weigh-in | WEIGHT | **§WEIGHT below** |
   | a sleep score or hours | SLEEP | `references/checklists.md` §3 |
   | steps / active energy | STEPS | `references/checklists.md` §4 |
   | a workout / walk | WORKOUT | `references/checklists.md` §5 |
   | a waist measurement | WAIST | `references/checklists.md` §6 |
   | "explain" / "why" / "what is" | EXPLAIN | `references/checklists.md` §7 |
   | "progress" / "chart" / "dashboard" | DASHBOARD | `references/checklists.md` §8 |
   | a method / evidence question | METHOD Q&A | [`fat-loss-protocol`](../fat-loss-protocol/SKILL.md) |
   | a correction / undo of an entry | FIX | `references/playbooks.md` §11–12 |
   | a possible medical red flag | SAFETY | read the safety-boundaries file (index above) |
   | none of the above, on-topic | TALK | `references/checklists.md` §9 |

4. **The three hard rules apply to every reply** (below): no vibe-served facts,
   morning-only weight trends, time-of-day before calling the day "done".
5. **Verify & reply.** After any write, run the verification SELECT (`playbooks.md`
   §14) in a **separate** call; reply compact + Telegram-friendly, macros spelled out,
   in the tenant's language, quoting the numbers you just read, ending with **one**
   concrete next lever if off-target.

### §MEAL — meal entry (the common path)

1. Split the message into **items + quantities** ("3 eggs and 100g tuna" = two items).
2. Per item, estimate `calories / protein_g / carbs_g / fat_g` from the macro table in
   `references/food-defaults.md` (or a tenant shorthand); compute `leucine_g =
   protein_g × ratio` from the leucine ratios there.
3. `meal_type` by the **preflight clock**: before ~18:00 default `snack`/`lunch`
   (**never `dinner`**); after ~18:00 or if stated, `dinner`.
4. Write **one INSERT per item** (assumption in `notes`) — one `sqlite3` call per
   statement, **never** chain INSERT+SELECT (a mid-call error lands the INSERT but
   errors the call; a blind retry double-inserts). Exact SQL: `references/playbooks.md`
   §1–3. The single-item shape:

   ```bash
   sqlite3 ~/.hermes/data/oteny-flatbelly-talent/food.db "INSERT INTO meals (date, meal_type, food, calories, protein_g, carbs_g, fat_g, leucine_g, notes) VALUES (date('now'),'snack','3 fried eggs (L)',250,18,0,17,1.57,'egg leucine 8.7%; ~40 kcal pan oil');"
   ```

5. **Verify** with a separate `SELECT`, then read today's totals + per-meal leucine
   (`references/reports.md` §1, §5). Before ~18:00 frame as "so far today" with "X g
   protein to go" — don't declare a day total/deficit.
6. **Reply:** macros spelled out, **quote** the numbers you read, pitch jargon to how
   settled the tenant is (`references/glossary.md` ladder), give **one** lever if a
   protein-anchored meal is LOW on leucine.

### §WEIGHT — weight entry

1. Classify **morning vs evening** from the tenant's words in any language → set
   `period` (unstated + fasted ⇒ `morning`). An evening reading must **not** overwrite a
   morning one (`references/playbooks.md` §4–5). The shape:

   ```bash
   sqlite3 ~/.hermes/data/oteny-flatbelly-talent/food.db "INSERT INTO weight (date, weight_kg, period, notes) VALUES (date('now'),103.7,'morning','fasted') ON CONFLICT(date) DO UPDATE SET weight_kg=excluded.weight_kg, period=excluded.period, notes=excluded.notes;"
   ```

2. **Only if morning:** recompute the trend **morning-only** (`references/reports.md`
   §3) — quote the prior morning + delta ("107.5 → 106.9 = −0.6 kg") and report both
   the full-period and last-7-day slopes. **Never** trend on evening weights.
3. Reply with the number + trend, in the tenant's language.

## ⚠️ HARD RULE: Morning weights only for trend math

The `weight` table mixes morning and evening entries; the **`period`** column
disambiguates (**not** the free-text `notes` — that would only work in one language).
Classify the entry from the tenant's words in **any** language at write time; when
unstated, a fasted weigh defaults to `'morning'`. For any trend (slope, kg/week,
ETA-to-goal) **filter to morning only**: `WHERE COALESCE(period,'morning') = 'morning'`
(NULL counts as morning). Evening weights run 0.5–1.5 kg higher and inflate the loss
rate. Always report **both** full-period and last-7-day slopes — the first 2–3 weeks
are water/glycogen-dominated; sustained loss settles around **0.5–1.0% of body weight
per week**. Slope code: `references/reports.md` §3; per-body-type rate logic:
[`fat-loss-protocol`](../fat-loss-protocol/SKILL.md) ("Deriving the natural path").

## ⚠️ HARD RULE: Check time-of-day before framing the day as "done"

Check local time (preflight gives it; else `TZ=<profile.timezone> date +'%H:%M %A'`)
before calling totals a "day total", declaring a deficit, assigning
`meal_type='dinner'` to a late-afternoon item, or writing closed-window coaching.
Before ~18:00 the day is in progress: frame as "so far today" / "X g protein to go",
default the latest item to `snack`/`lunch` unless after ~18:00 or stated as dinner.

## ⚠️ HARD RULE: No vibe-served facts

**Never state a number, delta, trend or comparison without reading it from the
database in the same turn.** No "holding steady" / "down a bit" without a fresh query.
Query the prior value(s), compute the delta from the returned numbers, and quote the
source values ("107.5 → 106.9 = −0.6 kg"). If you have not queried this turn, say "let
me check" and run it.

## ⚠️ HARD RULE: Never hunt for a file — run the path you're given

Every script and the database are at the **absolute paths written in this skill**
(`~/.hermes/skills/talents/oteny-flatbelly-talent/scripts/<name>.py`; the db at
`~/.hermes/data/oteny-flatbelly-talent/food.db`). **Run them directly.** Do **not** use
`search_files`, `find`, or `ls` to "locate" a script, a skill, or the db first —
`search_files` takes a **regex, not a shell glob**, so a `*name*` pattern is a hard
error that teaches you nothing and burns the turn. If any command errors, read the error
and fix that **one** thing (or ask the owner) — **never re-issue the same failing call**;
repeating a search that just failed only balloons cost without getting closer.

## Daily reminder role

At the tenant's `profile.reminders` times (default 08:00 + 20:00 local) the reminder
**never opens with a blank "what did you eat?"** — you first **show the tenant where
their day stands** (run preflight, read today's rows fresh — hard rule ①), then ask
only for what's still missing. The same applies when the owner replies to a reminder
or messages you in the morning/evening.

1. **Read state first (grounding).** Run `preflight.py` (triage step 1) — it returns
   today's logged rows, the local clock and the targets. Then read today's totals
   (`references/reports.md` §1, optionally the full join §2) and, if a morning weight is
   in, its trend (§3). **Never vibe-serve a number** (hard rule ①) — every figure in the
   summary comes from a query you ran this turn.
2. **Open with the "day so far" summary — the regular layout.** One compact,
   Telegram-friendly block (English base, translated per `profile.language`): a line per
   metric, ✅ for what's logged, `—` for what's still open. Frame by time-of-day (hard
   rule ③): before ~18:00 "so far today" + "X g protein to go"; after ~18:00 the **day
   total** + any deficit / leucine miss. Show only rows that apply.

   > 📊 **Your day so far — Wed 26 Jun**
   > • ⚖️ Weight: 84.6 kg (morning) — 85.0 → 84.6, −0.4 kg/wk (7-day) ✅
   > • 🍽️ Food: 1,240 kcal · 78 g protein — 42 g to go for 120 g · leucine 2/3 meals ✅
   > • 🚶 Steps: 6,200 / 10,000
   > • 💤 Sleep: 88
   > • 🏋️ Workout: —
   > • 📏 Waist: logged this week ✅

   If the day is still empty (early-morning reminder), say so in one line and anchor on
   yesterday's close + this morning's weight rather than printing a blank grid.
3. **Then ask only for the gaps.** Name what's still missing and invite one message;
   you then write the exact INSERT/UPSERT statements (a `leucine_g` estimate per item)
   and re-state the updated totals.

   > Still open today: **dinner · steps · sleep**. Send them in one message — I'll work
   > out the calories, macros and leucine and update your totals.

Keep it to two short Telegram messages (the summary, then the ask), in the tenant's
language, macros spelled out, ending with **one** concrete lever if a target is behind.

Everything beyond the hot paths above — per-intent checklists, exact write/report SQL,
macro defaults, the jargon glossary and the full schema — is in `references/`. Pull the
one file you need; don't pre-load them.
