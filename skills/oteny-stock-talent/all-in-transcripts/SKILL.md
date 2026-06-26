---
name: all-in-transcripts
description: "Ingest + store All-In podcast transcripts (SQLite)."
version: 1.1.0
author: Oteny
license: MIT
metadata:
  hermes:
    tags: [youtube, transcripts, all-in-podcast, sqlite, research, oteny-stock-talent]
    related_skills: [oteny-stock-talent, all-in-distill, oteny-youtube-transcript]
---

# all-in-transcripts (OtenyStockTalent ingest)

Stores All-In Podcast transcripts in a per-tenant SQLite DB at
`~/.hermes/data/oteny-stock-talent/allin_transcripts.db`, so each episode is fetched
once and reused for briefs and cross-episode trends. The transcription itself uses the
always-available **`youtube_transcript`** tool (the `oteny-youtube-transcript` skill);
this skill owns the episode list, the diff, and the store.

> No API token lives in this skill — the `youtube_transcript` tool does the fetch.

## Database schema

The **executable** schema is `scripts/setup_db.py` (idempotent — run it at first-run,
below). One table, `episodes`: `id` PK · `video_id` TEXT UNIQUE · `title` TEXT ·
`published_at` TEXT (real upload metadata, never guessed) · `episode_number` INT ·
`duration` TEXT · `transcript` TEXT · `created_at` TIMESTAMP. Never hand-write the DDL
— `setup_db.py` owns it.

## How transcription works

1. **List what's new** — `poll_new_episodes.py` polls the episode list and diffs it
   against the DB (a free GET). It returns the YouTube ids not yet stored.
2. **Fetch each new transcript with the `youtube_transcript` tool** on the episode's
   YouTube URL. It is a **paid scraper** (a few cents per video); if *you* chose to
   fetch unasked, confirm the small cost with the owner first.
3. **Store it** — `store_transcript.py` upserts on `video_id`, so re-storing the same
   episode never double-charges.
4. **Brief it** — hand the stored transcript to [`all-in-distill`](../all-in-distill/SKILL.md).

A user who already has a transcript can **paste** it → `all-in-distill --paste` with no
fetch at all.

## Commands

```bash
# Setup (idempotent)
python3 scripts/setup_db.py --db ~/.hermes/data/oteny-stock-talent/allin_transcripts.db

# List new episodes (free GET + diff)
python3 scripts/poll_new_episodes.py --json --db ~/.hermes/data/oteny-stock-talent/allin_transcripts.db

# Store a transcript you fetched with the youtube_transcript tool
python3 scripts/store_transcript.py --video-id <id> --title "<title>" --transcript-file /tmp/transcript.txt

# Verify
python3 scripts/verify_db.py --db ~/.hermes/data/oteny-stock-talent/allin_transcripts.db
```

## Operating rules (user-enforced)

1. **Never insert placeholder rows.** A failed fetch is surfaced, not stored with a
   guessed date / fake transcript.
2. **Report errors verbatim.** Print the actual exception/payload before asking how to
   proceed — no silent fallbacks.
3. **Don't guess dates.** `published_at` comes from real upload metadata; if missing,
   leave NULL and say so.
4. **Don't fake distillation.** This skill stores transcripts; the brief comes from
   the orchestrator LLM reading the actual transcript (see `all-in-distill`).

## Common pitfalls

- The `youtube_transcript` tool is a paid scraper — confirm the cost before a bulk
  backfill, and let `store_transcript.py`'s `video_id` upsert dedupe so an episode
  already stored is never re-charged.
- Always run `verify_db.py` after storing to confirm row count + dates look sane.
