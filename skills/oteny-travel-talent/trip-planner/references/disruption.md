# trip-planner — Disruption: monitor, reroute, EU261 claim, post-trip review

The cron-driven half of the engine, re-aimed from Wilma's back-office *Transport Review*
to the **end-user traveller**. Four flows: the **monitor** (watch booked legs), the
**reroute** (act on a change), the **EU261 claim** (delay compensation), and the
**post-trip review** (Wilma's 7-step, user-facing). All obey the hard rules — especially
**no fabricated status** and **verify live** (`SKILL.md`).

**⚠️ A disruption you report must be SOURCED — cite it, don't invent it (and don't suppress it).**
`web_search` IS a valid, useful source for planned works, diversions, and disruptions — Google
indexes the GVB / NS / municipal announcements and they are **real** (e.g. the Surinameplein Oranje
Loper works + the 4 July zomerdienstregeling are genuine). Use it for "any delays / storingen?" when
the structured `transit`/`departures` board doesn't carry the answer. Two rules keep it honest:

1. **Cite it + frame it as a report, not a live feed.** Lead with the source — "Per GVB, there are
   works at Surinameplein from 4 July…" with the link the tool returns — **not** a bare "⚠️ CRITICAL
   live disruption" as if from a guaranteed real-time feed. (Structured times are realtime-fused; a web
   result is a *report* that may be slightly stale or imprecise on exact specifics.)
2. **Quote what the source says; never invent a specific it didn't.** No made-up exact distance
   ("40 m"), bridge number, platform, or **train number** the source didn't state. If two results
   conflict (e.g. two different numbers for one departure), **say so and hand the live board** — don't
   pick one and assert it. Don't agree a closure exists just because the user guessed it.

**Treat a forwarded photo / sign as possibly STALE — cross-check it.** (A real case: a stop's closure
sign was left up by the workers but the stop was open; the web / live board was correct.) Always end
with the live board (`transit.md` step 4) as the floor. *(FLIGHT status → prefer the structured
`flight_status` tool for gate/delay; web is the context fallback — still cite, never an invented gate.)*

## §MONITOR — watch booked flights/trains within the window (cron)

The monitor cron fires every few hours **only within the trip window** — from **2 days
before** the first departure through **1 day after** the trip ends (to catch a late arrival
or an airline-claim window). The planner sizes it as a day-bounded cron expression (never an
open interval, so a far-future trip costs nothing until its window opens), and the script
gates it. The deterministic backbone is `scripts/monitor_transport.py`; the LLM only calls
the status tool and messages on a change — **`flight_status` for a flight leg** (structured
gate/delay), `travel` for a train.

1. List the legs due a check:
   ```bash
   python3 ~/.hermes/skills/talents/oteny-travel-talent/scripts/monitor_transport.py --due
   ```
   `NONE DUE` → reply `[SILENT]`. Stop. (That is how a far-future trip costs nothing.)
2. For **each** due leg, fetch the live status — **`flight_status` for a flight** (flight no.;
   structured status/gate/delay; the primary source), `travel` for a train. A failed lookup is an
   **error to surface**, never an empty "on time". `web_search` is fine for the *reason*/context
   (cite it); take the gate/delay numbers from the structured tool, never a guessed one.
3. Record each fetched status (the diff is deterministic):
   ```bash
   python3 ~/.hermes/skills/talents/oteny-travel-talent/scripts/monitor_transport.py --update --leg <id> --status "delayed 40m, gate B7"
   ```
   `UNCHANGED` → say nothing for that leg. `CHANGED` → go to §REROUTE.
4. Message the trip group/DM **only** for CHANGED legs; otherwise `[SILENT]`.

## §REROUTE — act on a delay / gate change / cancellation

