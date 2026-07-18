# `required_artifacts.yaml` — the declared setup goal

The single most important idea in a Talent: a bot's "setup goal" is **declared, not
implied.** `required_artifacts.yaml` lists every artifact that must exist before the bot
can work, each with a **machine-checkable** existence condition. That manifest *is* the
goal; the first-run drill ([`first-run-authoring.md`](first-run-authoring.md)) is the
loop that drives toward
it; `selfcheck` is the deterministic judge. A bundle whose "done" state is vague cannot be
validated and cannot self-heal — so a well-formed manifest is the first thing a grader
checks (rubric checks 1 + 2).

## Artifact classes a manifest may declare

Omit those a bot doesn't need — a chat-only Talent may declare only `profile` + `routing`.

| Class | Checkable condition |
|---|---|
| `data` | db file exists + named tables present |
| `profile` | profile file exists + required fields non-empty |
| `memory` | `~/.hermes/memories/USER.md` rendered from the profile |
| `routing` | this bot's `channel_prompt` (+ optional DM hint) registered |
| `cron` | named jobs registered (with `enabled_when: tool:<x>` if gated) |
| `tools` | required tools present; absent charged tools shipped as stubs |
| `secret` | named env vars present (delivered by the deployer, never baked) |

Each condition must be a **one-line check** (a path, table names, field names) — if you
cannot write one for an artifact, it is underspecified (the check-2 failure). The classes
mirror the namespacing rules (check 6): `data` under `~/.hermes/data/<bot>/`, `routing`
keyed by the bot's group id, `secret` delivered by the deployer and never baked into the
bundle (check 4).
