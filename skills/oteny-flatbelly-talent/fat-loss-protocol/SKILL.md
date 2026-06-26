---
name: fat-loss-protocol
description: "The fat-loss method + the RCT evidence behind it."
version: 1.0.0
author: Oteny
license: MIT
metadata:
  hermes:
    tags: [visceral-fat, VAT, protocol, evidence, nutrition, exercise, sleep, oteny-flatbelly-talent]
    related_skills: [food-tracker, flatbelly-coach-voice]
---

# fat-loss-protocol (the OtenyFlatBellyTalent method)

The evidence-based method OtenyFlatBellyTalent coaches toward: lose **visceral adipose
tissue (VAT)** — the metabolically active visceral fat — with real food, protein/leucine
timing, sleep, and the right dose of movement. This skill is the **method and its
citations**; the logging engine is [`food-tracker`](../food-tracker/SKILL.md), the
voice is [`flatbelly-coach-voice`](../flatbelly-coach-voice/SKILL.md).

> Method numbers are the product and stay (leucine 2.5 g/meal, protein 1.6–2.2 g/kg,
> 0.5–1.0% of body weight per week sustainable, 150–300 min/wk cardio, RCT effect
> sizes). Body numbers belong to the tenant's profile — translate every prescription
> to *their* weight and *their* body composition, never a baked example body. Rates
> are expressed as **% of body weight**, not absolute kg, so the same rule fits a
> 60 kg lean athlete and a 130 kg starting body alike.

## 🧭 Quick-reference index

| Need | Load |
|---|---|
| The full 90-day method body + the cardio/TRE/leucine evidence rules | `references/protocol.md` |
| Why visceral fat matters (the motivation/education: dysfunctional organ, TOFI, drivers) when the tenant asks "what is visceral fat?" / "why bother?" | `references/why-visceral-fat.md` |
| Meal ideas + staples (yoghurt+whey bowl, cottage cheese, psyllium) when the tenant asks "what should I eat?" | `references/food-ideas.md` |
| The cited peer-reviewed studies (2022–2026) with URLs | `references/research-dossier.md` |
| Medical safety boundary (red flags, deficit floor, disclaimers) | `../references/safety-boundaries.md` |

## The levers, in order of leverage

1. **Sleep is the highest lever.** <7h → +10–15% VAT; 4–5h restriction → +10–20% VAT
   in 3 weeks (JACC 2022). Target 7.5–8h, bedtime within ±30 min. Irregular bedtime
   (>2h variance) alone adds 5–10% body fat.
2. **Protein, distributed.** 1.6–2.2 g/kg/day with even pacing → +20–25% VAT loss vs
   the same deficit unpaced (IJSNEM 2025). Each protein-anchored meal: 25–40 g
   protein / 2.5–3.0 g leucine to clear the mTOR threshold — distribution across 3–5
   meals beats a skewed intake by ~25% in 24h MPS, and matters more with age
   (anabolic resistance at 55+).
3. **Moderate cardio works — directly. A daily 60+ min walk is the baseline.** 150–300
   min/wk moderate (zone 2) → −10–20% VAT, dose-dependent with no plateau to 300+ min/wk
   (JAMA Network Open 2024, 116 RCTs), and it *lowers* resting cortisol at moderate
   doses. A **daily walk of 60+ minutes** is the single highest-adherence lever — it
   clears blood glucose, improves insulin sensitivity, and on its own covers most of the
   weekly cardio minutes and the 7–10k step goal. (Do **not** repeat the gym-lore line
   that "cardio spikes cortisol" at sane doses — see below.)
4. **Resistance for synergy.** Resistance alone is a weak solo VAT lever (−5–10%) but
   resistance + cardio → +20–30% total fat loss vs either alone. 3×/wk, each muscle
   group hit 2×, preserves muscle in a deficit.
5. **Eating window 8–10h.** Early vs late does NOT matter for VAT (Dote-Montero 2025
   RCT, n=197, MRI: early −4%, late −6%, both NS) — pick whichever window the tenant
   will adhere to. Consistency > timing.
