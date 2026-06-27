-- OtenyShopBotTalent canonical schema. Idempotent: CREATE ... IF NOT EXISTS.
-- The first-run section runs this; this file is the single home of the schema (the .md
-- never inlines DDL). Apply:
--   sqlite3 ~/.hermes/data/oteny-shopbot-talent/shopping.db < init.sql

-- Supermarkets the household shops at; exactly one is the default (items file there
-- unless the owner says otherwise).
CREATE TABLE IF NOT EXISTS stores (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  is_default INTEGER NOT NULL DEFAULT 0,
  notes TEXT
);

-- The walk order of a store's sections/aisles: lower sort_order = earlier in the walk,
-- so the rendered list reads top-to-bottom as you move through the store.
CREATE TABLE IF NOT EXISTS sections (
  id INTEGER PRIMARY KEY,
  store_id INTEGER NOT NULL REFERENCES stores(id),
  name TEXT NOT NULL,
  sort_order INTEGER NOT NULL DEFAULT 100,
  UNIQUE(store_id, name)
);
CREATE INDEX IF NOT EXISTS idx_sections_store ON sections(store_id, sort_order);

-- The live shared shopping list. status flips active -> bought when someone picks it up
-- (bought items drop off the active list but stay for the recent-buys view / re-add).
CREATE TABLE IF NOT EXISTS items (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  quantity TEXT,                         -- free text: "2", "500 g", "1 bunch"
  store_id INTEGER REFERENCES stores(id),
  section_id INTEGER REFERENCES sections(id),
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','bought','removed')),
  added_by TEXT,                         -- household member display name (from the group)
  bought_by TEXT,
  added_at TEXT NOT NULL DEFAULT (datetime('now')),
  bought_at TEXT,
  notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_items_status ON items(status);
CREATE INDEX IF NOT EXISTS idx_items_store ON items(store_id);

-- Generic keyword -> canonical aisle section reference (the standout: auto-grouping by
-- section). Tenant-agnostic method data (shared with the food-items reference), NOT PII.
-- Seeded idempotently below; the owner can refine a store's own section order in `sections`.
CREATE TABLE IF NOT EXISTS item_sections (
  id INTEGER PRIMARY KEY,
  item_pattern TEXT NOT NULL UNIQUE,     -- lowercase keyword the item name contains
  section_name TEXT NOT NULL             -- canonical section ("Produce","Dairy",...)
);

-- Common item -> section seed (idempotent; refine per tenant in `sections`).
INSERT OR IGNORE INTO item_sections (item_pattern, section_name) VALUES
  ('banana','Produce'), ('apple','Produce'), ('spinach','Produce'),
  ('lettuce','Produce'), ('tomato','Produce'), ('onion','Produce'),
  ('potato','Produce'), ('carrot','Produce'), ('avocado','Produce'),
  ('bread','Bakery'), ('sourdough','Bakery'), ('bun','Bakery'), ('bagel','Bakery'),
  ('milk','Dairy'), ('yoghurt','Dairy'), ('yogurt','Dairy'), ('butter','Dairy'),
  ('cheese','Dairy'), ('egg','Dairy'), ('cream','Dairy'),
  ('chicken','Meat & Fish'), ('beef','Meat & Fish'), ('mince','Meat & Fish'),
  ('salmon','Meat & Fish'), ('tofu','Meat & Fish'),
  ('rice','Pantry'), ('pasta','Pantry'), ('flour','Pantry'), ('sugar','Pantry'),
  ('oil','Pantry'), ('beans','Pantry'), ('cereal','Pantry'), ('coffee','Pantry'),
  ('tea','Pantry'), ('peanut butter','Pantry'),
  ('peas','Frozen'), ('ice cream','Frozen'), ('pizza','Frozen'),
  ('water','Drinks'), ('juice','Drinks'), ('soda','Drinks'), ('beer','Drinks'),
  ('wine','Drinks'),
  ('dish soap','Household'), ('detergent','Household'), ('toilet paper','Household'),
  ('kitchen roll','Household'), ('foil','Household'),
  ('shampoo','Personal care'), ('toothpaste','Personal care'), ('soap','Personal care');
