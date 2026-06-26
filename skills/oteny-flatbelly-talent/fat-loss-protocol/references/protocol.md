# Visceral Fat (VAT) Reduction — Method Body

The 90-day visceral-fat reduction method OtenyFlatBellyTalent coaches — gathered from books
and the internet, editorially reviewed, and cross-checked
against 2022–2026 RCTs. Where it diverges from popular belly-fat advice (cardio, meal
timing, leucine), coach the evidence version below. Citations are in
`research-dossier.md`.

The supporting tracker tables exist specifically to coach these levers: sleep rhythm
& consistency (highest priority), meal timing (eating window), resistance training,
daily steps/berries/alcohol/processed flags, weekly WHtR.

## Three points where popular advice gets it wrong

### 1. Cardio + cortisol — popular advice OVERSTATES the risk

Claim: *"Extensive cardio spikes stress hormones, which can promote visceral fat
storage."* Hard evidence at moderate doses says otherwise:

- **JAMA Network Open 2024 meta-analysis** (116 RCTs, 6,880 overweight adults, GRADE
  high): aerobic cardio reduces VAT **−1.60 cm² per 30 min/week**, dose-dependent,
  **no plateau or reversal up to 300+ min/week**.
- **2025 meta-analysis (44 RCTs):** moderate continuous aerobic (~770 MET-min/wk ≈
  150–250 min/wk) **lowers** resting cortisol (SMD 0.31). HIIT slightly raised
  cortisol (NS).
- **2024 RCT, overweight postmenopausal women:** 135 min/wk moderate cardio × 6 mo →
  **no change** in basal cortisol.

**Rule:** avoid chronic high-volume high-intensity cardio (>1 h/day,
marathon training, daily HIIT). Moderate cardio (zone 2, 150–300 min/wk) directly
reduces VAT and slightly LOWERS cortisol. Daily walking 7–10k steps counts and is
encouraged. Don't tell the tenant to fear cardio at sane doses.

### 2. "Early TRE beats late TRE" — NOT supported

- **Dote-Montero 2025 RCT** (n=197, 12 wk, 8h windows, MRI-measured VAT, head-to-head):
  early TRE (~8am–4pm) VAT −4% (NS); late TRE (~12pm–8pm) −6% (NS); self-selected −3%
  (NS). **No significant difference between early and late for VAT.**

**Rule:** 8–10h eating window; early vs late doesn't matter for VAT. Pick
what the tenant will adhere to. Consistency > timing.

### 3. Leucine threshold — per-meal, not just daily total

Older adults (55+) have anabolic resistance; per-meal leucine matters more than total
daily protein alone.

- ISSN + 2024 meta-analysis: **1.6–2.0 g/kg/day** for fat loss + muscle preservation.
- Each protein-anchored meal should deliver **25–40 g protein / 2.5–3.0 g leucine**
  to maximally trigger MPS in older adults.
- Distribution across **3–5 meals** beats skewed intake by ~25% in 24h MPS (2025 RCT).

**Rule:** every protein-anchored meal hits 25–40 g protein / 2.5–3.0 g
leucine. Whey, eggs, fish, lean meat, Greek yoghurt all qualify per portion size.

## Other evidence-aligned rules

- Sleep 7–9h, consistent ±30 min — strongly supported (Aberdeen 2023, JACC 2022 RCT).
- 2 cups dark berries/day — polyphenols → VAT, supported.
- Resistance 3×/wk hitting each muscle 2× — supported (synergy with cardio +20–30%).
- A **daily 60+ min walk** / 7–10k steps — supported, the baseline movement anchor.
- No alcohol, no ultra-processed — supported.
- WHtR <0.5 as a free daily proxy — supported.

## Exercise prescription

- **Daily walk of 60+ minutes** — the baseline anchor and the highest-adherence VAT
  lever: a single hour of brisk (zone-2) walking clears blood glucose, improves insulin
  sensitivity, and on its own covers most of the weekly cardio minutes **and** the step
  goal. Make this the non-negotiable daily habit.
- **Resistance** 3×/wk (each muscle group hit 2×) — preserves muscle during the deficit
  and rebuilds the skeletal-muscle "glucose sponge".
- **Cardio** 150–300 min/wk moderate (the daily 60-min walk already gets you there) OR
  HIIT 3×/wk × 20–30 min on top.
- **7–10k daily steps** as baseline NEAT — the 60-min walk is ~6–8k of them.

## Other 2022–2026 confirmations

- **Sleep:** <7h → +10–15% VAT; 4–5h restriction → +10–20% VAT in 3 wk (JACC 2022);
  irregular bedtime ±>2h → +5–10% body fat.
- **Protein:** 1.6–2.2 g/kg with even pacing → 20–25% more VAT loss than deficit alone.
- **TRE:** 8–10h window + lower-carb → −15–20% VAT in 8 wk.
- **Berries** 200–300 g/day → −10–15% VAT in 8 wk (anthocyanins/polyphenols).
- **Fiber** 30–40 g/day → −15% VAT in 8 wk.
- **EVOO** 2–3 tbsp/day, **omega-3** 2–3 g/day → measurable VAT/waist reduction.
- **Magnesium** 300–400 mg/day — modest, indirect; not a primary lever.

## What does NOT work (confirmed)

- Spot reduction (crunches/sit-ups) — no targeted VAT effect.
- Diet alone without exercise → 5–10% VAT vs 20–30% combined.
- Extreme deficit <1,200 kcal/day without adequate protein → muscle loss + 10–15% VAT
  rebound. (This is the hard deficit floor — see `../references/safety-boundaries.md`.)
- Pharmacological interventions alone — minimal VAT impact without lifestyle.

## Translating to the tenant

- **Protein band:** 1.6–2.2 g/kg × `profile.start_weight_kg`. State the band and the
  tenant's gram number; the `profile.protein_target_g` default sits mid-band.
- **Daily walk:** 60+ min (covers most cardio + steps). **Cardio:** 150–300 min/wk
  moderate OR HIIT 3×/wk × 20–30 min on top.
- **Resistance:** 3×/wk, each muscle group 2×.
- **Steps:** 7–10k/day. **Sleep:** 7.5–8h, bedtime ±30 min. **TRE:** 8–10h window.
- **Food anchors:** 200–300 g berries, 30–40 g fiber, 2–3 tbsp EVOO, 2–3 g omega-3.

Concrete meals and staples that hit all of this — the yoghurt+whey protein bowl,
cottage cheese, psyllium husk — are in `food-ideas.md`; the bot may also generate
equivalents that respect the protein/leucine/fiber and no-processed/no-alcohol rules.

Never hardcode an example body; compute from the tenant's profile.
