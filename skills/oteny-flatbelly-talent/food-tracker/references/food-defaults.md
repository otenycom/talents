# food-tracker — Macro defaults, leucine ratios & shorthands

The estimation tables the `§MEAL` path uses, plus the mechanic for the tenant's own
vocabulary. These are **illustrative few-shot examples**, not the tenant's data —
quote the assumption you used in `meals.notes` so corrections are easy.

## Leucine estimation (`leucine_g ≈ protein_g × ratio`)

Whey 10.5% · Egg 8.7% · Beef 8.5% · Chicken/Pork 8.0% · Fish 8.5–9.0% · Greek
yoghurt 9.5% · Cheese 9.5% · Beans/lentils/soy 7.5–8.0% · Nuts/seeds 7.0% ·
Bread/grain 7.0% · Veg/fruit/berries 5.5–6.0%. For mixed meals use the dominant
animal-protein ratio. For MPS at 55+, each protein-anchored `meal_type` group should
sum to ≥ `profile.leucine_threshold_g` (default 2.5 g, 3.0 g if age ≥ 55).

## Macro defaults (illustrative — grow the tenant's own list in their profile)

Standard supermarket-grade assumptions when the tenant logs a generic name without a
grade. When the tenant qualifies ("lean"/"mager", "fatty"/"vet"), shift accordingly and
`UPDATE` the row.

| Food | Default assumption | kcal/100g | Protein/100g | Fat/100g | Leucine ratio |
|---|---|---|---|---|---|
| minced beef ("rundergehakt") | half-om-half ~15% fat | 240 | 22 g | 16 g | 8.5% |
| skyr (plain 0% fat) | sugar-free natural | 63 | 10.6 g | 0.2 g | 9.5% |
| smoked chicken slices | low-fat deli | 110 | 24 g | 2.5 g | 8.0% |
| smoked mackerel | full-fat | 270 | 20 g | 22 g | 8.5% |
| salmon fillet | farmed Atlantic | 200 | 22 g | 13 g | 9.0% |
| eggs (L) | per egg | — | 6 g/egg | 5 g/egg | 8.7% |
| quark 0% | natural | 55 | 10 g | 0.3 g | 9.5% |
| cottage cheese ("Hüttenkäse") | original 4% | 100 | 13 g | 4 g | 9.5% |

## Shorthands & the tenant's own vocabulary (start empty)

The tenant grows their own `## Your shorthands` / `## Your common foods` in
`profile.yaml` as they say "from now on I refer to this as …". Illustrative examples
of the *mechanic* (not tenant data):

- **fruit bowl** → 300 g protein-yoghurt + 2 cups dark berries + 10 g whey isolate +
  chia + psyllium ≈ 435 kcal · 44 g protein · ~4.0 g leucine.
- **soup bowl** → 450 g base + psyllium + cooked carrot ≈ 301 kcal · 31 g protein.

Scale linearly ("1.5 soup bowls", "2 fruit bowls"). Store the expansion in
`meals.notes`; see `playbooks.md` §3.

## Output formatting rules

Spell macros out — never abbreviate as single letters (a trailing single letter reads
as a unit or a typo; `82 g P` looks like the unit *gram*, ambiguous in several
languages):

- ✅ `1194 kcal · 82 g protein · 79 g carbs · 56.5 g fat · 6.74 g leucine`
- ❌ `82 g P · 79 g C · 56.5 g F`

Keep replies compact and Telegram-friendly. Quote source numbers whenever comparing to
a prior value. For *how settled* to pitch the jargon (the fade ladder), see
`glossary.md`.
