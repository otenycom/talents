# OtenyStockTalent — First-run setup & self-check

**You are here only because the guard printed `NOT-READY`.** Mechanical and idempotent
(declared scripts only — never improvise `python3 -c` or a heredoc; the approval gate
flags those and the bot stalls). The setup GOAL is `../required_artifacts.yaml`;
`selfcheck.py` is the judge.

## Guard (always run first)

```bash
python3 ~/.hermes/skills/talents/oteny-stock-talent/scripts/selfcheck.py
```

- `READY` → skip the rest and brief.
- `NOT-READY: missing=[…]` → run the remediation for each listed artifact, then re-check.

## Remediation: `data` (transcripts DB)

The shipped, idempotent `setup_db.py` owns the schema (columns are documented in
[`all-in-transcripts`](../all-in-transcripts/SKILL.md)):

```bash
python3 ~/.hermes/skills/talents/oteny-stock-talent/all-in-transcripts/scripts/setup_db.py --db ~/.hermes/data/oteny-stock-talent/allin_transcripts.db
```

## Remediation: `profile` (light intake)

Ask (in the tenant's language) and write `~/.hermes/data/oteny-stock-talent/profile.yaml`
(template: `../profile/profile.yaml.template`):
1. Which **tickers** are on your watchlist?
2. Your **risk tolerance** (conservative / balanced / aggressive)?
3. (optional, group bots) the **authorized members** + the addressing convention.
4. Reply **language** (default English) and **timezone**.

Then render this bot's DOMAIN memory (D34): fill `../profile/memory.md.template`'s
`{{placeholders}}` from `profile.yaml` and write it to
`~/.hermes/data/oteny-stock-talent/memory.md` (`mkdir -p` its dir first). If
`~/.hermes/memories/USER.md` does not exist yet, also render a small shared identity file
there (name / timezone / language). The persona reads memory.md at the start of each
session — honor it, and append a short line when you learn a lasting preference.

## Remediation: `tools` (probe the transcriber; verify live-tape)

```bash
python3 ~/.hermes/skills/talents/oteny-stock-talent/all-in-transcripts/scripts/fetch_transcript.py --url dummy
```
```bash
python3 ~/.hermes/skills/talents/oteny-stock-talent/scripts/live_tape.py NVDA
```

The transcriber probe should report `unavailable` (it ships as a stub in v1, D30);
live-tape (free Yahoo) should print a quote. Set the persona to **paste/live-tape
mode** (see the umbrella skill's "transcriber is a stub" note).

## Remediation: `routing` (register the channel prompt)

```bash
python3 ~/.hermes/skills/talents/index-reconciler/scripts/index_reconciler.py --apply
```

## Remediation: `localized_bundle`

If `profile.language` ≠ the base language, translate with
[`skill-translator`](../../skill-translator/SKILL.md), then
`echo "<lang>" > ~/.hermes/data/oteny-stock-talent/.bundle_lang`.

## `cron` (auto-watcher) — gated OFF in v1

The All-In poll→ingest→brief watcher is **not registered** while
`youtube_transcription` is a stub (it can't complete ingest). It is declared
`enabled_when: tool:youtube_transcription` and turns on when the real charged tool lands
(D30). Do not register it now.

## Re-check

Run the guard again; when `READY`, brief — grounded in live prices.
