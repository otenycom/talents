#!/usr/bin/env python3
"""all-in-distill: load transcript content for LLM-based distillation.

Does NOT generate a brief — distillation is the orchestrator LLM's job; this is the
loader. Reads from the OtenyStockTalent transcripts DB, OR from a pasted transcript file
(``--paste``) so the bot works even while the transcriber is stubbed.

Usage:
    distill.py --list
    distill.py --last
    distill.py --video <ID>
    distill.py --latest N
    distill.py --paste <file> [--title "..."] [--date YYYY-MM-DD]   # paste-mode
    distill.py --last --head 5000
    distill.py --last --json
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

DB_PATH = os.path.expanduser("~/.hermes/data/oteny-stock-talent/allin_transcripts.db")
KEYS = ("video_id", "title", "published_at", "episode_number", "duration", "transcript")


def fetch_one(video_id: str, db=DB_PATH):
    conn = sqlite3.connect(db)
    try:
        row = conn.execute(
            "SELECT video_id, title, published_at, episode_number, duration, transcript "
            "FROM episodes WHERE video_id=?", (video_id,)).fetchone()
    finally:
        conn.close()
    return dict(zip(KEYS, row)) if row else None


def fetch_latest(limit: int, db=DB_PATH):
    conn = sqlite3.connect(db)
    try:
        rows = conn.execute(
            "SELECT video_id, title, published_at, episode_number, duration, transcript "
            "FROM episodes ORDER BY published_at DESC, id DESC LIMIT ?", (limit,)).fetchall()
    finally:
        conn.close()
    return [dict(zip(KEYS, r)) for r in rows]


def list_episodes(db=DB_PATH) -> int:
    conn = sqlite3.connect(db)
    try:
        rows = conn.execute(
            "SELECT video_id, title, published_at, LENGTH(transcript) "
            "FROM episodes ORDER BY published_at DESC, id DESC").fetchall()
    finally:
        conn.close()
    if not rows:
        print("(no episodes in database)")
        return 0
    print(f"📚 {len(rows)} episode(s) in {db}\n")
    for vid, title, date, tlen in rows:
        short = (title or "")[:65] + ("…" if title and len(title) > 65 else "")
        print(f"  {date or '   ?    '}  {vid}  {tlen:>7,} chars  {short}")
    return 0


def dump_episode(ep, *, head=None, as_json=False):
    transcript = ep["transcript"] or ""
    if head and head > 0 and len(transcript) > head:
        transcript = transcript[:head] + f"\n…[truncated, {len(ep['transcript'])-head} chars omitted]"
    if as_json:
        out = dict(ep)
        out["transcript"] = transcript
        out["transcript_chars_total"] = len(ep["transcript"] or "")
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return
    print("--- EPISODE START ---")
    for k in ("video_id", "title", "published_at", "episode_number", "duration"):
        print(f"{k}: {ep.get(k)}")
    print(f"transcript_chars: {len(ep['transcript'] or '')}")
    print("--- TRANSCRIPT ---")
    print(transcript)
    print("--- EPISODE END ---")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="all-in-distill transcript loader")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--list", action="store_true")
    g.add_argument("--last", action="store_true")
    g.add_argument("--video")
    g.add_argument("--latest", type=int, metavar="N")
    g.add_argument("--paste", metavar="FILE", help="distill a pasted transcript file (no DB)")
    p.add_argument("--title", default="(pasted transcript)")
    p.add_argument("--date", default=None)
    p.add_argument("--db", default=DB_PATH)
    p.add_argument("--head", type=int, default=None)
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    if args.paste:
        try:
            text = open(os.path.expanduser(args.paste)).read()
        except OSError as e:
            print(f"❌ cannot read paste file: {e}", file=sys.stderr)
            return 2
        ep = {"video_id": "pasted", "title": args.title, "published_at": args.date,
              "episode_number": None, "duration": None, "transcript": text}
        dump_episode(ep, head=args.head, as_json=args.json)
        return 0

    if args.list:
        return list_episodes(args.db)
    if args.video:
        ep = fetch_one(args.video, args.db)
        if not ep:
            print(f"❌ video_id not found: {args.video}", file=sys.stderr)
            return 2
        dump_episode(ep, head=args.head, as_json=args.json)
        return 0
    if args.last:
        eps = fetch_latest(1, args.db)
        if not eps:
            print("(no episodes)", file=sys.stderr)
            return 1
        dump_episode(eps[0], head=args.head, as_json=args.json)
        return 0
    if args.latest is not None:
        eps = fetch_latest(args.latest, args.db)
        if not eps:
            print("(no episodes)", file=sys.stderr)
            return 1
        for i, ep in enumerate(eps):
            if i:
                print()
            dump_episode(ep, head=args.head, as_json=args.json)
        return 0
    p.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
