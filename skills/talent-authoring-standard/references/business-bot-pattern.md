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
  channel rather than a 1:1 DM.

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
