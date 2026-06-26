---
name: all-in-distill
description: "Distill an All-In transcript into a portfolio brief."
version: 1.0.0
author: Oteny
license: MIT
metadata:
  hermes:
    tags: [all-in-podcast, distillation, investment, portfolio, oteny-stock-talent]
    related_skills: [oteny-stock-talent, all-in-transcripts]
---

# all-in-distill

Reads an episode (from `~/.hermes/data/oteny-stock-talent/allin_transcripts.db`, or from a **pasted
transcript file** when the transcriber is stubbed) and emits the full transcript +
metadata so **you** (the orchestrator LLM) write the brief. The script never writes a
brief — a previous design shipped a hardcoded brief identical for every episode; that
is the regression to avoid.

## Commands

```bash
python3 scripts/distill.py --list                       # what's in the DB
python3 scripts/distill.py --last                        # most-recent episode (full transcript)
python3 scripts/distill.py --video <ID>                  # a specific episode
python3 scripts/distill.py --latest 3                     # latest N back-to-back
python3 scripts/distill.py --paste /tmp/transcript.txt    # PASTE MODE (no DB; v1 path)
python3 scripts/distill.py --last --head 4000             # preview / token budget
python3 scripts/distill.py --last --json                  # machine-readable
```

**Paste mode** is the v1 workhorse while `youtube_transcription` is stubbed: the user
pastes a transcript, you save it to a file, run `--paste`, and brief it.

## Brief format (LLM-produced, compact for Telegram)

```
**All-In | YYYY-MM-DD** (E? — <video_id>)
*<full episode title>*

**Core Thesis:** <one tight sentence about what this episode actually argues>

### Key Takeaways
- <claim with attribution + numbers when present>   (3–5 bullets)

### Company Positioning
- **TICKER / Name** — Bullish/Neutral/Bearish | <one-line reason>   (only companies actually discussed)

**Portfolio Watch:** <one actionable sentence>
```

Rules for the brief:
- Tied to *this* transcript's actual content — no template carry-over.
- Don't invent tickers or claims; if the hosts didn't name a company, don't.
- Cite specific numbers from the transcript when present (run rates, valuations,
  Polymarket odds, share-price deltas) — these make the brief useful vs generic.
- Keep it under ~2k chars (comfortable for one Telegram message).
- Distinguish near-term vs long-term calls; tickers where public, "(private)" where not.

The abstract template form is in `references/output-format.md`.

## Common pitfalls

1. **Don't auto-write the brief in the script** — pipe transcript → you.
2. **Don't reuse a prior episode's takeaways** — re-read the current transcript.
3. **Long transcripts** (~80–100k chars) burn tokens; use `--head` for spot-checks,
   feed the full text only when you actually want a real brief.
4. **`published_at`/episode number** come from real metadata; don't fabricate.

## Verification

- `--list` shows real dates + non-trivial byte counts.
- `--last` / `--paste` prints the metadata header + `--- TRANSCRIPT ---` + real text.
- The brief references content actually present (spot-check a quote or company mention).