6. **Food anchors.** 200–300 g dark berries/day (polyphenols), 30–40 g fiber/day,
   2–3 tbsp EVOO, 2–3 g omega-3 — each independently associated with measurable VAT
   reduction. Concrete meals + staples (the yoghurt+whey bowl, cottage cheese, psyllium
   husk) live in `references/food-ideas.md` — the bot may also generate equivalents that
   respect the protein/leucine/fiber and no-processed/no-alcohol constraints.

## Three points where popular advice gets it wrong

Popular belly-fat advice gets these three points wrong; the 2022–2026 RCT evidence
says coach the version below:

1. **Cardio is not the enemy at moderate doses** — it reduces VAT and lowers cortisol;
   only chronic >1h/day high-intensity without recovery, or under-fueling, raises the
   cortisol concern.
2. **Early TRE does not beat late TRE for VAT** — both NS; adherence is the variable.
3. **Per-meal leucine threshold matters at 55+** — total daily protein alone is not
   enough; distribute it.

Full reasoning + every citation: `references/protocol.md` and
`references/research-dossier.md`.

## What does NOT work (confirmed)

Spot reduction (crunches/sit-ups); diet alone without exercise (5–10% vs 20–30%
combined); extreme deficit <1,200 kcal/day without adequate protein (muscle loss +
10–15% VAT rebound); drugs without lifestyle integration.

## Deriving the natural path (any body type)

The method is one set of levers; the **trajectory** is derived per person, never
baked. The same logic must fit a very obese starter, an average dieter, and a lean
muscular athlete — so read the body and pick the path. Inputs: `sex`, `age`,
`height_cm`, current morning weight, and **waist** → **waist-to-height ratio (WHtR =
waist ÷ height)**, the primary health metric (valid across sexes, ethnicities and
**high muscle mass** — NICE 2022; a lean bodybuilder and an obese person are scored on
the same scale).

**1. Read WHtR and choose the path** (bands: <0.4 too low · 0.4–0.49 healthy ·
0.5–0.59 raised · ≥0.6 high — "keep your waist under half your height"):

| WHtR | What it means | Path |
|---|---|---|
| **≥ 0.5** | Central adiposity → meaningful visceral fat | **Fat loss** toward WHtR < 0.5 |
| **0.4–0.49** | Already healthy central adiposity | **Recomposition / maintenance** — not an aggressive deficit |
| **< 0.4** | Very lean | **No fat-loss prescription** — muscle/maintenance; apply the ED guard (`../references/safety-boundaries.md`) |

**2. Set the rate generically — % of body weight, scaled by adiposity:**

- **Fat-loss path:** target **0.5–1.0% of current body weight per week**. Lean toward
  the **upper end** when WHtR is high and there is plenty of fat to draw on; toward the
  **lower end** as WHtR approaches 0.5, to protect muscle. Weeks 1–3 often drop faster
  (water/glycogen) — don't extrapolate that into the steady rate.
- **Recomposition path:** a **small or zero deficit** (≤ ~0.3–0.5%/wk); push protein +
  resistance so fat falls while muscle holds or grows. Success = waist shrinking and
  strength rising, **not** the scale moving.

**3. Protein basis (generic).** 1.6–2.2 g/kg/day, distributed so each protein-anchored
meal clears the leucine threshold. Base it on **current weight** for lean/normal
bodies; for high adiposity (WHtR ≥ 0.5 with a large gap to a healthy weight) base it on
**goal/reference weight** so a very large body isn't handed an unrealistic protein
target. BMR via Mifflin-St Jeor from `sex/age/height_cm`.

**4. Universal floors (never crossed, any body type).** Never below ~1,200 kcal/day;
never faster than ~1%/wk sustained (flag > 1.5%/wk in week 4+ as water or under-eating);
never push WHtR below 0.4 or goal BMI below 18.5 (eating-disorder guard).

Quote the *rule* and the tenant's *number*, never a sample body. The success metric for
everyone is **WHtR trending toward / holding under 0.5**, with weight as the day-to-day
tracker.

## Citation policy

When stating an effect size, cite the study (year + journal short name) inline from
`research-dossier.md`. Don't relay claims as gospel and don't vibe-serve evidence —
same hard rule as DB facts. **No live web search in v1** (the static dossier is the
source); live evidence lookup is a future charged-tool path.

## Safety

This is lifestyle coaching, not medical advice. The deficit floor, red-flag
escalation, and disclaimer in `../references/safety-boundaries.md` are hard guards —
load them with the voice.
