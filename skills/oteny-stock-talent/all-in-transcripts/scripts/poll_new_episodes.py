#!/usr/bin/env python3
"""Poll the All-In episode list, diff vs the DB, and ingest any missing ones.

Free HTTP GET + SQLite diff; ingest delegates to the (stubbed in v1) fetcher in
``fetch_transcript.py``. With the fetcher stubbed, genuinely-new episodes surface in
``failed[]`` with the structured "unavailable" payload — the poller NEVER stubs a row
(skill rule 1).

Usage:
  poll_new_episodes.py [--dry-run] [--json] [--limit N] [--db PATH] [--episodes-url URL]
"""
from __future__ import annotations

import argparse
import html as html_lib
import json
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_transcript import DEFAULT_DB, fetch_transcript, upsert_episode  # noqa: E402

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


def ingest_one(video_id: str, db_path: str, ai_fallback=False) -> dict:
    fetched = fetch_transcript(video_id, ai_fallback=ai_fallback)   # stubbed -> raises
    rows = upsert_episode(db_path, fetched)
    return {"video_id": fetched["video_id"], "title": fetched["title"],
            "published_at": fetched["published_at"],
            "episode_number": fetched["episode_number"],
            "transcript_chars": len(fetched["transcript"]), "rows_changed": rows}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", default=DEFAULT_DB)
    p.add_argument("--dry-run", action="store_true")
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

    if not new_pairs:
        if args.json:
            print(json.dumps({"added": [], "failed": [], "had_new": False}))
        return 0

    if args.dry_run:
        if args.json:
            print(json.dumps({"dry_run": True, "added": [], "failed": [],
                              "candidates": [{"video_id": v, "title": t} for v, t in new_pairs]},
                             ensure_ascii=False, indent=2))
        else:
            print(f"🔎 {len(new_pairs)} new episode(s) (dry-run):")
            for v, t in new_pairs:
                print(f"  • {v}  {t or '(no title)'}")
        return 0

    added, failed = [], []
    for vid, title in new_pairs:
        try:
            added.append(ingest_one(vid, args.db))
        except Exception as e:  # transcriber stubbed -> unavailable payload lands here
            failed.append((vid, title, str(e)))
        time.sleep(0.2)

    if args.json:
        print(json.dumps({"added": added,
                          "failed": [{"video_id": v, "title": t, "error": e} for v, t, e in failed],
                          "had_new": True}, ensure_ascii=False, indent=2))
        return 0

    out = []
    if added:
        out.append(f"📥 ingested {len(added)} new episode(s)")
    if failed:
        out.append(f"⚠️  {len(failed)} fetch(es) failed (transcriber not enabled in this build):")
        for v, t, e in failed:
            out.append(f"• `{v}` {t or '(no title)'}  {e[:200]}")
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
