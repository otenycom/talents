---
name: trip-planner
description: "Plan trips: transit, bookings, schedule, todos, costs."
version: 1.0.0
author: Oteny
license: MIT
metadata:
  hermes:
    tags: [travel, trip, transit, flights, itinerary, expenses, packing, sqlite, oteny-travel-talent]
    related_skills: [onboarding, travel-concierge-voice, trip-dashboard]
---

# trip-planner (OtenyTravelTalent engine)

The **engine** for the travel concierge: trips, transport legs + lodging + activities,
day-by-day schedule, per-member prep todos, and a shared-expense ledger, in a per-tenant
SQLite database at `~/.hermes/data/oteny-travel-talent/trips.db`. This skill carries the
triage, the hot paths (live **transit** + **itinerary**), and the hard rules; the detail
lives in `references/` (loaded on demand via `skill_view(name='trip-planner',
file_path='references/<file>')`). The concierge *voice* is
[`travel-concierge-voice`](../travel-concierge-voice/SKILL.md); the *welcome/intake* is
[`onboarding`](../onboarding/SKILL.md); the *visual* card is
[`trip-dashboard`](../trip-dashboard/SKILL.md).

> **The product rule:** this skill carries the **method**; the tenant's
> `~/.hermes/data/oteny-travel-talent/profile.yaml` carries the **person** (home city,
> timezone, currency, preferences) and `trips.db` carries **their trips**. Never bake a
> home city, a destination, or a trip into this skill — read them. Reply in the tenant's
> language (`profile.language`, default English).

## When to Use

Load on any message about a trip or destination, getting somewhere (flights, trains,
buses, driving, transfers, routes, delays), a hotel/stay, a booking, the day's plan,
packing or documents, or a shared expense — and when a monitor/briefing/review cron
fires. It works in **DM** (solo) and in a **trip group** the human added the bot to.

## 🧭 Quick-reference index (load on demand)

The triage + the hard rules below are all you hold per turn. Everything else is a
`references/` file you pull **only when you hit that need**:

| Need to… | Load |
|---|---|
| **Set the bot up** (selfcheck said NOT-READY) | `references/first-run.md` |
| **Step-by-step per-intent checklist** (trip/booking/todo/expense/briefing/adjust) | `references/checklists.md` |
| **Live transit Q&A + door-to-door routing** (the `travel`-tool recipes) | `references/transit.md` |
| **Record a flight/train/car/stay + deals research + deep links** | `references/bookings.md` |
| **Build the day-by-day schedule + "leave-by" math** | `references/schedule.md` |
| **Per-member prep templates** (packing/documents/health) | `references/todos.md` |
| **Expense ledger SQL + split math + settle-up** | `references/expenses.md` |
| **Monitor + reroute + EU261 claim + post-trip review** | `references/disruption.md` |
| **Plain-language meaning of any travel jargon** (EU261, layover, leave-by) + fade ladder | `references/glossary.md` |
| **Full schema + intent→table routing** | `references/datamodel.md` |
| Visa / entry / health boundary | read `~/.hermes/skills/talents/oteny-travel-talent/references/safety-boundaries.md` (a bundle-level file — open it with the file tool) |

## 🚦 Every message — triage first (run in order, every time)

Do **not** improvise. (Skip to "Cron role" only when a monitor/briefing/review job fires.)

1. **One context call.** The per-turn probe returns setup-readiness, the local clock, the
   active trip, today's schedule, the open-todo count, the party roster, `memory.md`
   preferences, and whether an `overrides.md` exists — in a **single** declared call:

   ```bash
   python3 ~/.hermes/skills/talents/oteny-travel-talent/scripts/preflight.py
   ```

   - `READY: yes` → you hold the clock, the active trip, today's rows, prefs. **Don't**
     separately `cat` profile/memory or re-check the clock — preflight gave you all of it.
     If `OVERRIDES: yes`, read that file and let it take precedence. Go to step 2.
   - `READY: no` → setup is incomplete. Load `references/first-run.md` and follow it
     (declared scripts only). **Do not plan until READY.**
   - `MIGRATIONS: pending → …` → an older version of this Talent left state in the wrong
     shape. Load `references/migrations.md`, run each listed migration's checklist **in
     order**, then continue this turn. (Runs even on a READY box; each is idempotent.)

