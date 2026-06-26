#!/usr/bin/env python3
"""Verify the OtenyStockTalent All-In transcripts database (schema, counts, data quality)."""
import argparse
import sqlite3
import sys
from pathlib import Path

DEFAULT_DB = Path.home() / ".hermes" / "data" / "oteny-stock-talent" / "allin_transcripts.db"

EXPECTED_COLS = {"id", "video_id", "title", "published_at", "episode_number",
                 "duration", "transcript", "created_at"}


def verify(db_path: Path) -> int:
    if not db_path.exists():
        print(f"FAIL: database not found at {db_path}")
        return 1
    issues = 0
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(episodes)")}
        if not cols:
            print("FAIL: 'episodes' table missing")
            return 1
        missing = EXPECTED_COLS - cols
        if missing:
            print(f"FAIL: missing columns: {missing}")
            issues += 1
        total = conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
        empty = conn.execute(
            "SELECT COUNT(*) FROM episodes WHERE transcript IS NULL OR length(transcript)=0").fetchone()[0]
        dup = conn.execute(
            "SELECT video_id, COUNT(*) c FROM episodes GROUP BY video_id HAVING c>1").fetchall()
        latest = conn.execute(
            "SELECT video_id, episode_number, published_at, length(transcript) tlen, title "
            "FROM episodes ORDER BY COALESCE(published_at,'') DESC, id DESC LIMIT 5").fetchall()

    print(f"Database:               {db_path}")
    print(f"Total episodes:         {total}")
    print(f"Empty transcripts:      {empty}")
    print(f"Duplicate video_ids:    {len(dup)}")
    print("Latest episodes:")
    for r in latest:
        ep = f"E{r['episode_number']}" if r["episode_number"] else "  -"
        print(f"  {r['published_at'] or '????-??-??'}  {ep:>5}  [{r['video_id']}]  "
              f"{(r['title'] or '')[:60]}  ({r['tlen']:,} chars)")
    if not latest:
        print("  (none)")

    if issues == 0 and empty == 0 and not dup:
        print("OK: verification passed.")
        return 0
    if empty:
        print(f"WARN: {empty} rows have empty transcripts.")
    if dup:
        print(f"FAIL: duplicate video_ids: {[d['video_id'] for d in dup]}")
        issues += 1
    return 1 if issues else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify OtenyStockTalent transcripts DB")
    ap.add_argument("--db", default=str(DEFAULT_DB))
    args = ap.parse_args()
    return verify(Path(args.db).expanduser())


if __name__ == "__main__":
    sys.exit(main())
