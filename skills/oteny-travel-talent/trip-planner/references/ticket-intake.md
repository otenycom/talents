# trip-planner — Ticket intake: a forwarded e-ticket → a saved booking (ground truth)

When the tenant **forwards a flight or train e-ticket** (a PDF or a photo/screenshot of a
ticket or boarding pass), read it and auto-fill a `bookings` row. The ticket is **ground
truth** — far better than asking them to retype times — so a forwarded ticket is the best
way to record a booked leg. We still **never book or pay**; we record what they already
booked. Schema: [`datamodel.md`](datamodel.md); the manual path + deep links:
[`bookings.md`](bookings.md).

## The flow (parse → save → verify → reply)

1. **Active trip.** Get it from preflight. No active trip yet? Create/confirm one first
   (`checklists.md` §TRIP) — a booking needs a `trip_id`. A solo DM is fine.
2. **Parse the ticket with the `parse_document` tool**, passing the forwarded file as
   `source` and **the exact prompt in "Extraction prompt" below** as `prompt`. One call;
   if several PDFs were forwarded (e.g. a base ticket + a supplement), pass them together so
   it reconciles them into one booking. `parse_document` returns `{"text": "<json>"}` — read
   the JSON out of `text`.
3. **`is_ticket: false`** → it wasn't a ticket (an invoice, a passport, a random PDF). Say
   what you saw and ask what they'd like to do — **don't** invent a booking.
4. **Write one `bookings` row per leg** (`datamodel.md`), `kind` = the ticket `mode`
   (`flight`/`train`), `monitor=1` (it has a real carrier + number + time), `booking_ref`
   = the flight/train number or PNR, `notes` = `"from forwarded e-ticket"`. One `sqlite3`
   statement per call; read the new `id` back to verify (never chain INSERT+SELECT).

   ```bash
   sqlite3 ~/.hermes/data/oteny-travel-talent/trips.db "INSERT INTO bookings (trip_id, kind, title, from_loc, to_loc, start_ts, end_ts, carrier, booking_ref, monitor, cost, currency, notes) VALUES (<trip_id>,'flight','AMS→LIS','Amsterdam','Lisbon','2026-09-10T09:40','2026-09-10T11:55','TAP','TP661',1,180,'EUR','from forwarded e-ticket');"
   ```

   - A **round-trip** ticket = **two** legs (outbound + return) → two rows. A multi-segment
     flight (e.g. AMS→LIS→FNC) = one row per segment. Put the **total price on the first
     leg only** (others `NULL`) with a note, so the spend recap isn't double-counted.
5. **If any leg is a flight, schedule its EU261 one-shot** (so a ≥3h delay is auto-checked
   the day after arrival) and the windowed monitor — exactly as [`bookings.md`](bookings.md)
   step 4:

   ```bash
   python3 ~/.hermes/skills/talents/oteny-travel-talent/scripts/provision_cron.py --trip <trip_id> --json
   ```
   Register each `to_create` job with the `cronjob` tool, **pinning `model` + `provider`**.
6. **Verify + reply.** Run a verification `SELECT` in a separate call; confirm the saved
   leg(s), **quoting the times/route you read back**, note it's being watched (`monitor=1`),
   and offer to add it to the day plan (`schedule.md`). End a "getting there" leg with the
   `maplink.py` deeplink to the departure station/airport (hard rule ③).

## Extraction prompt (pass this VERBATIM as `parse_document`'s `prompt`)

> You are parsing one or more forwarded travel documents (flight or train e-tickets /
> boarding passes). Some attachments may be unrelated (an invoice, a passport) — ignore
> those. Reply with **ONLY** a JSON object, no markdown, no prose:
>
> ```
> {"is_ticket": true, "mode": "flight"|"train",
>  "legs": [{"from": "AMS", "to": "LIS", "from_name": "Amsterdam", "to_name": "Lisbon",
>            "start_ts": "YYYY-MM-DDTHH:MM", "end_ts": "YYYY-MM-DDTHH:MM",
>            "carrier": "TAP", "number": "TP661"}],
>  "round_trip": false, "total_price": 0.0, "currency": "EUR"}
> ```
>
> Rules:
> - **Dates are European — the day comes FIRST.** `05/03/2026` = 5 March 2026, never 3 May.
>   Times are 24h, local to the departure point; use `00:00` if no time is printed.
> - `legs`: one object **per travelled segment**, in chronological order. A **round-trip**
>   ticket has the outbound **and** the return as separate legs (set `round_trip: true`).
>   A multi-stop flight has one leg per flight number.
> - `from`/`to`: IATA code for a flight, station name for a train. `from_name`/`to_name`:
>   the human city/station name.
> - `carrier` + `number`: airline + flight number (e.g. `TAP` `TP661`) or rail operator +
>   train/service number; join multiple operators on one leg with ` / `.
> - `total_price`: the **sum across all attachments**, as a number; `0` if not printed.
> - If **no** attachment is a travel ticket, reply `{"is_ticket": false}`.
>
> **CRITICAL — a supplement or a seat reservation is NOT a return trip.** A booking often
> arrives as two documents: the travel ticket **plus** a separate supplement / reservation
> /surcharge. The second one is an **extra fee for the same journey**, not a return leg —
> **add its price to `total_price`** and do **not** create an extra leg from it. Read the
> ticket *type* in its own language to decide one-way vs round-trip; a fare/reservation word
> is an add-on, never a direction:
>
> | Country / operator | one-way | round-trip | add-on (price only, NOT a return) |
> |---|---|---|---|
> | 🇳🇱 NL (NS) | Enkele reis | Retour | **Toeslag** (Intercity-direct surcharge) |
> | 🇩🇪 DE (DB) | Einfache Fahrt / Hinfahrt | Hin- und Rückfahrt | **Reservierung** / Sitzplatzreservierung; Sparpreis/Flexpreis are fares |
> | 🇫🇷 FR (SNCF) | Aller simple | Aller-retour | **Réservation** (TGV/Intercités seat — already included, not a return) |
> | 🇧🇪 BE (SNCB/NMBS) | Enkele reis / Aller simple | Heen en terug / Aller-retour | seat **reservation** |
> | 🇮🇹 IT (Trenitalia/Italo) | Solo andata | Andata e ritorno | **Prenotazione** |
> | 🇪🇸 ES (Renfe) | Solo ida | Ida y vuelta | seat reservation |
> | 🇬🇧 UK | Single | Return | **Seat reservation** |
>
> When unsure whether a second document is a return or a supplement, treat it as a
> **supplement** (add the price, no extra leg) — under-counting a leg is safer than
> inventing a return journey the traveller doesn't have.

## Notes that keep it honest

- **The ticket is the source; quote it.** Record `notes='from forwarded e-ticket'` so a
  later correction is a trivial `UPDATE`. If the parse is uncertain on a field, say so and
  confirm with the tenant rather than guessing.
- **Never fabricate a missing field.** If a price or a time isn't on the ticket, leave it
  `NULL` and say "no time printed" — don't invent one (the hard rules in `SKILL.md` apply
  here too).
- **We don't book.** Parsing a confirmation records *their* booking; it never creates,
  holds, or pays for anything.