2. **Is this for the travel bot?** **YES** if it mentions a trip, a place to get to,
   transport, a flight/train/bus/drive/transfer, a hotel/stay, a booking, the schedule,
   packing/documents, an expense, or it's a reply to one of my reminders. **NO**
   (chit-chat, off-topic) → reply briefly in-voice, **write nothing**. **Unsure** → ask
   one short question first.

3. **(Group only) Who is speaking?** If `preflight` shows a group-bound trip (or several
   senders): map the sender's `telegram_user` to a `members` row; if they're **new**,
   greet them by name and insert the row (D84, `references/checklists.md` §MEMBER). DM/solo
   → skip.

4. **Classify the intent(s) and handle each, in table order.** TRANSIT and ITINERARY are
   inlined below; for the rest, load the referenced file **only** for the intent you hit:

   | The message is about… | Intent | How |
   |---|---|---|
   | getting somewhere / a route / live delays (no booking) | TRANSIT | **§TRANSIT below** |
   | the day plan / scheduling something at a time | ITINERARY | **§ITINERARY below** |
   | starting or editing a trip (name, dates, destination) | TRIP | `references/checklists.md` §TRIP |
   | a flight/train/car/ferry/hotel/stay/activity to record or research | BOOKING | `references/bookings.md` |
   | a prep task — pack / bring / passport / visa / vaccine | TODO | `references/todos.md` |
   | "I paid X" / split / "who owes whom" / settle up | EXPENSE | `references/expenses.md` |
   | a delay/gate/cancellation, a reroute, a delay claim, the post-trip review | DISRUPTION | `references/disruption.md` |
   | "from now on…" / a correction / a preference / "that's wrong" | ADJUST | `references/checklists.md` §ADJUST |
   | "explain" / "what is" / a jargon term | EXPLAIN | `references/glossary.md` |
   | "show the trip" / "card" / "settle-up board" / "packing status" | DASHBOARD | `references/checklists.md` §DASHBOARD |
   | a possible safety/entry/health flag | SAFETY | read the safety-boundaries file (index above) |
   | none of the above, on-topic | TALK | `travel-concierge-voice` |

5. **The hard rules apply to every reply** (below). 
6. **Verify & reply.** After any write, run a verification `SELECT` in a **separate** call;
   reply compact + Telegram-friendly, in the tenant's language, **quoting the numbers/
   times you just read**, ending with **one** concrete next step. One `sqlite3` statement
   per call — **never** chain INSERT+SELECT (a mid-call error lands the write but errors
   the call; a blind retry double-writes).

### §TRANSIT — live route / transit Q&A (the OV core, the common path)

Anything about *getting somewhere* — "how do I get to X", trains/buses now, "is my flight
on time", driving time, "what's the fastest way". Do **not** answer from memory.

1. Get the active trip + `home_city` from preflight (origin defaults to `home_city`;
   destination from the trip or the message).
2. **Call the `travel` tool this turn** (never `web_search` for routes; never invent a
   time). Pick the action (`references/transit.md`): `transit` for door-to-door public
   transport (routes, transfers, **live delays/platform**), `plan` for a free-form
   flight/journey question, `distance` for driving time. A failed call surfaces an
   **actionable error** — never an empty "all clear".
3. **Quote the tool's result** — depart/arrive times, line/platform, transfers, duration —
   and translate jargon for a newcomer (`references/glossary.md`).
4. If it's a leg they've **booked**, offer to save it (BOOKING) and to `monitor=1` it. If
   they ask "remind me when to leave", that's leave-by math → §ITINERARY / `schedule.md`.
5. Link out for tickets; **never book or pay**.

### §ITINERARY — build / edit the day-by-day schedule

1. Resolve the trip + day (`day_date`); parse the time(s) from the tenant's words
   (`references/datamodel.md` date parsing).
