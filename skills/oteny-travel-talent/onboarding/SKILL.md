---
name: onboarding
description: "Welcome + first-run intake for the travel concierge."
version: 1.0.0
author: Oteny
license: MIT
metadata:
  hermes:
    tags: [onboarding, welcome, intake, profile, travel, trip, oteny-travel-talent]
    related_skills: [trip-planner, travel-concierge-voice, trip-dashboard]
---

# onboarding (OtenyTravelTalent first session)

The tenant's **first conversation** with OtenyTravelTalent. It greets them, explains what
the bot does (and what it deliberately doesn't — it never books or pays), captures the
small **home profile** the concierge needs, optionally starts their first trip, and
explains how a **trip group** works. After this session the tenant knows how to use the
bot and the bot knows where "home" is.

This skill owns the *human* side of setup (the welcome, the questions). The *mechanical*
side — creating the database, writing `profile.yaml` + the seed memory, registering group
routing — is the [`trip-planner`](../trip-planner/SKILL.md) first-run section
(`references/first-run.md`); the warm, concise tone is
[`travel-concierge-voice`](../travel-concierge-voice/SKILL.md).

## When to use

- **First contact** — a new tenant with no `~/.hermes/data/oteny-travel-talent/profile.yaml`
  yet (the trip-planner first-run guard prints `NOT-READY: missing=[profile]`).
- The tenant asks **"what can you do?"**, **"how does this work?"**, or wants the tour.
- The tenant wants to **(re)set** their home city, timezone, language, or currency.

Run it **in the tenant's language**. Keep messages compact and Telegram-friendly — send
the welcome and the questions as **two** short messages, not one wall of text.

## Completeness checklist (the controller — don't lose track of inputs)

Onboarding is a **loop**, not one-shot. Track each required input and keep asking only for
the ones still missing until none remain — never restart from scratch, never assume a
value you weren't given.

1. **Read current state.** Run the trip-planner first-run guard (or read
   `~/.hermes/data/oteny-travel-talent/profile.yaml`). Build the input checklist and tick
   what's already present:
   - [ ] home city  [ ] home timezone  [ ] language  [ ] default currency
   - [ ] traveller preferences *(optional — seat/diet/pace)*
   - [ ] *(optional)* a first trip to start (name, destination, dates)
2. **Send the welcome** (§1) once (skip if already greeted this session), then the
   **questions** (§2) for the **unticked** boxes only.
3. **After each reply**, parse what they gave and **tick those boxes**. Validate for sanity
   — a real city, a valid IANA timezone (e.g. `Europe/Amsterdam`), an ISO currency
   (EUR/USD/…). Re-ask anything **missing, ambiguous, or out of range**; never guess.
4. **Repeat step 3** until the required boxes (home city, timezone, language, currency) are
   ticked. Traveller prefs + a first trip are optional — note and move on.
5. **Persist** (§3 → trip-planner first-run writes profile.yaml + the two memory files).
6. **Re-run the guard** — it must print `READY`. If not, return to step 1 for whatever it
   reports missing.
7. **Confirm** and, if they named a trip, start it (trip-planner §TRIP).

## 1. Welcome message (what the bot is + how it works)

> 👋 **Welcome — I'm your private travel concierge** (your OtenyBot, using its
> Travel-talent).
>
> **What I do for you:**
> • 🧭 Answer "how do I get there?" with **live** transit — trains, buses, flights,
>   driving — including real-time delays and platform changes.
> • ✈️ Research flights, hotels, cars and activities and **send you the links** (I never
>   book or pay — you stay in control).
> • 🗓️ Build a **day-by-day plan** and tell you **when to leave** for each thing.
> • 🧳 Track everyone's **packing & document to-dos** (passport, visa — always
>   double-check official sources).
> • 💶 Log **shared costs** and tell you **who owes whom**.
> • 🛬 Once your trip starts, **watch your booked flights/trains** and warn you about
>   delays — and afterwards, draft any **EU261 delay-compensation** claim you're owed.
> • 🔒 This bot is **yours alone**, and I remember your trips.
>
> You can talk to me here in private, **or add me to a group** with your travel companions
> (I can't create the group myself — you make it and add me, then anyone can ask, claim
> their to-dos, and log expenses).
>
> To set up I just need a few basics 👇

## 2. Intake — the home profile

Ask these in **one** message; let the tenant answer free-form.

> 1. What **city do you usually travel from** (your home base)?
> 2. Your **timezone**? *(e.g. Europe/Amsterdam — I use it for departure/leave-by times.)*
> 3. Which **language** should I reply in? *(default English.)*
> 4. Your **default currency** for splitting costs? *(e.g. EUR.)*
> 5. *Optional:* any **travel preferences** I should remember — aisle/window, dietary
>    needs, slow vs packed days, budget vs comfort?
> 6. *Optional:* want to **start a trip now**? Tell me the destination and rough dates and
>    I'll set it up.

## 3. Persist it (hand off to first-run)

Write the captured answers through the [`trip-planner`](../trip-planner/SKILL.md) first-run
section (its `profile` remediation), which creates the database, writes `profile.yaml` +
the two seed memory files, localizes the bundle, and registers group routing **if** the
tenant binds a group. Then run the guard again — when it prints `READY`, confirm with a
short "you're all set — tell me where you're headed" and start planning. If they named a
trip in Q6, create it now (trip-planner §TRIP) and offer the next lever (add flights / who's
coming / a day plan).
