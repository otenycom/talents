---
name: weight-progress-dashboard
description: "Render a weight + waist progress chart image."
version: 1.0.0
author: Oteny
license: MIT
metadata:
  hermes:
    tags: [dashboard, visualization, weight, progress, telegram, oteny-flatbelly-talent]
    related_skills: [food-tracker]
---

# weight-progress-dashboard

Generates a dark-themed PNG of the tenant's weight progress — **fully parameterized
from `~/.hermes/data/oteny-flatbelly-talent/profile.yaml`** (goal weight, optional milestones, DB path).
Nothing about a body is baked.

- Morning-weight time series (auto-filters evening entries — food-tracker hard rule).
- 7-day rolling slope projected to the goal line.
- Goal band + ETA; an optional milestone band (from `profile.milestones`).
- Headline: total kg lost + % to goal. Four stat cards: pace, still-to-go, milestone
  (or full-period pace), goal ETA.
- Telegram-friendly 13×8.5" canvas at 180 dpi.

## When to use

- The tenant asks for a "progress visual / chart / dashboard".
- The weekly cron (registered by `../scripts/provision_cron.py`).
- After milestone weeks where the trend changed materially.

## How to run

```bash
python3 ~/.hermes/skills/talents/oteny-flatbelly-talent/weight-progress-dashboard/scripts/generate.py
```

Reads `~/.hermes/data/oteny-flatbelly-talent/food.db` + `~/.hermes/data/oteny-flatbelly-talent/profile.yaml`, writes
`/tmp/hermes/cache/oteny_belly_progress_<YYYY-MM-DD>.png`, and prints the path. Deliver
it by including `MEDIA:<path>` in the reply. Override paths with `--db` / `--profile`
/ `--out-dir` for testing.

## profile.yaml inputs

- `goal_weight_kg` (**required**) — the goal line.
- `milestones` (optional) — a list of `{label, weight_kg}`; the first drives the
  secondary band (e.g. a tenant-supplied liver-marker milestone). Omit → the third
  card shows full-period pace instead.

## Captioning convention

Lead with the headline (kg lost + % to goal), then 3–4 bullets: last-7-day pace
(validate it's in the **0.5–1.0% of body weight per week** band — ≈ `current_kg × 0.005`
to `× 0.01`; leaner bodies and recomposition sit lower), full-period slope, milestone
ETA (if any), goal ETA. Don't editorialize beyond the data — ground the caption in a DB
read (no vibe-served facts).

## Style tokens (keep consistent across visuals)

```
BG #0b1020  panel #121933  grid #1f2a4d   text #e7ecff  muted #8b95c2
weight #7dd3fc  trend #a78bfa  goal #34d399  milestone #fbbf24  start #f472b6
```

## Pitfalls

- **<2 morning weights** → the script exits non-zero; the cron sends a "not enough
  data yet" message instead of crashing.
- **Slope flips positive** (regain week) → ETA cards show "—" / "recovery week".
- Keep dpi ≤ 200 so Telegram delivers it as a photo, not compressed-to-mush.
- `matplotlib` is provisioned by the platform: it is declared in this bundle's
  `agent-profile.yaml` (`runtime.python_packages`), the hermeshost deployer installs it into
  the tenant's system `python3`, and the golden + container images bake it. If it is ever
  missing the script degrades to a "chart unavailable" message and exits 2 (the cron then
  registers FAILED) rather than crashing with a raw `ImportError`.