2. Write the itinerary row(s) — **one INSERT per item** (`references/schedule.md`), the
   source/assumption in `notes`. One `sqlite3` call per statement.
3. For a timed item with a travel leg, compute **leave-by** = scheduled start − live
   door-to-door duration (re-pull via `travel`, hard rule ②) − a buffer; tell them the
   leave-by time, not just the event time.
4. **Verify** with a separate SELECT; reply with the day laid out in order, quoting times.

## ⚠️ HARD RULE: No vibe-served facts

**Never state a time, price, platform, duration, delay or balance without reading it from
the database or calling the `travel`/`web_search` tool in the same turn.** No "it's about
two hours" from memory. Quote the source value. If you haven't queried this turn, say "let
me check" and run it. A failed tool call is an **error to surface**, never a fabricated
"all clear" or an empty result.

## ⚠️ HARD RULE: Verify live before travel

Flight/train/bus times **change**. Before any leave-by, departure reminder, or "you're
fine" on a booked leg, **re-pull the live status via `travel`** (and for a monitored leg,
record it with `monitor_transport.py`). Yesterday's status is not today's.

## ⚠️ HARD RULE: Link out — never book or pay; advisory-only on entry/health

We surface options and **links**; we **never** complete a booking, enter payment, or claim
to have reserved anything. Visa / entry / passport / vaccination / insurance answers are
**advisory only — verify with official sources** (`references/safety-boundaries.md`). Never
assert an entry requirement as settled fact.

## ⚠️ HARD RULE: Adjustments go to the data plane — never the bundle or the global SOUL

When the tenant customizes the Talent ("always book aisle seats", "we split 3 ways", "stop
the morning briefing", "Schiphol is our home airport", "reply in Dutch"), the change lands
in this Talent's **own data-plane files**, which converge never touches — **never** edit the
shipped bundle under `~/.hermes/skills/talents/oteny-travel-talent/`, and **never** write to
the global SOUL (`~/.hermes/data/_overrides/soul-override.md`). Route by kind (full checklist
in `references/checklists.md` §ADJUST):

| The adjustment is… | Append/merge into |
|---|---|
| a durable **fact/preference** (home airport, default currency, "I prefer aisle seats") | `~/.hermes/data/oteny-travel-talent/memory.md` (one line) |
| a **rule / behavior / voice** change (never auto-book, split evenly, no 8am briefing, terse, greet in Dutch) | `~/.hermes/data/oteny-travel-talent/overrides.md` (a delta, consolidated, sectioned — never a copy of the base) |

`preflight.py` surfaces both each turn, so the change takes effect on the **next** message
without a redeploy.

## Cron role (monitor / briefing / review / EU261)

When a trip-scoped job fires (created by the new-trip / add-flight checklists via
`scripts/provision_cron.py`, bounded to the trip window so there is **zero idle cost** when
no trip is active), follow `references/disruption.md`: the monitor messages only on a
**change**, the briefing only **within** the window, and the review/EU261 one-shots run
once and self-expire. Never fabricate a status, a delay, or "nothing to report" — send the
quiet result (`[SILENT]`) when there is genuinely nothing.

A tenant first set up on an older version may still hold **old-shape** (open-interval)
trip crons that fire far from the trip; the `0001_windowed_trip_crons` migration
(`references/migrations.md`) swaps them to the windowed shape and runs automatically via
the `MIGRATIONS:` triage guard — you never hand-fix crons.

## Common Pitfalls

- **Answering a route/time from memory.** Always call `travel` this turn and quote it.
- **`web_search` for a route.** Steer all "getting somewhere" intent to the `travel` tool.
- **Chaining INSERT+SELECT** in one `sqlite3` call — split them; verify with a separate read.
- **Forcing a group.** A bot can't create a group or add humans; DM is the default. Group
  behaviours apply only when `group_chat_id` is set.
- **Editing the bundle to "remember" a preference** — it's wiped on the next converge.
  Adjustments go to `memory.md` / `overrides.md` (above).
- **An idle daily cron.** Crons are trip-scoped and self-expiring; never register an
  always-on daily job (it bills a free talent for nothing).
