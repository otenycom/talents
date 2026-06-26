# Visceral Adipose Tissue (VAT) Reduction — Research Dossier

The evidence backing for the method in `protocol.md`. Quote and cite from this file
when the tenant asks "where does that number come from?" Static and baked for v1 — no
live web search.

## Sleep — highest leverage
- **Aberdeen 2023** — <7h/night associated with +10–15% VAT accumulation; no benefit
  beyond 8h. https://abdn.elsevierpure.com/en/publications/shorter-sleep-duration-is-associated-with-greater-visceral-fat-ma
- **JACC 2022 RCT** — 4–5h sleep restriction → +10–20% abdominal VAT in 3 weeks.
  https://www.sciencedirect.com/science/article/pii/S0735109722003102
- **Wiley 2023** — Irregular sleep (>2h variance) → +5–10% body fat including VAT.
  https://onlinelibrary.wiley.com/doi/full/10.1002/osp4.640
- **Sleep journal 2023** — <7h linked to 15–20% more VAT regain post-diet.
  https://academic.oup.com/sleep/article/46/5/zsac295/6874808

## Diet pattern, protein, eating window
- **Lipid Journal 2025** — Mediterranean + 500–800 kcal deficit → −10–15% VAT in 12
  weeks. https://www.lipidjournal.com/article/S1933-2874(25)00387-3/fulltext
- **IJSNEM 2025 RCT** — Protein 1.6–2.2 g/kg with even pacing → +20–25% VAT loss vs
  standard deficit. https://journals.humankinetics.com/view/journals/ijsnem/35/6/article-p493.xml
- **PMC 2026** — 8–10h eating window + lower-carb → −15–20% VAT in 8 weeks.
  https://pmc.ncbi.nlm.nih.gov/articles/PMC12829361
- **Dote-Montero 2025 RCT** — early vs late TRE: −4% vs −6% VAT, both NS (no
  difference for VAT). https://www.mdpi.com/2072-6643/17/1/169

## Exercise (cardio, resistance, synergy)
- **JAMA Network Open 2024 meta-analysis** — 150–300 min/wk moderate cardio →
  −10–20% VAT, dose-dependent, independent of weight loss.
  https://jamanetwork.com/journals/jamanetworkopen/fullarticle/2828487
- **PMC 2025 (T2D patients)** — HIIT 3×/wk × 20–30 min, 4-min bursts → −15–25% VAT.
  https://pmc.ncbi.nlm.nih.gov/articles/PMC12684977
- **ScienceDirect 2023 meta-analysis** — HIIT not superior to continuous cardio; both
  ~12% VAT. https://www.sciencedirect.com/science/article/pii/S1728869X23000461
- **ScienceDirect 2025** — Resistance alone: only −5–10% VAT.
  https://www.sciencedirect.com/science/article/abs/pii/S1871403X25001188
- **JNR-TWNA 2025** — Resistance + cardio/HIIT → +20–30% total fat-loss synergy.
  https://journals.lww.com/jnr-twna/fulltext/2025/04000/exercise_strategy_for_reducing_visceral_adipose.9.aspx

## Foods / supplements
- **Polyphenols** 500–1000 mg/day → −12–18% VAT, 2026 trial.
  https://examine.com/research-feed/study/1YYDo1
- **Berries** 200–300 g/day → −10–15% VAT in 8 weeks via gut-microbiome shift.
- **Fiber** 30–40 g/day → −15% VAT in 8 weeks (Japanese 2026 trial).
- **EVOO** 2–3 tbsp/day → up to 3× faster VAT loss; oleocanthal anti-inflammatory.
- **Omega-3** 2–3 g/day → −10–15% waist/VAT, 2026.
- **Magnesium** 300–400 mg/day — modest, indirect.
  https://pmc.ncbi.nlm.nih.gov/articles/PMC7551574

## What does NOT work
- Spot reduction — no targeted VAT effect (confirmed 2025).
- Diet alone without exercise → 5–10% VAT vs 20–30% combined.
  https://www.medicalnewstoday.com/articles/diet-exercise-study-best-strategy-reducing-belly-fat-weight-loss
- Extreme deficit <1,200 kcal/day without adequate protein → muscle loss + 10–15% VAT
  rebound. https://onlinelibrary.wiley.com/doi/full/10.1002/oby.23660
- Pharmacological interventions alone — minimal VAT impact without lifestyle.

## Translating effect sizes to the tenant

Apply the bands to the tenant's `profile`, not an example body:
- **Protein band:** 1.6–2.2 g/kg × `start_weight_kg` → the tenant's gram range;
  `protein_target_g` defaults mid-band.
- **Cardio:** 150–300 min/wk moderate OR HIIT 3×/wk × 20–30 min.
- **Resistance:** 3×/wk, each muscle group 2×.
- **Steps:** 7–10k/day. **Sleep:** 7.5–8h, bedtime ±30 min.
- **Food anchors:** 200–300 g berries, 30–40 g fiber, 2–3 tbsp EVOO, 2–3 g omega-3.
