# trip-planner — Data Model Reference

Canonical reference for the SQLite schema at `~/.hermes/data/oteny-travel-talent/trips.db`.
For *how* to write/read, see the per-intent checklists in `checklists.md` and the
domain references (`bookings.md`, `schedule.md`, `todos.md`, `expenses.md`). Resolve
the DB path from the one namespaced location — never hardcode a home directory.

The **executable** schema is the single shipped file `../../scripts/init.sql` (applied
idempotently at first-run: `sqlite3 …/trips.db < …/scripts/init.sql`). Never paste a
`CREATE TABLE` block — this doc describes the columns; `init.sql` creates them.

## Tables at a glance

| Table | Cardinality | What goes here |
|---|---|---|
| `trips` | one per trip | The trip itself: name, destination, dates, home city, status, optional group binding |
| `members` | many per group trip | The travel party (only populated when bound to a group) |
| `bookings` | many per trip | Transport legs + lodging + activities (unified). `monitor=1` = watched |
| `itinerary` | many per trip | The day-by-day schedule |
| `todos` | many per trip | Per-member prep (packing / documents / health / booking / admin) |
| `expenses` | many per trip | The shared-expense ledger |

The implicit join key is always `trip_id`. `members.id` is referenced (not FK-enforced)
by `todos.member_id` and `expenses.payer_member_id`.

## Columns (canonical)

**`trips`** (one per trip)
- `id` PK · `name` TEXT (e.g. "Our Trip to Lisbon") · `destination` TEXT · `start_date`/
  `end_date` TEXT `YYYY-MM-DD` (local) · `type` ∈ beach/city/ski/road-trip/family/
  business/other · `home_city` TEXT (origin for door-to-door routing; defaults from
  `profile.home_city`) · `status` ∈ `planning`/`active`/`past`/`cancelled` ·
  `group_chat_id` TEXT **nullable** (NULL = DM/solo; set only when bound to a Telegram
  group, resolved at runtime — never baked) · `created_ts` · `notes`.

**`members`** (many per group trip; `idx_members_trip`)
- `id` PK · `trip_id` · `telegram_user` TEXT (canonical id/username; **NULL** if added by
  name only) · `display_name` TEXT · `role` ∈ `lead`/`member`/`child` · `home_city` ·
  `notes`. `UNIQUE(trip_id, telegram_user)` where the user is set — one member row per
  speaker, so the group speaker→member map never double-inserts.

**`bookings`** (many per trip; `idx_bookings_trip`, `idx_bookings_monitor`)
- `id` PK · `trip_id` · `kind` ∈ flight/train/bus/car/ferry/hotel/airbnb/resort/activity ·
  `title` · `from_loc`/`to_loc` · `start_ts`/`end_ts` ISO local (departure/arrival, or
  check-in/check-out, or activity start/end) · `carrier` (airline / rail operator /
  hotel) · `booking_ref` (PNR / confirmation; for a flight or train this is also the
  natural leg number) · `status` (last-known live status — `on-time`/`delayed 40m`/
  `cancelled`/`gate B12`) · `monitor` 0/1 (1 = watched by the disruption cron) ·
  `deeplink` (the link we surface — **we link out, never book/pay**) · `cost` · `currency`
  · `notes`.

**`itinerary`** (many per trip; `idx_itinerary_trip_day`)
- `id` PK · `trip_id` · `day_date` `YYYY-MM-DD` · `time` `HH:MM` local (NULL = unscheduled/
  all-day) · `title` · `place` · `category` ∈ transit/meal/activity/lodging/admin ·
  `notes`.

**`todos`** (many per trip; `idx_todos_trip_member`)
- `id` PK · `trip_id` · `member_id` (members.id; **NULL** = whole-party / unassigned) ·
  `title` · `category` ∈ packing/document/booking/health/admin · `due` `YYYY-MM-DD`
  (NULL = no hard date) · `done` 0/1 · `notes`.

**`expenses`** (many per trip; `idx_expenses_trip`)
- `id` PK · `trip_id` · `payer_member_id` (who paid; **NULL** = the owner) · `amount` REAL
  · `currency` (defaults from `profile.default_currency`) · `category` (food/transport/
  lodging/activity/other) · `split_json` · `note` · `ts`.

## Conventions to know

### `bookings.monitor` — flag the legs the cron watches
Set `monitor=1` on a **flight or train** the tenant has booked (it has a real
`carrier` + `booking_ref` + `start_ts`), so the disruption cron picks it up
(`disruption.md`). Lodging/activities are not monitored. `status` starts NULL and is
updated by `monitor_transport.py` as live status changes.

### `bookings.notes` — quote your assumption / source
Record where a time or price came from (the `travel` tool result, the tenant's
forwarded confirmation), so corrections are trivially `UPDATE`-able.

### `expenses.split_json` — how the cost is shared
- `'even'` (default) → split equally across **every** `members` row for the trip.
- a JSON object `{"<member_id>": <share>, ...}` → custom split by weight or absolute
  amount. `settle_up.py` interprets both. A solo DM trip with no members has no one to
  settle with — log the expense for the spend recap only.

### Time storage — always the owner's local wall-clock
`start_date`/`end_date`/`day_date` are `YYYY-MM-DD`; `start_ts`/`end_ts`/`due` carry a
time as ISO `YYYY-MM-DDTHH:MM` or `HH:MM`. Store the **local** clock the tenant means
(the box is configured to the owner's timezone). The cron planner converts as needed.

### Date parsing (support the tenant's language)
- `today` / `vandaag` → `date('now')` (local — preflight gives the clock)
- `tomorrow` / `morgen` → `date('now','+1 day')`
- explicit dates ("5 July" / "5 juli") → that date, current year unless it implies a
  flip. Confirm the parsed date in the reply when it isn't obvious.

## What goes where — intent → table routing

| The message is about… | Table | Key columns |
|---|---|---|
| starting / naming a trip, its dates, destination | `trips` | one row; `status='planning'` |
| who is travelling (group) | `members` | row per person; map `telegram_user`→member |
| a flight / train / bus / ferry / car / hotel / stay / activity booked or found | `bookings` | row per leg; `monitor=1` on a booked flight/train |
| "what's on day X", scheduling something at a time | `itinerary` | row per scheduled item |
| "I need to pack / bring / sort X", a passport/visa task | `todos` | row per task; `member_id` = who |
| "I paid €X for Y", splitting a cost | `expenses` | row per payment; `split_json` |
| a live transit/route question (no booking yet) | *(none — call the `travel` tool, `transit.md`)* | read-only |

## Upserts & idempotency

There is no `date UNIQUE` per trip (a day has many itinerary rows, a trip has many
bookings), so most writes are plain `INSERT`s. To **edit** an existing row, `UPDATE … WHERE
id = <id>` after reading the id back. To avoid a duplicate member on the group
speaker map, the `UNIQUE(trip_id, telegram_user)` index makes
`INSERT … ON CONFLICT(trip_id, telegram_user) DO UPDATE SET display_name=excluded.display_name`
idempotent. One `sqlite3` statement per call — never chain INSERT+SELECT.

## Adding a new column / migration playbook

1. `ALTER TABLE <t> ADD COLUMN <name> <type>;`
2. Update this schema block and the "Tables at a glance" row.
3. Add an INSERT/UPDATE example to the relevant domain reference.
4. Note the migration date so the origin is traceable.
