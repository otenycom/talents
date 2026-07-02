# The scoped-business-bot pattern (authoring deltas)

Most of the catalog is a **B2C personal bot** on Telegram (Flatbelly, Stocks, Travel,
Shopbot). A second class is emerging: the **scoped business bot** — a single-job bot for
an internal team that lives in the team's own chat and reaches the **business's Odoo** as
its data plane. Barney is the first business-bot instance; this doc is the generic
authoring delta on top of the standard. Four things change vs a B2C bot — author them in
order, then grade them with the checklist below.

A business bot still passes **every** rubric check in [`../SKILL.md`](../SKILL.md). The
deltas here refine four of them: routing (check 5), toolset (checks 1 + 9), the data plane
(checks 2 + 6), and testing (check 14).

## 1. Channel routing — Discuss, not Telegram (check 5)

A B2C bot routes to a Telegram channel the owner DMs. A business bot routes to an Odoo
**`discuss.channel`** — the chat built into the business's Odoo, where the team already
works all day. In `agent-profile.yaml`:

```yaml
routing:
  channel: discuss                 # not "telegram"
  channel_prompt: |
    You are <bot>, the team's <job> desk in this Odoo Discuss channel. Load the
    <bot> skill and follow its triage and hard rules. Never ask for a password or a
    one-time code in chat. Reply in the operator's language; keep replies chat-short.
  signature: "<bot>"
```

- The team posts to a dedicated channel (e.g. "<Team> and <bot>"); the bot replies there.
- **No public inbound, no separate app** — the chat is inside the business's Odoo.
- The `channel_prompt` is the standing instruction injected every turn — same discipline
  as a B2C bot (who it is, which skill to load first, the hard rules), tuned for a team
  channel rather than a 1:1 DM. The platform renders it into the box keyed by the bot's
  home channel on **every delivery** — delivery = activation, so pushing a Talent change
  changes who the bot *is* with no extra step.
- Add **`preload_skills:`** (top-level, beside `skills:`) naming the persona/umbrella
  skill + the main working skill: the platform injects their full text at the top of
  every fresh session — including each dispatched isolated run — so the job starts with
  its procedure in the cached prefix instead of spending calls on `skill_view`.

## 2. Minimal locked toolset (checks 1 + 9)

A B2C assistant requests the wide set (`[terminal, execute_code, cron, send_message]`) —
breadth *is* the product. A business bot requests **only the tools its one job needs**, and
the generic toolsets are **OFF**:

- **OFF for a scoped bot:** `terminal`, `execute_code`, `skills`, filesystem, and the
  open-web search tools. None of these mount unless the job genuinely needs them.
- **ON, named explicitly:** the `/json/2/` Odoo client (the data plane, §3); optionally the
  secure browser (`browser` + `browser_request_human` + `browser_download`) for portal
  filing; optionally a mailbox reader for an inbox round-trip; optionally a knowledge
  lookup; plus `send_message` / `memory` / `todo` as the job needs.

The discipline is **list the minimum and stop** — "I'll add `terminal` just in case" is the
exact anti-pattern. Every tool you *don't* request is attack surface a hijacked or
prompt-injected bot has no way to reach.

**The locked floor is real, not a prompt promise.** A Talent only *requests* tools; the
host gateway decides what mounts. On a locked-down instance the gateway *also* disables the
generic toolsets, so even a prompt-injected Talent that asked for a shell finds none
mounted to call. The allowlist is your declaration of intent; the gateway is enforcement —
together they make "<bot> has no terminal" a structural property, not a hope. Never rely on
a `channel_prompt` line ("don't run shell") to keep a bot safe; rely on **not requesting**
the tool.

## 3. The `/json/2/` uplink is the data plane (checks 2 + 6)

A B2C bot's source of truth is a local SQLite db under `~/.hermes/data/<bot>/`. A business
bot's source of truth is **the business's Odoo**, reached over the authorized **`/json/2/`
uplink** — it reads and writes real business records, not a local db.

- The bot connects with its **own least-privilege bot user + a scoped API key** (delivered
  by the deployer as a secret, never baked — check 4 + the `secret` artifact class). It is
  not a human's login and not an admin key.
- The manifest declares **`odoo_grants`** — the explicit list of models/operations the bot
  user may touch. That binds the bot's reach: a grant the manifest doesn't name is a record
  the bot cannot read or write, even if its prompt tries.
- `required_artifacts.yaml` declares the uplink as the readiness condition (the bot user
  resolves + the scoped key is present + a probe read returns), the business-bot analog of
  "db file exists + tables present." A bot with no reachable uplink is NOT-READY and must
  not serve.
