# Cross-Episode Trend Synthesis

When the user says "trends from the recent All-In", "what should I invest in based on
the pod", or any "across multiple episodes" question, DO NOT brief one episode at a
time. Synthesize across 4–6 recent episodes and surface only themes that recur in ≥2.

## Why a subagent

Each transcript is 60–95k chars. Reading 5–6 in the main context crushes response
quality. **Delegate** the heavy reading to a subagent (`delegate_task`) — the main
agent stays cheap; the subagent scans and returns a tight synthesis.

## Recipe

```python
delegate_task(
    context="""
Database: ~/.hermes/data/oteny-stock-talent/allin_transcripts.db
Table `episodes`, columns: video_id, title, published_at, transcript

NOTE: the column is `transcript`, NOT `transcript_text` — raw SQL needs `transcript`.

Recent business-focused episodes (skip pure political guest spots):
  <list 5-6 video_ids + dates + titles>

Pull with:
  import sqlite3, os
  conn = sqlite3.connect(os.path.expanduser('~/.hermes/data/oteny-stock-talent/allin_transcripts.db'))
  rows = conn.execute('''SELECT video_id, title, published_at, transcript
      FROM episodes WHERE video_id IN (...) ORDER BY published_at DESC''').fetchall()

Prioritize: companies the hosts repeatedly call out (>=2 eps); infra/capex
bottlenecks; sector rotations; specific numbers ($ figures, Polymarket %, growth rates).
""",
    goal="""
Read the 5 most recent business-focused All-In transcripts and produce a cross-episode
trend analysis of INVESTABLE themes.

Output (Telegram-ready, <=3500 chars, no tables):

## All-In Cross-Episode Trends — <month> <year>
*Based on episodes [list dates]*

**Meta-Thesis:** <one tight sentence>

### Trend 1: <Theme> (<N>/<total> eps)
- What's happening: 2-3 bullets with attribution + numbers
- Investable angles:
  - **TICKER / Company** — why it benefits

### Trend 2: ... (4-6 trends total)

### Watchlist Priority (ranked)
1. **TICKER** — one-line thesis, conviction (high/med/low)

**Caveats:** <hosts' own hedges, what could break theses>

Quality bar: cite specific numbers; attribute to hosts where it matters; prefer
picks-and-shovels over narrative; skip political content; specific in findings,
generic in method; DROP any trend not present in >=2 episodes.
""",
    toolsets=["terminal", "file"],   # web/browser NOT needed - data is local
)
```

## Pitfalls

1. **Column is `transcript`, not `transcript_text`.** State it explicitly in the
   subagent context.
2. **Don't give the subagent web/browser toolsets** — data is local; web tempts it to
   "double-check" via search, which adds non-transcript facts and is slow. Verify a
   number in the main agent AFTER synthesis with `live-fact-check-recipes.md`.
3. **Quality-bar enforcement matters.** Without "drop trends not in ≥2 episodes" the
   subagent pads with single-mention noise.
4. **Telegram length cap** ~3500 chars in one message. Tell the subagent the cap.

## Output handling

Drop the synthesis straight into the chat (no rewrite — it already matches the
format), then offer ONE follow-up hook. Don't re-summarize.

## When to skip the subagent

Single-episode questions use the direct flow (`distill.py --video <id>` → main agent
reads + briefs). The subagent is only for cross-episode synthesis that wouldn't fit
the main context comfortably.