1. State the change plainly, quoting the live status ("TP661 now departs 11:20, was 09:40
   — delayed 1h40").
2. **Recompute the leave-by** (`schedule.md`) from the new time and tell them the new
   leave-by.
3. If the change **breaks a connection or the day plan**, call `travel` (`action: plan`)
   for **alternatives** and present 2–3 with the trade-off + a link. **Link out — never
   rebook or pay.**
4. If it's a **≥3h arrival delay or a cancellation**, flag that it may be **EU261-claimable**
   and that the post-arrival cron will draft the claim (or do it now on request — §EU261).

## §EU261 — flight delay-compensation claim (one-shot cron, day after arrival)

Adapted from Wilma's Step 6. Runs the day after a monitored flight's arrival; or on demand.

1. **Re-pull the live flight via the `flight_status` tool** (pass the flight number) — it
   returns structured `status`, `delay_min`, `cancelled`, terminal/gate, and great-circle
   `distance_km`. On time → `[SILENT]`. Take the gate/delay **numbers** from `flight_status` (the
   structured source), never a guessed one; `web_search` is fine for the *reason*/context, cited.
2. **Eligibility** — EU261/2004 applies to a flight **departing an EU/EEA airport** (any
   airline) **or arriving in the EU/EEA on an EU/EEA airline**, when the **arrival delay is
   ≥ 3 hours**, the flight was **cancelled** (<14 days' notice), or boarding was denied —
   and the cause was **not** an extraordinary circumstance (most weather/ATC strikes are
   exempt). State eligibility in one line; if borderline, say "likely eligible, confirm".
3. **Amount by great-circle distance** (use `flight_status`'s `distance_km`; quarantined thresholds):
   - ≤ 1500 km → **€250**
   - 1500–3500 km, **and all intra-EU flights > 1500 km** → **€400**
   - > 3500 km (non-intra-EU) → **€600**
   (A 3–4h delay on a long-haul >3500 km leg may be halved to €300 — note it if so.)
4. **Where to claim** — the airline's own claim form/email (find it via `travel`/
   `web_search`); mention the national enforcement body / a claims service as a fallback,
   **without** endorsing a paid agency.
5. **Draft a ready-to-send claim message** — tailored to the flight number, date, route,
   scheduled vs actual arrival, the delay duration, and the amount + legal basis (EU261/
   2004). Hand it to the tenant to send; **we don't submit it**.

> Output the claim as: **Eligibility** (one line) · **Compensation** (amount + basis) ·
> **Where to claim** (URL/email) · **Draft message** (ready to send). Plain language; define
> "EU261" for a newcomer (`glossary.md`).

## §POST-TRIP REVIEW — Wilma's 7-step, user-facing (one-shot, day after the trip)

A background review (no greeting/sign-off), **facts only**, read-only on the trip. Work
through the steps in order; ground every fact in a DB read or a tool result.

1. **Identify the trip** — name, destination, dates, the party. Read it from the DB.
2. **Flight/train status** — for each leg that had a booking, look up the **actual vs
   scheduled arrival** (`travel`/`web_search`); note any ≥3h delay, cancellation, or
   rebooking. (Only this trip's legs.)
3. **Route assessment** — was the chosen mode/route sensible (train vs taxi vs combo, the
   right station, a closer/cheaper option missed)? Suggest improvements for next time.
4. **Timing** — did the leave-by buffers hold? Any too-tight connection or wasted wait?
5. **Spend recap** — run `scripts/settle_up.py --trip <id>`: total spend per currency + the
   final settle-up ("Anna owes Ben …"). Quote it.
6. **What went well / what to improve** — 2–3 concrete bullets each, from the data.
7. **Claimable delays** — surface any leg from step 2 that clears the EU261 bar (§EU261),
   with the draft, so nothing claimable is left on the table.

Reply with a tight, scannable review (headline + the steps as short bullet groups), in the
tenant's language. **No invented facts** — if a leg has no booking/no data, say "no data"
rather than assuming. After it runs, the trip's recurring crons have already self-expired
(bounded `repeat`), so nothing lingers.
