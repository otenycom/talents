# trip-planner — Disruption: monitor, reroute, EU261 claim, post-trip review

The cron-driven half of the engine, re-aimed from Wilma's back-office *Transport Review*
to the **end-user traveller**. Four flows: the **monitor** (watch booked legs), the
**reroute** (act on a change), the **EU261 claim** (delay compensation), and the
**post-trip review** (Wilma's 7-step, user-facing). All obey the hard rules — especially
**no fabricated status** and **verify live** (`SKILL.md`).

**⚠️ A disruption is only real if a STRUCTURED live source says so.**
**Never invent a network change, a line/route reorganisation, a stop closure, "works on the
line", a relocated stop, or an accident to explain a route — and never agree a closure exists
because the user guessed it.** For **ground transit** (tram/bus/metro/train) we have **no live
delay/diversion feed**: Google's structured `transit`/`departures` carry times only — not
delays, closures, or platforms. So a `web_search`/grounded hit is **NOT** a confirming source —
it invents plausible specifics (a relocated stop "until some date", a line "split", an "accident
at HH:MM"). **For an ad-hoc "any delays / storingen on my tram now?" do NOT `web_search` it and
report the hits as fact**: answer "I don't have a live delay feed for local transit", give the
`departures` board (what IS live) + the **9292 / Google Maps live board** (`transit.md` step 4)
as the authoritative real-time source, and flag possible planned works only as "verify on the
live board", never a certain dated closure. *(FLIGHT status is the exception — grounding is the
documented fallback there until the structured flight source lands, but still cite-or-stand-down,
never an invented gate/number.)* A fabricated closure sends the traveller on an absurd detour —
exactly the failure this rule prevents.

## §MONITOR — watch booked flights/trains within the window (cron)

The monitor cron fires every few hours **only within the trip window** — from **2 days
before** the first departure through **1 day after** the trip ends (to catch a late arrival
or an airline-claim window). The planner sizes it as a day-bounded cron expression (never an
open interval, so a far-future trip costs nothing until its window opens), and the script
gates it. The deterministic backbone is `scripts/monitor_transport.py`; the LLM only calls
`travel` and messages on a change.

1. List the legs due a check:
   ```bash
   python3 ~/.hermes/skills/talents/oteny-travel-talent/scripts/monitor_transport.py --due
   ```
   `NONE DUE` → reply `[SILENT]`. Stop. (That is how a far-future trip costs nothing.)
2. For **each** due leg, call the **`travel` tool** for the live status (flight/train no. +
   date). A failed lookup is an **error to surface**, never an empty "on time".
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

1. **Re-pull actual vs scheduled arrival** via `travel`/`web_search` for the exact flight
   number + date. On time → `[SILENT]`. Never fabricate a delay.
2. **Eligibility** — EU261/2004 applies to a flight **departing an EU/EEA airport** (any
   airline) **or arriving in the EU/EEA on an EU/EEA airline**, when the **arrival delay is
   ≥ 3 hours**, the flight was **cancelled** (<14 days' notice), or boarding was denied —
   and the cause was **not** an extraordinary circumstance (most weather/ATC strikes are
   exempt). State eligibility in one line; if borderline, say "likely eligible, confirm".
3. **Amount by great-circle distance** (quarantined thresholds):
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
