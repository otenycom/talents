# trip-planner — Live Transit & Door-to-Door Routing (the OV core)

Everything about **getting somewhere** goes through the **`travel` tool** — structured Google
routing (real stops/lines/times, the **live departures board** via `action: departures`,
door-to-door), with grounding only for free-form `plan`/flight questions. **Never** `web_search`
for a route, and **never** a time from memory. **Every route reply also ends with a real map
deeplink** from `maplink.py` (below). This file is the recipe book; the hard rules live in
[`SKILL.md`](../SKILL.md).

## Pick the `travel` action

| The tenant asks… | `action` | What to pass |
|---|---|---|
| public transport door-to-door (train/bus/tram/metro, transfers, the itinerary) | `transit` | plain origin + destination place names (+ "now"/a time) |
| "when's the next one? / is there an earlier (or later) tram/train?" — the live departures board | `departures` | origin + destination place names |
| flight **options** / booking / a free-form journey or itinerary question | `plan` | the whole question in `query` (e.g. "flights AMS→LIS 10 Sep morning") |
| driving distance / time between two places | `distance` | the two place names |
| "where/what is X", a place/station lookup | `place_lookup` | the place name |

**A specific flight's live STATUS / gate / terminal / delay / cancellation is NOT a `travel`
action — call the dedicated `flight_status` tool** (pass the flight number, e.g. `KL1001`). It
returns structured status/gate/delay from an aviation feed; **never** `web_search` or `travel
plan` a flight's status (those invent gates and numbers). If a flight isn't found or the feed
is down, it says so + gives a Google Flights link — hand that, never a guessed gate.
**`flight_status` is the COMPLETE flight answer — quote ONLY its fields and stop.** Do NOT
follow it with a `travel`/`plan`/`web_search` call to "enrich" the flight (that's the
fabrication surface). If the tool returned no gate, say **"gate not yet assigned"** — never a
"typical D-gate" or a guessed gate; and don't add an aircraft type/registration the tool
didn't return.

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
3. **Quote the structured result**: depart → arrive times (**already in local time — don't
   re-convert**), the line(s)/operator + vehicle, each transfer, total duration. *(Google
   does not return platform/track or an explicit delay number — never state those as fact; the
   deeplink in step 4 opens the app that shows the platform.)* For a newcomer, translate
   ("layover = the wait between connections", `glossary.md`). **Never invent a
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

## "When's the next one?" — the live departures board

Call **`travel` with `action: departures`** (origin + destination) — it returns the next real
departures from Google ("Tram 1 from Surinameplein: next 19:31 · 19:38 · 19:46"), worldwide.
This is the answer to "wanneer komt het? / when does it come? / is there an earlier one?".

- **Quote the times verbatim** — they are already the owner's local wall-clock (the tool
  localizes them via the stop's timezone). **Never re-do the timezone math yourself.**
- If the board can't be reached (a `fallback_hint`/error comes back), **follow the hint**:
  hand the `maplink.py` deeplink + the 9292 live board and say you couldn't fetch live times.
- **Never invent "next at 08:51"**, a frequency, or a delay. For an **NL stop** the board
  *also* folds in the live **OVapi** feed — a delay (`+2 late`), the train **spoor** (and
  `spoor 9 (was 5)` on a change), and a **⚠️ service alert**: **quote those when the board
  shows them** (real structured feed, not a guess) and surface a ⚠️ alert prominently. Outside
  NL (or when the feed had nothing) Google gives *times* only — no delay/platform — so don't
  state those (the deeplink opens the app that does). Either way: **quote exactly what the
  board returned this turn, never invent it.**
- **Don't *redundantly* re-call `travel` for the same route you already have** (reuse the result).
  But the board gives *times*, not disruptions — so **if the user asks about works / closures /
  "any delays?", `web_search` IS the right source** (planned works and diversions are real and
  indexed): **cite the source it returns** and frame it as a report ("Per GVB, works at Surinameplein
  from 4 July…"), **never** an invented closure/relocated-stop/exact-distance the source didn't state.
  Full discipline (cite, don't invent, treat a photo/sign as possibly stale): [`disruption.md`](disruption.md).

## Notes that keep it grounded

- **Live before travel (hard rule ②).** A status pulled yesterday is stale — re-pull
  before any leave-by or "you're fine".
- **Times come back already in local wall-clock** — the `travel` tool localizes each stop's
  time via that stop's own timezone, so quote them verbatim and **never re-convert**. For a
  zone-crossing trip, label each end ("dep 09:40 AMS / arr 11:55 WEST").
- **Door-to-door, not station-to-station.** Include the first/last mile (walk to the stop,
  the metro to the airport), because the **leave-by** the tenant cares about starts at
  *their door*.
- **Deeplink-first, grounding-assisted.** The grounded `travel` call gives the in-chat
  summary; the **`maplink.py` deeplink is what the user actually navigates with** — real
  live routing in their own map app, the authoritative source that stays correct when the
  prose is wrong. Always emit it. Grounding is **not** a substitute for a real map: it can
  fabricate a stop/line/closure, so anything specific that `travel` didn't confidently
  return goes to the deeplink, not to memory. (One grounded `travel` call is priced like a
  `web_search` call, so it does **not** trip the ask-first paid-tool rule.) *The structured
  real-time path is now live: `action: transit` for the door-to-door itinerary and
  `action: departures` for the live board — both worldwide, in local time. Explicit
  delay-minutes + platform/track aren't in Google's own data, but for **NL** stops the
  `departures` board now folds in the **OVapi live feed** (delay-minutes + spoor + service
  alerts) automatically — quote them when present; outside NL the deeplink opens the app that
  shows them.*
