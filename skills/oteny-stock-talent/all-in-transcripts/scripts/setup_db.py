#!/usr/bin/env python3
"""Initialize the OtenyStockTalent All-In transcripts SQLite DB. Idempotent.

Namespaced default path: ~/.hermes/data/oteny-stock-talent/allin_transcripts.db (the DB lives OUTSIDE
the skill dir so bots never collide and the skill stays read-only).
"""
import argparse
import sqlite3
import sys
from pathlib import Path

DEFAULT_DB = Path.home() / ".hermes" / "data" / "oteny-stock-talent" / "allin_transcripts.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS episodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    published_at TEXT NOT NULL,
    episode_number INTEGER,
    duration TEXT,
    transcript TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_episodes_published_at ON episodes(published_at);
CREATE INDEX IF NOT EXISTS idx_episodes_episode_number ON episodes(episode_number);
"""


def setup(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA)
        conn.commit()
        existing = conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
    print(f"Database ready at: {db_path}")
    print(f"Existing episode count: {existing}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Initialize OtenyStockTalent transcripts DB")
    ap.add_argument("--db", default=str(DEFAULT_DB))
    args = ap.parse_args()
    try:
        setup(Path(args.db).expanduser())
    except sqlite3.Error as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