- **Namespacing still holds (check 6):** any *local* scratch the bot keeps stays under
  `~/.hermes/data/<bot>/`; the authoritative records live in the business's Odoo, reached
  only through the granted `/json/2/` scope.

## 4. Stub doubles for side-effecting actions — dev/staging vs prod (checks 9 + 14)

Any action that touches the **outside world** — filing on a portal, sending an email,
posting to a third party — ships **two implementations**:

- a **stub double** that records the intent and returns a believable result without doing
  anything real, and
- the **real adapter** that performs the action.

Which one mounts is bound by the **uplink tier below the Talent, not by the bundle**:
**dev and staging mount the stub; prod mounts the real adapter.** The same Talent ships
**unchanged** dev → staging → prod — the tier swaps the double underneath it.

- A non-prod bot **structurally cannot** cause a real side effect: there is no real adapter
  mounted to call, so nothing the prompt does can file on the live portal or send a real
  email. This is the side-effect analog of the locked toolset (§2) — enforced below the
  Talent, not promised in its text.
- It also unlocks honest testing: because non-prod is side-effect-safe, the **full
  behavioral suite can run against a real test instance on every deploy** without risking a
  real-world action.
- This is the stub-and-degrade contract of **check 9**, extended to side effects: declare
  the real adapter as the dependency, ship the stub as the non-prod double; the persona
  reads identically against either.

## 5. Testing — the live Discuss driver (check 14)

A business bot's `tests/scenarios/*.yaml` run the same two-backend way as a B2C bot, but
`--backend live` drives **Odoo Discuss** instead of Telegram — the business-bot analog of
the Telegram scenario backend:

1. **post a turn** into the test bot's `discuss.channel`,
2. **poll for the reply** in that channel,
3. **assert ground truth over `/json/2/`** — read back the records the turn should have
   written/changed on the test Odoo (the data-plane assertion, the business-bot analog of
   the SQLite `state:` checks).

Because the test instance is non-prod, its stub doubles (§4) catch every side effect, so a
deploy can run the whole suite live with zero real-world action. Mock-backend scenarios
still assert the deterministic layer offline in CI; anything only the live channel can
judge (reply quality, the Discuss round-trip) is recorded `SKIP` offline and proven live.

## 6. The bot as a workflow executor (checks 5 + 6)

A business bot need not only *answer* a team in chat; it can be the **executor of a
workflow transition** — one isolated agent turn per bot-owned transition. The pattern: the
business's Odoo owns a state machine, and specific states/transitions belong to the bot;
each bot-owned record is driven through them by a **fresh isolated turn** — its own session,
not the team's running conversation.

- **The dispatch trigger — the owner's Odoo asks over the bot's own channel.** The primary
  trigger needs **no external poller and no inbound webhook**: the owner's Odoo iterates its
  own queue of bot-owned records (the ones in a state whose workflow declares it the bot's to
  advance) and, for each, **posts a flagged message into the bot's own chat channel**. The
  bot's *existing* channel poll — the same one it uses to answer the team — picks the flagged
  message up and runs it as a **fresh isolated turn**. Odoo asks; the bot's own poll answers.
- **A flagged message runs isolated.** A leading sentinel on the message marks it *isolated*:
  the adapter strips the sentinel and gives that turn a **unique per-message chat id**, so the
  gateway keys it to a **fresh session** — the same isolation a per-delivery webhook turn
  would get, over the chat channel. An unflagged message keeps the shared channel chat id, so
  the team's conversation still accumulates in one session. The sentinel string is a **pinned
  wire contract** — the owner-Odoo side that writes it and the bot-adapter side that parses it
  must agree on the exact literal.
- **The thin prompt — name the record, not its data.** The dispatch prompt is deliberately
  **thin**: it names the skill to load and the record ("record #id"), and **nothing else**.
  The bot fetches the record's DTO itself over its `/json/2/` uplink, so no business data (PII)
  ever rides the chat channel. The workflow shape emits the prompt from generic role flags, not
  a hard-coded reference.
- **The idempotent claim.** Before (or as) it dispatches, the owner's Odoo **claims** the
  record — advances it out of the queue state (e.g. into a visible "working" state). The claim
  is idempotent and removes the record from the queue, so a re-run never dispatches the same
  record twice. The turn does its one job (file, send, record) over the `/json/2/` uplink and
  the transition advances.
- **Generic role flags, not xml-ids.** The workflow declares which states and transitions
  are the bot's via **generic role flags** on the states/transitions (a state is a queue / a
  work-in-progress / a watch state; a transition is claim / work / escalate). The dispatch
  resolves the bot's work purely from those flags and the workflow shape — it never
  hard-codes a specific state or transition, so any workflow-bearing model becomes
  bot-drivable just by flagging its states.
