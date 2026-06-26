# food-tracker — Plain-Language Glossary (say it in human words)

New tenants don't know these terms — most people have never heard of leucine, mTOR or
WHtR. The table below gives the plain meaning + why it matters for each. Use it to teach
the vocabulary **gradually**: explain plainly while they're new, then **fade the jargon
in as they settle** so they learn the words without being lectured. Don't dump jargon on
a newcomer; don't keep over-explaining a regular.

## Fade the jargon in as the tenant settles

Gauge how settled they are — mainly by **how long they've used the bot** (the days they
have entries: `SELECT COUNT(DISTINCT date) FROM meals;`), and by whether they now use the
terms themselves and have stopped asking what things mean:

- **New (≈ first week / first handful of logged days):** lead with **plain words + why it
  matters**, every time the term comes up; the technical word is secondary.
  → `you cleared the muscle-protecting threshold this meal (it's called leucine — about
  2.5 g, ✅), which is what keeps muscle while you lose fat`
- **Settling (≈ weeks 2–4, has seen it explained a few times):** use the **real term
  first with a short tag**, not the full explanation, and not on every line.
  → `leucine 6.7 g ✅ (your muscle-protect threshold)`
- **Settled (logs fluently, uses the terms themselves):** use the term **bare**,
  peer-to-peer.
  → `leucine 6.7 g ✅`

**Override toward plain words at any stage** the moment they ask "what's X?" or seem
unsure. And never hand a **New** tenant a bare metric — `6.7 g leucine ✅` alone is
meaningless to a newcomer.

## The terms (term → in plain words → why it matters to you)

| Term | In plain words | Why it matters to you |
|---|---|---|
| calories (kcal) | a unit of food energy | the total you eat vs burn decides fat loss |
| protein | the nutrient that builds and protects muscle | eating enough lets you lose **fat**, not muscle |
| carbs (carbohydrates) | sugars and starches — quick energy | refined ones spike blood sugar; whole/fibre ones don't |
| fat (dietary) | the most energy-dense nutrient; some is essential | quality (olive oil, fish) matters more than cutting it all |
| macros (macronutrients) | the big three — protein, carbs, fat | their daily balance drives fat loss + keeping muscle |
| leucine | the amino acid that switches muscle-building **on** | hit enough per meal and your body guards muscle while you lose fat |
| leucine threshold | the ~2.5–3 g of leucine in **one** meal that flips the switch | a meal under it barely builds muscle even if total protein looks high |
| mTOR | your body's muscle-building "switch" | leucine + strength work turn it on — that's how you keep muscle on a diet |
| MPS (muscle protein synthesis) | the actual muscle-building process | what hitting the leucine threshold is there to maximise |
| anabolic resistance | with age, muscle responds less to protein | from ~55 you need a bit more protein per meal for the same effect |
| visceral fat (VAT) | the deep fat around your organs | the dangerous kind — the whole reason this coach exists |
| subcutaneous fat | the pinchable fat under your skin | the less harmful kind; not the main target |
| waist-to-height ratio (WHtR) | your waist divided by your height | keep it under 0.5 (waist < half your height) — your single best health number |
| BMI | a weight-for-height score | it misses visceral fat, so we track your waist instead |
| TOFI | "thin on the outside, fat on the inside" | why even slim people should check their waist |
| caloric deficit | eating a little less than you burn | the basic requirement to lose fat |
| BMR (basal metabolic rate) | the calories you burn at rest | the floor we never starve below (never under ~1,200 kcal) |
| recomposition | losing fat while keeping or gaining muscle | for lean people the scale barely moves but the waist still shrinks |
| NEAT | calories burned just moving around (walking, chores) | the easy everyday lever — that's why the daily hour-walk matters |
| zone 2 | an easy, conversational pace | brisk but you can still talk; burns fat without spiking stress |
| eating window / time-restricted eating (TRE) | eating only within set hours, fasting the rest | an 8–10h window (14h+ overnight fast) lets insulin settle |
| glycogen | stored carbs that hold water | why the first week's drop is fast (mostly water, not fat) |
| insulin | the hormone that stores nutrients after you eat | keeping it steady (not spiking) helps shed visceral fat |
| insulin resistance | when the body stops responding well to insulin | a driver of visceral fat and diabetes; the protocol helps reverse it |
| cortisol | your main stress hormone | staying high pushes fat to the belly; sleep + walks lower it |
| AMPK | an "energy sensor" that exercise switches on | helps burn fat and clear blood sugar |
| NAFLD (fatty liver) | fat stored in the liver, not from alcohol | visceral fat drives it; losing weight is the treatment |
| polyphenols / anthocyanins | healthy plant compounds in colourful fruit | why dark berries are a daily food anchor |
| omega-3 | healthy fats from oily fish | anti-inflammatory; linked to less waist/visceral fat |
| EVOO | extra-virgin olive oil | the default cooking + dressing fat |

For the deeper "why" on the health side, load
[`../../fat-loss-protocol/references/why-visceral-fat.md`](../../fat-loss-protocol/references/why-visceral-fat.md);
the method numbers are in [`../../fat-loss-protocol/SKILL.md`](../../fat-loss-protocol/SKILL.md).
