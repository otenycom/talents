#!/usr/bin/env python3
"""List new All-In episodes — poll the episode list, diff vs the local DB.

Free HTTP GET + SQLite diff. Reports the YouTube video ids that are NOT yet stored;
the agent then fetches each transcript with the ``youtube_transcript`` tool and stores
it via ``store_transcript.py``. This script never fetches a transcript and never stubs
a row (skill rule 1).

Usage:
  poll_new_episodes.py [--json] [--limit N] [--db PATH] [--episodes-url URL]
"""
from __future__ import annotations

import argparse
import html as html_lib
import json
import os
import re
import sqlite3
import sys
import urllib.error
import urllib.request

DEFAULT_DB = os.path.expanduser("~/.hermes/data/oteny-stock-talent/allin_transcripts.db")
EPISODES_URL = "https://allin.com/episodes"
USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 OtenyStockTalent/1.0")
LINK_RE = re.compile(r'href="https?://(?:www\.)?youtube\.com/v/([A-Za-z0-9_-]{11})"[^>]*>([^<]*)<')


def fetch_episodes_page(url, timeout=30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_episode_links(html: str):
    seen: dict[str, str] = {}
    for vid, title in LINK_RE.findall(html):
        title = html_lib.unescape(title).strip()
        if vid not in seen or (not seen[vid] and title):
            seen[vid] = title
    return list(seen.items())


def existing_video_ids(db_path: str):
    if not os.path.exists(db_path):
        return set()
    conn = sqlite3.connect(db_path)
    try:
        return {r[0] for r in conn.execute("SELECT video_id FROM episodes").fetchall()}
    finally:
        conn.close()


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="List new All-In episodes (poll + diff vs DB)")
    p.add_argument("--db", default=DEFAULT_DB)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--json", action="store_true")
    p.add_argument("--episodes-url", default=EPISODES_URL)
    args = p.parse_args(argv)

    try:
        html = fetch_episodes_page(args.episodes_url)
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"❌ poll: failed to fetch {args.episodes_url}: {e}", file=sys.stderr)
        return 1

    pairs = parse_episode_links(html)
    if not pairs:
        print(f"❌ poll: parsed 0 episode links from {args.episodes_url} — page structure changed.",
              file=sys.stderr)
        return 1

    have = existing_video_ids(args.db)
    new_pairs = [(v, t) for v, t in pairs if v not in have]
    if args.limit > 0:
        new_pairs = new_pairs[: args.limit]
    new = [{"video_id": v, "title": t} for v, t in new_pairs]

    if args.json:
        print(json.dumps({"new": new, "had_new": bool(new)}, ensure_ascii=False, indent=2))
        return 0
    if not new:
        print("no new episodes")
        return 0
    print(f"🔎 {len(new)} new episode(s):")
    for e in new:
        print(f"  • {e['video_id']}  {e['title'] or '(no title)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
