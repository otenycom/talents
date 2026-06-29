# trip-planner — Live Transit & Door-to-Door Routing (the OV core)

Everything about **getting somewhere** goes through the **`travel` tool** (grounded
live web — routes, transfers, **live delays & platform changes**, flights, driving) —
**never** `web_search` for a route, and **never** a time from memory. **Every route reply
also ends with a real map deeplink** from `maplink.py` (below). This file is the recipe
book; the hard rules live in [`SKILL.md`](../SKILL.md).

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
2. **Call `travel` exactly ONCE this turn** with the action above. Treat a tool failure as
   an **actionable error** — say "I couldn't reach live transit data" and hand over the
   deeplink (step 4), **never** a fabricated route or an empty "no trains". On a failure
   **STOP**: no `web_search` fallback, no retry of the same call, no probing variations
   (≤2 tool calls for a transit turn — preflight + one `travel`). Grinding searches is slow,
   costly, and amplifies fabrication. **Don't re-resolve what you already have**: a place or
   route you looked up earlier this conversation is still valid — reuse that result rather
   than re-calling `travel` for it (the broker caches, so a re-ask just wastes a turn).
3. **Quote the grounded result**: depart → arrive times, the line(s)/operator, platform,
   each transfer, total duration, and any **live delay/platform change**. For a newcomer,
   translate ("layover = the wait between connections", `glossary.md`). **Never invent a
   specific** boarding stop, line↔stop assignment, network change, or closure: if `travel`
   wasn't confident and specific, say so plainly and let the deeplink (step 4) carry the
   routing — do NOT name a stop from memory, and do NOT ratify the user's guessed line/route
   with made-up specifics.
4. **End with the map deeplink(s).** Run `maplink.py` and paste its links — the user's
   live, authoritative routing in their own app, the source of truth even if the prose above
   is off:

   ```bash
   python3 ~/.hermes/skills/talents/oteny-travel-talent/scripts/maplink.py --origin "<origin>" --destination "<destination>" --mode transit
   ```

   Match `--mode` to the trip (`transit`/`walking`/`driving`); `--no-nl` for a non-NL trip;
   `--apple` only when an iPhone-user preference is recorded in `memory.md`/`overrides.md`.
   For an NL transit trip it also prints the **9292 live-departures** board for the
   destination stop — that is the honest answer to "when's the next one?". **Never** draw a
   map with `image_generate` (a fabricated picture); link out instead.

   **If the user wants to SEE the route on a map** (not just get directions), add
   `static_map: true` to the `travel` call in step 2 — the result then carries a **real
   Google Static Map** image of the route (a `MEDIA:` reference); paste that reference so the
   image shows in-chat. It's a real Google map drawn from the route, **not** an
   `image_generate` fabrication. The deeplink still goes too — the image is the picture, the
   deeplink is what they navigate with.
5. **Offer the next step**: if it's a leg they'll take, offer to save it as a BOOKING
   (`bookings.md`) and `monitor=1` it; if they want a reminder, that's **leave-by** math
   (`schedule.md`). For NL pay-as-you-go transit, end with the **check-out reminder** offer
   (`checklists.md` §CHECKOUT) unless `memory.md` says "never remind". Link out for tickets —
   **never book or pay**.

## "When's the next one?" — honest real-time

There is **no live in-chat departure board yet**. So answer "wanneer komt het?" / "when does
it come?" with:
1. the line **frequency** *only if grounded data gives it* ("roughly every 8–10 min") — never
   a clock time you don't have, and
2. the **9292 live-departures deeplink** for that stop from `maplink.py` (the
   `…/locaties/<stop>/departures` link it prints for an NL transit trip).
**Never invent "next at 08:51."** A made-up time is worse than the link.

## Notes that keep it grounded

- **Live before travel (hard rule ②).** A status pulled yesterday is stale — re-pull
  before any leave-by or "you're fine".
- **Times are the owner's local wall-clock** unless the route crosses zones — then state
  the timezone for each end ("dep 09:40 AMS / arr 11:55 WEST").
- **Door-to-door, not station-to-station.** Include the first/last mile (walk to the stop,
  the metro to the airport), because the **leave-by** the tenant cares about starts at
  *their door*.
- **Deeplink-first, grounding-assisted.** The grounded `travel` call gives the in-chat
  summary; the **`maplink.py` deeplink is what the user actually navigates with** — real
  live routing in their own map app, the authoritative source that stays correct when the
  prose is wrong. Always emit it. Grounding is **not** a substitute for a real map: it can
  fabricate a stop/line/closure, so anything specific that `travel` didn't confidently
  return goes to the deeplink, not to memory. (One grounded `travel` call is priced like a
  `web_search` call, so it does **not** trip the ask-first paid-tool rule.) *A structured,
  real-time transit-data path — a live departures board + correct door-to-door legs — is the
  next upgrade; until it lands, the deeplink + the 9292 board cover the live gap.*
