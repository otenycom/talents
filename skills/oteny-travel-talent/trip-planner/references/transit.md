# trip-planner — Live Transit & Door-to-Door Routing (the OV core)

Everything about **getting somewhere** goes through the **`travel` tool** (Gemini-grounded
live web — routes, transfers, **live delays & platform changes**, flights, driving) —
**never** `web_search` for a route, and **never** a time from memory. This file is the
recipe book; the hard rules live in [`SKILL.md`](../SKILL.md).

## Pick the `travel` action

| The tenant asks… | `action` | What to pass |
|---|---|---|
| public transport door-to-door (train/bus/tram/metro, transfers, live delays/platform) | `transit` | plain origin + destination place names (+ "now"/a time) |
| a flight option or status, or any free-form journey/itinerary question | `plan` | the whole question in `query` (e.g. "flights AMS→LIS 10 Sep morning, status of TP661 today") |
| driving distance / time between two places | `distance` | the two place names |
| "where/what is X", a place/station lookup | `place_lookup` | the place name |

Ferry, walk and bike legs ride inside a `transit`/`plan` query ("…including the ferry").
**Rental cars**: research with `plan` (options/depots) + `web_search` for prices; link out.

## The recipe (entry → check → reply), every transit turn

1. **Resolve origin + destination.** Origin defaults to the trip's / `profile.home_city`;
   destination from the trip or the message. If genuinely ambiguous, ask **one** question.
2. **Call `travel` this turn** with the action above. Treat a tool failure as an
   **actionable error** — say "I couldn't reach live transit data, let me retry / try
   again shortly", **never** a fabricated route or an empty "no trains".
3. **Quote the grounded result**: depart → arrive times, the line(s)/operator, platform,
   each transfer, total duration, and any **live delay/platform change**. For a newcomer,
   translate ("layover = the wait between connections", `glossary.md`).
4. **Offer the next step**: if it's a leg they'll take, offer to save it as a BOOKING
   (`bookings.md`) and `monitor=1` it; if they want a reminder, that's **leave-by** math
   (`schedule.md`). Link out for tickets — **never book or pay**.

## Notes that keep it grounded

- **Live before travel (hard rule ②).** A status pulled yesterday is stale — re-pull
  before any leave-by or "you're fine".
- **Times are the owner's local wall-clock** unless the route crosses zones — then state
  the timezone for each end ("dep 09:40 AMS / arr 11:55 WEST").
- **Door-to-door, not station-to-station.** Include the first/last mile (walk to the stop,
  the metro to the airport), because the **leave-by** the tenant cares about starts at
  *their door*.
- **No structured Maps API** in v1 (D69) — grounding covers the whole surface; one grounded
  `travel` call is priced like a `web_search` call, so it does **not** trip the ask-first
  paid-tool rule.
