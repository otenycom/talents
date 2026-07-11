---
name: trip-dashboard
description: "Render the trip card: plan, bookings, costs, packing."
version: 1.0.0
author: Oteny
license: MIT
metadata:
  hermes:
    tags: [dashboard, visualization, trip, card, telegram, oteny-travel-talent]
    related_skills: [trip-planner]
---

# trip-dashboard

Generates a dark-themed PNG **trip card** — the "Our Trip to Lisbon" at-a-glance view —
**fully parameterized from `~/.hermes/data/oteny-travel-talent/trips.db` +
`profile.yaml`**. Nothing about a trip is baked.

- **Header**: trip name, destination, dates, and a **countdown** (days to go / "Day N of M"
  while ongoing / "ended").
- **Plan**: the next few scheduled items (today first), with times.
- **Bookings**: key legs (flights/trains with live status) + stays.
- **Settle-up board**: total spend + who-owes-whom (per currency), via `settle_up.py`.
- **Packing status**: open vs done to-dos per member.
- Telegram-friendly canvas at ≤180 dpi.

## When to use

- The tenant asks for a "trip card / overview / dashboard / settle-up board".
- The post-trip review cron (it embeds the spend recap).
- After a material change (a new booking, the schedule firmed up).

## How to run

```bash
python3 ~/.hermes/skills/talents/oteny-travel-talent/trip-dashboard/scripts/trip_card.py --trip <id>
```

Reads `~/.hermes/data/oteny-travel-talent/{trips.db,profile.yaml}`, writes
`/tmp/hermes/cache/oteny_trip_<id>_<YYYY-MM-DD>.png`, and prints the path. Deliver it by
including `MEDIA:<path>` in the reply. Override paths with `--db` / `--profile` /
`--out-dir` for testing; omit `--trip` to use the active/soonest trip.

## Captioning convention

Lead with the headline (trip + countdown), then 3–4 bullets grounded in the DB read: the
next move + its **leave-by**, any **live delay** on a monitored leg, the **settle-up**
one-liner, and the **packing status** ("3 of 8 to-dos still open"). Don't editorialize
beyond the data (no vibe-served facts).

## Style tokens (keep consistent across visuals)

```
BG #0b1020  panel #121933  grid #1f2a4d   text #e7ecff  muted #8b95c2
accent #7dd3fc  ok #34d399  warn #fbbf24  alert #f87171  member #a78bfa
```

## Pitfalls

- **Never use `image_generate` for a map or route.** The trip-card here is a **deterministic
  data render** (`trip_card.py` draws real DB rows on a canvas) — that's allowed and
  encouraged. An **AI-fabricated** map/route picture is banned (`trip-planner/SKILL.md` hard
  rules): it encodes nothing real and misleads wayfinding. For directions, emit the
  `maplink.py` deeplinks; for the at-a-glance trip view, render this card.
- **Trip not found / empty trip** → the script exits non-zero; reply "nothing to show yet"
  instead of crashing.
- **Live status is only as fresh as the last monitor run** — the card shows the stored
  `bookings.status`; for a definitive "is it on time now?", re-pull via `travel`.
- Keep dpi ≤ 200 so Telegram delivers it as a photo, not compressed-to-mush.
- `matplotlib` is provisioned by the platform: it is declared in this bundle's
  `agent-profile.yaml` (`runtime.python_packages`), the hermeshost deployer installs it into
  the tenant's system `python3`, and the golden + container images bake it. If it is ever
  missing the script degrades to a "trip card unavailable" message and exits 2 (the cron then
  registers FAILED) rather than crashing with a raw `ImportError`.