- **The escalate hand-back.** When the agent cannot finish (a rejection, an unexpected
  state), it takes the **escalate** transition — the bot's own failure hand-back to a human.
  This is the agent reporting "I can't", distinct from the reaper below.

An **inbound webhook + a manual per-record dispatch command** remain as an operator
**escape hatch** for backfill and recovery, but the two triggers must not both run
automatically at once — each would claim and fire the same record (a double side effect). The
channel-dispatch trigger is the primary automatic path; any automatic webhook/timer belt stays
off while it is live.

### The timeout reaper — the owner's backstop

The claim/escalate pair covers the cases where the dispatched turn *runs*. It cannot cover a
turn that **died mid-run and never reported back** — the gateway crashed, or never received
the dispatch — leaving a record stuck in the work-in-progress state forever. The backstop is a
**timeout reaper**: an Odoo scheduled action, owned by the business's Odoo (not the bot), that
finds work-in-progress records stuck past an **SLA timeout** and hands them back to a human
through the state's timeout exit.

- The reaper is the **safety belt for a dead run**, distinct from the `escalate`
  hand-back (which is the agent's *own* admission of failure while alive). One is the owner's
  Odoo reclaiming a stuck record; the other is the agent voluntarily giving one back.
- Each work-in-progress state carries its own SLA (in minutes); a zero SLA disables the
  reaper for that state.

## 7. Owner-visibility: your bot's activity log in your Odoo (check 6)

A B2C bot's activity is visible only to its owner in chat. A business bot serves a *team*,
and the owner needs to review **every exchange** from inside their own Odoo — the
external-bot analog of a native in-Odoo agent's logs. The bot writes each exchange back:

- **The write-back.** After each turn, the bot records **one session** into the business's
  Odoo over `/json/2/` — the exchange (turns, outcome) plus an **advisory soft-ref** to the
  record it was about (an origin model + id). The session is soft-linked, not a hard foreign
  key: the addon is domain-agnostic and the bot already has write access to those records.
- **Idempotent bot identity.** The bot lives *outside* the owner's Odoo, so nothing
  pre-seeds its record there — the bot **upserts its own identity** on first activity (keyed
  by its uplink reference, race-safe via a unique constraint). The log then appears the
  moment the bot first acts.
- **Best-effort, never fatal.** Recording the activity is best-effort — a logging failure
  **must not fail the transition** the bot just did. The write-back wraps the real work; if
  the log write throws, the work still stands.
- **The trust model.** The log is the bot's **self-report**, scoped to its own bot identity
  (matched by its uplink reference — an uplink reaches only its own owner's Odoo, so there is
  no cross-tenant reach). The origin soft-ref is advisory and unvalidated. The owner reviews
  the sessions from a **smart button on the record** the bot worked, or a per-bot activity
  view — every exchange, in their own Odoo, without touching the bot host.

## Grading deltas (run alongside the 14 checks)

- **Routing** — `routing.channel: discuss`, a team-channel `channel_prompt`, no Telegram
  assumptions. (PASS/FAIL)
- **Toolset** — minimum allowlist; `terminal`/`execute_code`/`skills`/open-web **absent**;
  every named tool justified by the job. (PASS/FAIL)
- **Data plane** — reads/writes the business Odoo over `/json/2/` with a least-privilege bot
  user + scoped key (delivered, not baked); `odoo_grants` declared and bounded; uplink is
  the `required_artifacts.yaml` readiness condition. (PASS/FAIL)
- **Stub doubles** — every outside-world action ships a stub + a real adapter, bound by
  tier (dev/staging = stub, prod = real); the same bundle ships across tiers unchanged.
  (PASS/FAIL)
- **Tests** — `tests/scenarios/*.yaml` drive the live Discuss channel and assert ground
  truth over `/json/2/`; the suite is safe to run live because non-prod is stubbed.
  (PASS/FAIL)
- **Workflow executor** — if the bot advances a workflow, its states/transitions are marked
  by generic role flags (queue/work/watch, claim/work/escalate); the owner's Odoo dispatches a
  transition by posting a flagged (isolated-sentinel) thin prompt — record id, not its data —
  into the bot's own channel, which the bot's existing poll runs as a fresh isolated turn (no
  external poller, no inbound webhook); the claim is idempotent, and a timeout reaper on the
  owner's Odoo backstops a dead run. (PASS/FAIL / N/A)
- **Owner-visibility** — the bot records each exchange as a session in the owner's Odoo over
  `/json/2/` (soft-linked to the record, idempotent bot identity, best-effort so a log
  failure can't fail the work); reviewable from a smart button on the record. (PASS/FAIL / N/A)
