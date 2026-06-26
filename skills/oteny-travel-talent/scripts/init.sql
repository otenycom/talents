-- OtenyTravelTalent canonical schema. Idempotent: CREATE ... IF NOT EXISTS.
-- The single EXECUTABLE copy of the schema; references/datamodel.md documents the
-- columns in prose. Apply at first-run (declared, approval-clean):
--   sqlite3 ~/.hermes/data/oteny-travel-talent/trips.db < init.sql
-- Six tables: trips · members · bookings · itinerary · todos · expenses.
-- Enums are canonical + language-independent (the triage classifies from the
-- tenant's words in any language, then stores the English token) so a non-English
-- tenant's data routes correctly.

-- One row per trip. group_chat_id is NULL for a DM/solo trip; set only when the
-- human binds the bot to a Telegram trip group (a bot cannot create a group itself).
CREATE TABLE IF NOT EXISTS trips (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  destination TEXT,
  start_date TEXT,                 -- YYYY-MM-DD (local)
  end_date TEXT,                   -- YYYY-MM-DD (local)
  type TEXT,                       -- canonical: beach/city/ski/road-trip/family/business/other
  home_city TEXT,                  -- origin for door-to-door routing; defaults from profile.home_city
  status TEXT NOT NULL DEFAULT 'planning'
    CHECK (status IN ('planning','active','past','cancelled')),
  group_chat_id TEXT,              -- nullable; resolved at runtime, never baked
  created_ts TEXT DEFAULT (datetime('now')),
  notes TEXT
);

-- The travel party. Only populated for a group trip (speaker -> member map); a solo
-- DM trip needs no members. telegram_user is NULL for a member added by name only.
CREATE TABLE IF NOT EXISTS members (
  id INTEGER PRIMARY KEY,
  trip_id INTEGER NOT NULL,
  telegram_user TEXT,              -- canonical Telegram id/username; NULL if added by name only
  display_name TEXT NOT NULL,
  role TEXT DEFAULT 'member' CHECK (role IN ('lead','member','child')),
  home_city TEXT,
  notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_members_trip ON members(trip_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_members_trip_user
  ON members(trip_id, telegram_user) WHERE telegram_user IS NOT NULL;

-- Transport legs + lodging + activities (the draft's legs+stays unified). monitor=1
-- flags a leg the disruption cron watches; status holds the last-known live status.
CREATE TABLE IF NOT EXISTS bookings (
  id INTEGER PRIMARY KEY,
  trip_id INTEGER NOT NULL,
  kind TEXT NOT NULL
    CHECK (kind IN ('flight','train','bus','car','ferry','hotel','airbnb','resort','activity')),
  title TEXT,
  from_loc TEXT,
  to_loc TEXT,
  start_ts TEXT,                   -- ISO local: departure / check-in / activity start
  end_ts TEXT,                     -- ISO local: arrival / check-out / activity end
  carrier TEXT,                    -- airline / rail operator / hotel chain
  booking_ref TEXT,                -- PNR / confirmation; the leg's natural number too (e.g. flight no.)
  status TEXT,                     -- last-known live status (on-time/delayed Nm/cancelled/gate X/...)
  monitor INTEGER NOT NULL DEFAULT 0,   -- 1 = watched by the disruption cron
  deeplink TEXT,                   -- the link we surface (we link out, never book/pay)
  cost REAL,
  currency TEXT,
  notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_bookings_trip ON bookings(trip_id);
CREATE INDEX IF NOT EXISTS idx_bookings_monitor ON bookings(trip_id, monitor);

-- Day-by-day schedule. category groups the entry (transit/meal/activity/lodging/admin).
CREATE TABLE IF NOT EXISTS itinerary (
  id INTEGER PRIMARY KEY,
  trip_id INTEGER NOT NULL,
  day_date TEXT NOT NULL,          -- YYYY-MM-DD (local)
  time TEXT,                       -- HH:MM (local), NULL = unscheduled / all-day
  title TEXT NOT NULL,
  place TEXT,
  category TEXT
    CHECK (category IS NULL OR category IN ('transit','meal','activity','lodging','admin')),
  notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_itinerary_trip_day ON itinerary(trip_id, day_date);

-- Per-member prep todos (claimable in a group). member_id NULL = whole-party todo.
CREATE TABLE IF NOT EXISTS todos (
  id INTEGER PRIMARY KEY,
  trip_id INTEGER NOT NULL,
  member_id INTEGER,               -- NULL = applies to the whole party / unassigned
  title TEXT NOT NULL,
  category TEXT
    CHECK (category IS NULL OR category IN ('packing','document','booking','health','admin')),
  due TEXT,                        -- YYYY-MM-DD (local), NULL = no hard date
  done INTEGER NOT NULL DEFAULT 0,
  notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_todos_trip_member ON todos(trip_id, member_id);

-- Shared-expense ledger. split_json encodes the split: the string 'even' (split
-- across every member) OR a JSON object {member_id: share} of weights/amounts.
CREATE TABLE IF NOT EXISTS expenses (
  id INTEGER PRIMARY KEY,
  trip_id INTEGER NOT NULL,
  payer_member_id INTEGER,         -- who paid (members.id); NULL = the owner
  amount REAL NOT NULL,
  currency TEXT,                   -- defaults from profile.default_currency / trip
  category TEXT,                   -- food/transport/lodging/activity/other (free-ish)
  split_json TEXT DEFAULT 'even',  -- 'even' or {"<member_id>": <share>, ...}
  note TEXT,
  ts TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_expenses_trip ON expenses(trip_id);
