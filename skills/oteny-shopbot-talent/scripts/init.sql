-- OtenyShopBotTalent canonical schema. Idempotent: CREATE ... IF NOT EXISTS.
-- The first-run section runs this; this file is the single home of the schema (the .md
-- never inlines DDL). Apply:
--   sqlite3 ~/.hermes/data/oteny-shopbot-talent/shopping.db < init.sql
--
-- Design mirrors the real-world-validated household list: category + store are free text
-- the model reasons (proven the reliable pattern), but kept upgrade-safe (data under
-- ~/.hermes/data) and English (the model localises the display). shop.py owns all writes.

-- The live shared list. status pending|completed|removed (completed/removed drop off the
-- active view). UNIQUE(name,store) so re-adding an item updates its qty + flips it back to
-- pending — no duplicate rows. IDs are lowest-vacant (assigned by shop.py) for stable, low,
-- cognitively-friendly numbers while shopping.
CREATE TABLE IF NOT EXISTS items (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  quantity TEXT DEFAULT '1',
  category TEXT DEFAULT 'Other',          -- a canonical aisle section (see categories)
  store TEXT DEFAULT 'Supermarket',       -- canonical store display name (see store_aliases)
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','completed','removed')),
  added_by TEXT,                          -- recorded, NOT shown in the default list
  bought_by TEXT,
  added_at TEXT NOT NULL DEFAULT (datetime('now')),
  completed_at TEXT,
  UNIQUE(name, store)
);
CREATE INDEX IF NOT EXISTS idx_items_status ON items(status);

-- Resolve a spoken store ("ah", "jumbo") to its canonical display name. The owner's own
-- specialty stores are LEARNED dynamically (shop.py) from structured "... bij <store>" /
-- "<store>: ..." patterns; this seeds the common chains.
CREATE TABLE IF NOT EXISTS store_aliases (
  alias TEXT PRIMARY KEY,                 -- lowercase
  canonical TEXT NOT NULL
);

-- The canonical aisle WALK order: lower sort_order = earlier in the store, so `list` reads
-- top-to-bottom as you walk and you never crisscross. Tenant-agnostic English sections
-- (the model localises the header on display). An item whose category isn't here sorts last.
CREATE TABLE IF NOT EXISTS categories (
  name TEXT PRIMARY KEY,
  sort_order INTEGER NOT NULL DEFAULT 500,
  emoji TEXT
);

INSERT OR IGNORE INTO categories (name, sort_order, emoji) VALUES
  ('Produce', 10, '🥦'), ('Bakery', 20, '🍞'), ('Dairy', 30, '🧀'),
  ('Meat & Fish', 40, '🥩'), ('Deli', 50, '🥓'), ('Pantry', 60, '🥫'),
  ('Frozen', 70, '🧊'), ('Drinks', 80, '🧃'), ('Snacks', 85, '🍫'),
  ('Household', 90, '🧴'), ('Personal care', 95, '🧼'), ('Other', 999, '🛒');

INSERT OR IGNORE INTO store_aliases (alias, canonical) VALUES
  ('ah', 'Albert Heijn'), ('albert heijn', 'Albert Heijn'), ('jumbo', 'Jumbo'),
  ('lidl', 'Lidl'), ('aldi', 'Aldi'), ('dirk', 'Dirk'), ('plus', 'Plus'),
  ('spar', 'Spar'), ('coop', 'Coop'), ('ekoplaza', 'Ekoplaza'), ('marqt', 'Marqt'),
  ('etos', 'Etos'), ('kruidvat', 'Kruidvat'), ('hanos', 'Hanos'), ('makro', 'Makro'),
  ('slager', 'Butcher'), ('butcher', 'Butcher'), ('bakker', 'Bakery'),
  ('market', 'Market'), ('markt', 'Market'), ('costco', 'Costco'),
  ('walmart', 'Walmart'), ('tesco', 'Tesco'), ('whole foods', 'Whole Foods'),
  ('trader joes', 'Trader Joe''s');
