# Clone neutralize — how a flatbelly clone is made safe

> Audience: the control plane (runs this deterministically at clone time) and any operator
> or author reviewing what a clone of this Talent's real state is and is not allowed to do.

A **clone** is a real prod tenant rebuilt from another tenant's captured `food.db` +
profile + cron jobs, so an author can test a new version of this Talent against true data.
Before the clone serves a single turn it is **neutralized**: every outbound action is
disabled. The declared steps live in [`../../neutralize.yaml`](../../neutralize.yaml); the
control plane runs `neutralize.py --all` (gateway not serving), and `check_neutralize.py`
refuses the gateway start unless every step is recorded applied
(`~/.hermes/data/oteny-flatbelly-talent/neutralize.json`).

## What gets de-fanged

| Vector | Risk on a clone | Neutralize step |
| --- | --- | --- |
| Scheduled cron jobs | The daily morning/evening log + weekly dashboard DM the **real owner** on the source's chat origin. | `0001_disable_outbound_crons` (`kind: crons`) sets every named job `enabled=false` in `~/.hermes/cron/jobs.json`. |
| Owner PII in `profile.yaml` | Name / body metrics belong to the source owner. | Scrubbed by the control-plane **redaction floor** at capture time — not a neutralize step (it runs before rebuild). |
| External `/json/2/` seam | flatbelly has **none** (in-house, owns its own `food.db`). | — |

## Why crons, not the agent

`neutralize.py` runs control-plane-side while the gateway is **not** serving, so it cannot
ask the agent to re-plan jobs. The `kind: crons` step is a deterministic file rewrite of
`jobs.json` (detect-then-act: a missing file or already-absent job is a no-op), which is
why a clone can be proven safe before it ever boots.

## Boot canary (defense in depth)

Even with the marker complete, an externally-cloned bot is independently re-checked at
boot (`ODOO_URL` points at staging, outbound crons disabled, the clone's bot token ≠ the
source's). Any failure is CRITICAL and the clone refuses to serve — the marker is trusted,
but not *only* the marker.
