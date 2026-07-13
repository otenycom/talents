# trip-planner — Bookings: record, deep-link, research (link out only)

The `bookings` table unifies transport legs + lodging + activities. This file is the SQL
+ the deals-research recipe. **We never book or pay** — we record what the tenant tells us,
research options, and surface **links**. Schema in [`datamodel.md`](datamodel.md).

> **⚠️ FIRST, for any deals/listing hunt: escalate the model, then drop back.** Hunting or
> verifying real bookable listings, rentals, tickets or offers (a live URL + a price the
> user may act on) is error-prone on the cheap model. Call
> **`switch_persona(task="live-inventory")`** before the hunt and relay its announcement
> to the user; when the hunt is done, call `switch_persona(task="live-inventory",
> done=true)` so ordinary chat stays cheap. Once per hunt, never per message. If the tool
> refuses or is unavailable, carry on — every listing you present must still be verified
> live before you call it bookable.

> **Forwarded an e-ticket?** When the tenant sends a **PDF or photo of a flight/train
> ticket**, don't ask them to retype it — parse it (it's ground truth) and auto-fill the
> row: [`ticket-intake.md`](ticket-intake.md).

## Record a booking (entry → verify → reply)

1. Classify `kind` ∈ flight/train/bus/car/ferry/hotel/airbnb/resort/activity. Pull what
   the tenant gave: `title`, `from_loc`/`to_loc`, `start_ts`/`end_ts` (ISO local),
   `carrier`, `booking_ref`, `cost`, `currency`, `deeplink`.
2. **Set `monitor=1` for a booked flight or train** (it has a real carrier + number +
   time) so the disruption cron watches it; lodging/activities are `monitor=0`.
3. Insert — one statement; then read the new `id` back to verify.

   ```bash
   sqlite3 ~/.hermes/data/oteny-travel-talent/trips.db "INSERT INTO bookings (trip_id, kind, title, from_loc, to_loc, start_ts, end_ts, carrier, booking_ref, monitor, deeplink, cost, currency, notes) VALUES (<trip_id>,'flight','AMS→LIS','Amsterdam','Lisbon','2026-09-10T09:40','2026-09-10T11:55','TAP','TP661',1,'https://flightaware.com/live/flight/TP661',180,'EUR','from forwarded confirmation');"
   ```
4. **If it's a monitored flight, schedule its EU261 one-shot** (list-first) so a ≥3h delay
   is auto-checked the day after arrival:

   ```bash
   python3 ~/.hermes/skills/talents/oteny-travel-talent/scripts/provision_cron.py --trip <trip_id> --json
   ```
   Register each `to_create` job with the `cronjob` tool, **pinning `model` + `provider`**.
5. Reply: confirm the saved leg, quoting the times you read back; offer to watch it
   (already on if `monitor=1`) and to add it to the day plan (`schedule.md`).

## Deep links (what to put in `deeplink` / surface)

Construct a **status/info link**, never a checkout link with payment:
- **Flight status** — a flight-tracker URL keyed on the flight number + date.
- **Train** — the operator's live-departures/journey page for the route.
- **Hotel/stay** — the property's own page or a maps link; if the tenant booked elsewhere,
  store their confirmation link.
- **Activity** — the venue/official page.
- **Getting there (every leg)** — **always** add the map deeplink from `maplink.py` so the
  tenant can navigate to the airport / station / hotel / venue in their own app:

  ```bash
  python3 ~/.hermes/skills/talents/oteny-travel-talent/scripts/maplink.py --origin "<from>" --destination "<to>" --mode transit
  ```

  Match `--mode` (`transit`/`walking`/`driving`); `--no-nl` for a non-NL trip. This is the
  same rule as a route reply (`SKILL.md` hard rules + `transit.md`): a "getting somewhere"
  answer never ships without a real map link.
Prefer the **official carrier/operator** page; quote the source so a correction is easy.

## Deals research (flights / hotels / car / activities) — research, never book

This is the same grounded recipe as live transit, just aimed at *options + price*:
1. Use the **`travel` tool** (`action: plan`) for flight/journey options and timings, and
   **`web_search`** for prices/availability/deals (both are grounded, list-priced like a
   search — they do **not** trip the ask-first paid-tool rule).
2. Present 2–3 concrete options with the trade-off (price vs time vs stops), each with a
   **link**. Quote the source + the as-of time — prices move.
3. Offer to **record** the chosen one as a booking (above). **Never** claim to have
   reserved, held, or paid for anything.

> **Paid scrapers / assisted booking are out of scope in v1** (backlog). If a tenant wants
> the bot to *complete* a booking, explain we link out only and that assisted booking is a
> future paid capability — then hand them the link.

## Edit / remove a booking

`UPDATE bookings SET <col>=… WHERE id=<id>;` after reading the id back (correct a time,
flip `monitor`, add a `deeplink`). To drop one: `DELETE FROM bookings WHERE id=<id>;`
(guarded by id — never an unguarded DELETE). Re-verify with a SELECT.
