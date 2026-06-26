# trip-planner — Plain-Language Glossary (say it in human words)

New travellers don't all know these terms. The table gives the plain meaning + why it
matters. Use it to teach the vocabulary **gradually**: explain plainly while the tenant is
new, then **fade the jargon in as they settle** so they learn the words without being
lectured. Never hand a newcomer a bare term they can't read.

## Fade the jargon in as the tenant settles

Gauge how settled they are — mainly by **how long / how many trips** they've used the bot
(`SELECT COUNT(*) FROM trips;`), and by whether they use the terms themselves:

- **New (first trip / first days):** lead with **plain words + why it matters**, every time.
  → `you'll have a layover in Madrid (a wait between connecting flights) of about 90 min —
  enough to change planes without rushing`
- **Settling (a few trips in):** the **real term first with a short tag**.
  → `90-min layover in Madrid (the connection wait)`
- **Settled (plans fluently):** the term **bare**.
  → `90-min layover MAD`

**Override toward plain words** the moment they ask "what's X?" or seem unsure.

## The terms (term → in plain words → why it matters to you)

| Term | In plain words | Why it matters to you |
|---|---|---|
| leave-by | the time you must walk out the door | miss it and you miss the flight/train — it's the number I anchor on |
| door-to-door | the whole journey from your door to the destination, not just the train ride | the real travel time, including the walk and the first/last mile |
| layover / stopover | the wait between two connecting flights | too short risks a missed connection; too long wastes a day |
| transfer / connection | changing from one train/flight to the next | the moment things most often go wrong — I build in a buffer |
| PNR / booking reference | the code that identifies your booking | you quote it to the airline/hotel; I store it to track your leg |
| gate | the airport door your flight leaves from | it can change late — that's one thing the monitor watches |
| boarding pass | the ticket that lets you onto the plane | check in to get it; some airlines charge to print at the airport |
| check-in (flight) | confirming you're flying + getting your pass | opens ~24–48h before; the cut-off is well before departure |
| check-in / check-out (hotel) | when you can take / must leave the room | gaps here decide whether you need luggage storage or an early arrival plan |
| carry-on / cabin bag | the bag you bring onboard | size/weight limits vary by airline — worth checking before you pack |
| checked bag / hold luggage | the bag that goes in the plane's hold | usually costs extra and adds time at both ends |
| EU261 | the EU rule that pays you for big flight delays/cancellations | a ≥3h arrival delay on an eligible flight can mean €250–€600 — I'll draft the claim |
| extraordinary circumstances | causes outside the airline's control (most weather, strikes) | when these cause the delay, EU261 compensation usually doesn't apply |
| visa | official permission to enter a country | some nationalities need one in advance — always verify with the official source |
| ESTA / eTA | a quick online travel authorization (e.g. USA / Canada) | not a visa, but required before you fly — apply early, verify officially |
| Schengen | the European zone with no internal border checks | days inside it can be capped (90/180) for some passports — check yours |
| passport validity | how long your passport must be valid past your trip | many countries require 6 months — a near-expiry passport can deny boarding |
| customs | the checkpoint for what you may bring across a border | matters for gifts, food, duty-free limits |
| jet lag | tiredness from crossing time zones | why I show times in both zones and suggest sane arrival/leave-by times |
| red-eye | an overnight flight arriving early morning | cheap and time-saving, but plan for a tired arrival day |
| half-board / full-board / all-inclusive | how many meals the stay includes | changes your food budget + how I split expenses |
| even split | a shared cost divided equally across the party | the default; I can do custom splits when only some of you shared something |
| settle up | working out who owes whom so everyone's square | I compute the fewest transfers (e.g. "Anna owes Ben €84") |
| itinerary | your day-by-day plan | the schedule I build, with leave-by times for the timed bits |
| great-circle distance | the shortest distance between two airports | it sets the EU261 compensation band (≤1500 / 1500–3500 / >3500 km) |

For entry/visa/health specifics, always **verify live** with the official source — these
change and depend on nationality (`../../references/safety-boundaries.md`).
