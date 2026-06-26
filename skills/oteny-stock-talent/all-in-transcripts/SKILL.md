---
name: all-in-transcripts
description: "Ingest + store All-In podcast transcripts (SQLite)."
version: 1.0.0
author: Oteny
license: MIT
metadata:
  hermes:
    tags: [youtube, transcripts, all-in-podcast, sqlite, research, oteny-stock-talent]
    related_skills: [oteny-stock-talent, all-in-distill]
---

# all-in-transcripts (OtenyStockTalent ingest)

Downloads All-In Podcast transcripts and stores them in a per-tenant SQLite DB at
`~/.hermes/data/oteny-stock-talent/allin_transcripts.db`. The **transcriber (`fetch_transcript.py`) is
a stub in v1** — a declared-but-absent charged tool (`youtube_transcription`, D30).
The DB schema, the poller, and the verifier are fully functional; the distiller works
on a **pasted** transcript without the fetcher.

> No API token lives in this skill. The real transcriber is brokered off-VM when D30
> lands; only the stub file + the watcher's cron-gate flip change.

## Database schema

The **executable** schema is `scripts/setup_db.py` (idempotent — run it at first-run,
below). One table, `episodes`: `id` PK · `video_id` TEXT UNIQUE · `title` TEXT ·
`published_at` TEXT (real upload metadata, never guessed) · `episode_number` INT ·
`duration` TEXT · `transcript` TEXT · `created_at` TIMESTAMP. Never hand-write the DDL
— `setup_db.py` owns it.

## Commands

```bash
# Setup (idempotent)
python3 scripts/setup_db.py --db ~/.hermes/data/oteny-stock-talent/allin_transcripts.db

# Transcriber probe (STUB — prints a structured "unavailable" payload, writes nothing)
python3 scripts/fetch_transcript.py --url <id>

# Poll the episode list + diff vs DB (free GET; ingest only runs the transcriber for
# new ids — which is stubbed, so new ids surface as 'failed' with the unavailable msg)
python3 scripts/poll_new_episodes.py --json --db ~/.hermes/data/oteny-stock-talent/allin_transcripts.db

# Verify
python3 scripts/verify_db.py --db ~/.hermes/data/oteny-stock-talent/allin_transcripts.db
```

## Operating rules (user-enforced)

1. **Never insert placeholder rows.** A failed fetch is surfaced, not stubbed with a
   guessed date / fake transcript.
2. **Report errors verbatim.** Print the actual exception/payload before asking how to
   proceed — no silent fallbacks.
3. **Don't guess dates.** `published_at` comes from real upload metadata; if missing,
   leave NULL and say so.
4. **Don't fake distillation.** This skill stores transcripts; the brief comes from
   the orchestrator LLM reading the actual transcript (see `all-in-distill`).

## v1 behaviour (transcriber stubbed)

- `fetch_transcript.py` returns `{"status":"unavailable","reason":"youtube-
  transcription tool not configured in this build","how_to_enable":"D30 charged
  tool"}` and writes nothing — no token, no network.
- `poll_new_episodes.py` still diffs the live episode list against the DB for free;
  any genuinely new episode is reported in `failed[]` with the unavailable payload
  (the poller never stubs a row).
- The auto-watcher cron is **not registered** while the tool is absent
  (`enabled_when: tool:youtube_transcription`). See `../references/cron-architecture.md`.
- **What still works without the transcriber:** paste a transcript →
  [`all-in-distill`](../all-in-distill/SKILL.md) `distill.py --paste <file>` → brief;
  and live-tape ticker Q&A via `../scripts/live_tape.py`.

## Common pitfalls

- Installing a real transcriber client is a D30 concern; do not try to wire one now.
- Always run `verify_db.py` after any real fetch (once enabled) to confirm row count +
  dates look sane.
