#!/usr/bin/env python3
"""Store an All-In episode transcript in the per-tenant SQLite DB.

The transcript text is fetched by the agent with the always-available
``youtube_transcript`` tool (the ``oteny-youtube-transcript`` skill); this script just
**persists** what the tool returned, so an episode is fetched (and paid for) once and
reused for briefs and cross-episode trends. No network and no token here — the tool
does the fetch.

Exports (imported by poll_new_episodes.py): ``DEFAULT_DB``, ``upsert_episode``.

CLI:
    store_transcript.py --video-id <id> --title "<t>" [--published-at <iso>] \
        [--episode-number N] [--duration <d>] [--transcript-file PATH] [--db PATH]
    (the transcript is read from --transcript-file, or from stdin when it is omitted)
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

DEFAULT_DB = os.path.expanduser("~/.hermes/data/oteny-stock-talent/allin_transcripts.db")


def upsert_episode(db_path: str, fetched: dict) -> int:
    """Idempotent upsert keyed on video_id — re-storing an episode never double-charges."""
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute(
            """INSERT INTO episodes (video_id, title, published_at, episode_number, duration, transcript)
               VALUES (:video_id, :title, :published_at, :episode_number, :duration, :transcript)
               ON CONFLICT(video_id) DO UPDATE SET
                 title=excluded.title, published_at=excluded.published_at,
                 episode_number=excluded.episode_number, duration=excluded.duration,
                 transcript=excluded.transcript""",
            fetched,
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Store a fetched All-In transcript in the DB")
    p.add_argument("--video-id", required=True)
    p.add_argument("--title", default="")
    p.add_argument("--published-at", default=None)
    p.add_argument("--episode-number", type=int, default=None)
    p.add_argument("--duration", default=None)
    p.add_argument("--transcript-file", default=None,
                   help="file holding the transcript text (omit to read stdin)")
    p.add_argument("--db", default=DEFAULT_DB)
    args = p.parse_args(argv)

    if args.transcript_file:
        transcript = Path(args.transcript_file).read_text(encoding="utf-8")
    else:
        transcript = sys.stdin.read()
    if not transcript.strip():
        print("refusing to store an empty transcript "
              "(fetch it with the youtube_transcript tool first)", file=sys.stderr)
        return 1

    rows = upsert_episode(args.db, {
        "video_id": args.video_id, "title": args.title,
        "published_at": args.published_at, "episode_number": args.episode_number,
        "duration": args.duration, "transcript": transcript,
    })
    print(f"stored {len(transcript)} chars for {args.video_id} ({rows} row changed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
