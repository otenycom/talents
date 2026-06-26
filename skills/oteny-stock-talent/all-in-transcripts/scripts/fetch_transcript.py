#!/usr/bin/env python3
"""STUB transcriber for OtenyStockTalent v1.

The real YouTube transcription is a charged tool (D30, off-VM brokered key). This stub
keeps the interface so the poller and pipeline are unchanged, but does **no external
call and writes nothing** — no token, no network. It cleanly reports "unavailable" so
the persona degrades to paste-mode + live-tape Q&A (see the umbrella SKILL.md).

Exports (imported by poll_new_episodes.py):
    DEFAULT_DB
    UNAVAILABLE                       # the structured payload
    TranscriberUnavailable            # raised by fetch_transcript()
    fetch_transcript(url, ...)        # raises TranscriberUnavailable
    upsert_episode(db_path, fetched)  # real DB upsert (used once the tool is enabled)

CLI:
    fetch_transcript.py --url <id>    # prints the unavailable payload, exits 0
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

DEFAULT_DB = os.path.expanduser("~/.hermes/data/oteny-stock-talent/allin_transcripts.db")

UNAVAILABLE = {
    "status": "unavailable",
    "reason": "youtube-transcription tool not configured in this build",
    "how_to_enable": "D30 charged tool (brokered key, metered into credits)",
    "degrade_to": ["paste a transcript -> all-in-distill", "live-tape ticker Q&A"],
}


class TranscriberUnavailable(RuntimeError):
    """Raised in place of a real fetch so callers surface it (never stub a row)."""

    def __init__(self):
        super().__init__(json.dumps(UNAVAILABLE))


def fetch_transcript(url_or_id: str, *_, **__) -> dict:
    """STUB: never returns a transcript. Raises so the poller lists it as failed."""
    raise TranscriberUnavailable()


def upsert_episode(db_path: str, fetched: dict) -> int:
    """Real upsert kept for when the tool is enabled. Unused while stubbed."""
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
    p = argparse.ArgumentParser(description="STUB transcriber (v1) — reports unavailable")
    p.add_argument("--url", required=True)
    p.add_argument("--db", default=DEFAULT_DB)
    p.parse_args(argv)
    print(json.dumps(UNAVAILABLE, indent=2))
    return 0  # not an error — the tool is intentionally absent in this build


if __name__ == "__main__":
    sys.exit(main())
