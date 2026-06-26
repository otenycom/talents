# OtenyStockTalent Cron Architecture (the All-In auto-brief watcher)

How the per-episode auto-brief watcher is wired, and why. It is **opt-in** — not
registered at first-run, because it incurs recurring paid transcriber spend (a few cents
per new episode); register it when the owner asks to auto-follow new episodes. The
transcript tool (`youtube_transcript`) is always available. This doc is the design and
the source of several hard-won delivery rules.

## Job at a glance

- **Name:** `OtenyStockTalent All-In watcher`
- **enabled_when:** owner opts in (recurring per-episode transcriber spend → off by default)
- **Schedule:** periodic (polls are free; the transcriber only costs per brand-new
  `video_id`).
- **Type:** LLM cron. The brief is written by the orchestrator LLM reading the actual
  transcript — never a script template.
- **Skills loaded:** `oteny-stock-talent`, `all-in-transcripts`, `all-in-distill`.
- **Tooling:** `terminal` (run scripts) + `send_message` (per-episode delivery).

## Pipeline

```
poll_new_episodes.py --json                       (free HTTP GET + SQLite diff)
   had_new == false  → final response: [SILENT]
   had_new == true   → for each entry in `new` (oldest first):
       youtube_transcript tool on the episode URL (paid — fetch the transcript)
       store_transcript.py --video-id <id> ...    (persist it)
       distill.py --video <id>                    (dump transcript)
       LLM writes the compact brief
       send_message(target="telegram:<GROUP_ID>", message=<brief>)   # one per episode
   final response: [SILENT]                        (suppress auto-delivery double-post)
```

`<GROUP_ID>` is **looked up at run time from `~/.hermes/channel_directory.json`** —
never hardcoded. Telegram group ids are **negative**; a positive 9-digit id in a
"deliver to group" cron is the bug.

## Why send_message instead of the framework's auto-delivery

The cron runtime appends "do NOT use send_message — your final response will be
auto-delivered." For this job that's **explicitly overridden**, because:

1. **One brief per Telegram message is a hard product requirement.**
2. **Telegram's 4096-char cap auto-splits batched messages at arbitrary cut points**
   and destroys brief formatting.

After all per-episode `send_message` calls, the final response must be exactly
`[SILENT]` so auto-delivery doesn't repeat them.

## Cost model

HTTP GET to the episode list: free. HTML parse / SQLite diff: free. Transcriber run:
**paid, fixed per new episode, regardless of polling frequency.** Polling frequency
is purely "how soon the brief lands," never a cost argument.

## Testing without re-spending the transcriber

The DB upserts on `video_id` (re-fetching re-runs the paid tool). To test cheaply: the
poller only lists candidates (no paid call), so run it alone to see what's new; or delete
one row to force a single "new" episode, then `cronjob action=run`. Verify exactly one
brief arrives as its own message and the final response was `[SILENT]`.

## Failure modes

| Failure | Behavior |
|---|---|
| Episode list unreachable | Poller exits non-zero; LLM surfaces it in the final response |
| Transcript fetch fails for one video | The tool error is surfaced; that episode is skipped; the others still process |
| No transcript available | The tool reports it; surface that, never fabricate a transcript |
| `send_message` tool error | LLM includes the error (overrides `[SILENT]`) so the user sees it |
| `send_message` not in toolset | LLM falls back to auto-delivery — fine for 1 brief, mangled for ≥2. Verify the job's allowlist includes `send_message` (or no allowlist). |
| **Wrong-target delivery (briefs in DM not group)** | Root cause is always a hardcoded/incorrect target string. **Always resolve the id from `channel_directory.json`.** `last_status: ok` means nothing for delivery correctness — only the session log + directory cross-check catches it. |
| LLM routes via `hermes send` CLI instead of the tool | Same wrong-target symptom; the toolset diagnostic doesn't apply. The target string must be correct regardless of delivery path. |

## Channel-ID lookup

```bash
cat ~/.hermes/channel_directory.json
# platforms.telegram[] entries: id, name, type (dm/group), thread_id.
# Group ids are NEGATIVE. Resolve the OtenyStockTalent group by name/type — never copy an
# id from memory or a previous prompt.
```

When a brief lands wrong: (1) read the last cron session for the actual `target=`/
`--to` used (check BOTH `send_message` calls and `hermes send` in `terminal` calls);
(2) compare to `channel_directory.json`; (3) patch the prompt with the correct id;
(4) backfill missed messages; (5) verify with `cronjob action=run`.

## File map

- Poller (lists new ids): `all-in-transcripts/scripts/poll_new_episodes.py`
- Fetch: the `youtube_transcript` tool (the `oteny-youtube-transcript` skill)
- Store: `all-in-transcripts/scripts/store_transcript.py`
- Loader: `all-in-distill/scripts/distill.py`
- DB: `~/.hermes/data/oteny-stock-talent/allin_transcripts.db`
