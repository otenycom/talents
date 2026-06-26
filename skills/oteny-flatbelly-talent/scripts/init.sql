-- OtenyFlatBellyTalent canonical schema. Idempotent: CREATE ... IF NOT EXISTS.
-- The first-run SKILL.md section runs this inline; this file is the helper copy.
-- Apply: sqlite3 ~/.hermes/data/oteny-flatbelly-talent/food.db < init.sql
CREATE TABLE IF NOT EXISTS meals (
  id INTEGER PRIMARY KEY,
  date TEXT NOT NULL,
  meal_type TEXT NOT NULL CHECK (meal_type IN ('breakfast','lunch','dinner','snack')),
  food TEXT NOT NULL,
  calories INTEGER,
  protein_g REAL,
  carbs_g REAL,
  fat_g REAL,
  notes TEXT,
  leucine_g REAL
);
CREATE INDEX IF NOT EXISTS idx_meals_date ON meals(date);

CREATE TABLE IF NOT EXISTS weight (
  id INTEGER PRIMARY KEY,
  date TEXT NOT NULL UNIQUE,
  weight_kg REAL NOT NULL,
  period TEXT CHECK (period IS NULL OR period IN ('morning','evening')),  -- canonical, language-independent
  notes TEXT
);

CREATE TABLE IF NOT EXISTS daily_metrics (
  id INTEGER PRIMARY KEY,
  date TEXT UNIQUE NOT NULL,
  steps INTEGER,
  first_meal_time TEXT,
  last_meal_time TEXT,
  eating_window_hours REAL,
  sleep_hours REAL,
  bedtime TEXT,
  wake_time TEXT,
  sleep_consistency_score INTEGER,
  alcohol INTEGER DEFAULT 0,
  processed_foods INTEGER DEFAULT 0,
  dark_berries_cups REAL DEFAULT 0,
  notes TEXT,
  active_kcal INTEGER
);
CREATE INDEX IF NOT EXISTS idx_daily_metrics_date ON daily_metrics(date);

CREATE TABLE IF NOT EXISTS workouts (
  id INTEGER PRIMARY KEY,
  date TEXT NOT NULL,
  workout_type TEXT CHECK (workout_type IN ('resistance','hiit','walk')),
  duration_minutes INTEGER,
  muscle_groups TEXT,
  notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_workouts_date ON workouts(date);

CREATE TABLE IF NOT EXISTS waist (
  id INTEGER PRIMARY KEY,
  date TEXT UNIQUE NOT NULL,
  waist_cm REAL,
  height_cm REAL,
  whtr REAL GENERATED ALWAYS AS (waist_cm / height_cm) STORED,
  notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_waist_date ON waist(date);
