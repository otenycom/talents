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

- **OFF for a scoped bot:** `terminal`, `execute_code`, filesystem, and the open-web
  search tools. None of these mount unless the job genuinely needs them. (The gateway
  keeps a small `skills`/`clarify` **read floor** mounted — `skill_view` must work for the
  bot to load its own composing skills; what's off is skill *creation/self-editing*, see
  the lockdown below.)
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

**No self-modification (the lockdown).** On a locked instance the platform *also* disables
cross-session self-learning: the post-turn self-improvement review never spawns, persistent
memory and the user profile are off, the skill curator is off, and the delivered Talent
tree is **read-only** on disk between deliveries. So a business-bot Talent must never
depend on `skill_manage`, runtime memory, or editing its own files — **all improvement
ships through the source repo → lint → delivery**, exactly like code. (This exists because
a live bot once rewrote its own delivered playbook mid-run; on a locked bot that is now
structurally impossible. A B2C assistant keeps self-improvement — there it *is* the
product.)

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

## 4b. Fail closed — never fabricate a side effect (checks 7 + 14)

The worst failure a business bot can produce is not a crash — it is a **confident lie**: a
run that could not perform the real-world action but *reports success anyway* (an invented
confirmation number, a record advanced to "done" with nothing behind it). A weak-tier model
under pressure will improvise exactly this. Two rules, both mandatory:

- **The Talent fails closed.** Any external identifier or proof (a filing number, a booking
  reference, a receipt) is **READ from the external system's confirmation** — never
  constructed, templated, or guessed. If the adapter is blocked/unreachable/errored/timed
  out, or a read returns 403, the action **did not happen**: write nothing, advance
  nothing, take the **escalate** transition to a human, and say why. A 403 is a STOP —
  never a method-name-guessing loop. Give the skill the **exact escalate call** (the same
  advance method through the escalate transition) — a model told to "escalate" without the
  mechanics will invent method names hunting for one.
- **The server refuses an unproven "done" (the claim guard).** Don't only trust the
  Talent's discipline: the workflow's single advance choke point exposes a guard hook, and
  the domain layer refuses the success transition unless the **proof record actually
  exists** (e.g. a captured, non-placeholder filing number on the credential). A run that
  skips the proof — on *any* model — is refused server-side, stays in-progress, and the
  timeout reaper hands it to a human. Escalation is **never** blocked by the guard: a stuck
  run must always be able to reach a person.

Grade both with **adversarial red scenarios** (below): induce the failure (portal down, a
revoked grant) and assert the *negative* ground truth — the record did NOT advance, no
proof exists, the reply escalates and never claims success.

## 4c. Your test double is YOUR fixture — self-host and tunnel it (the dog-food rule)

A subtle ownership failure is putting the stub double (§4) on the *platform's* infrastructure.
Negate it: a business-bot author is **not** on the platform team, yet must be able to build, run,
and change their own double with only their repo + a laptop. So the double **and** the real
system's identity are **yours, in your repo**; the platform provides only the generic wiring.

- **The double is a fixture in your repo** — ideally **dependency-free** (any stdlib HTTP server)
  and shaped like the real system (its form fields, its confirmation format). You run it locally and
  expose it at a public URL with a **dev tunnel** (`cloudflared tunnel --url http://127.0.0.1:<port>`);
  the platform points a non-prod bot's tool at that URL through a **generic tier knob** (an env var),
  never at a platform-hosted service. The platform hosts no double of yours.
- **You declare your external systems in the Talent; the platform binds each by tier.** Every
  outside-world system the bot touches is **named in the agent profile** — `external_systems:` is a
  list of `{name, env_var, real_url, fence_hosts}`, and `portal:` is sugar for a single system bound
  to a default env var. For each, the platform binds **one** URL by the uplink tier — **prod → the
  Talent-declared `real_url`; any non-prod tier → the stub** — and exposes it to the bot's tool as
  `<env_var>=<base>`; on a non-prod tier it also fences the browser off the **union** of every
  declared `fence_hosts`. The platform *binds/fences whatever you named* and hard-codes no third
  party's address, so it stays generic across every client's bot. **The prod identity (`real_url` +
  `fence_hosts`) lives in your Talent** and is versioned with it; the throwaway stub value does not
  (next bullet).
- **The stub URL is a request-time knob — never committed, never a platform config field.** Your
  local double's tunnel URL changes every run and is *not* part of the bundle, so you hand it to the
  platform **at request time**: the dev launcher passes it into the spin-up as the stub endpoint for
  the named system (keyed by the system's `name`), the platform threads it into that one converge, and
  it is **never persisted** as a control-plane field on the bot. A later re-converge that carries no
  spin-up config **preserves** the already-delivered non-prod stub rather than resetting it. Net: the
  **prod address is versioned in the Talent; the ephemeral stub address is supplied per request** and
  fenced as a non-prod double — a non-prod base that resolves to one of your Talent-fenced real hosts
  is refused.

**Rule:** *platform = mechanism, your repo = domain fixture, you self-host via a tunnel.* The
identifier your double returns should match the **real format** (so the server-side proof guard, §4b,
validates it), but that exact shape must **not** be disclosed to the model anywhere in the Talent — an
undisclosed invariant a confabulation can't dress to pass.

*Worked example (Barney, the Dutch posted-worker filer):* the meldloket double is a stdlib
`http.server` in the client repo (`cuneus_barney/stubportal/`, minting a bare 9-digit number — the
real portal's shape); the Talent declares `portal.real_url` + `portal.fence_hosts`; the server-side
claim guard refuses a "filed" whose number isn't the right shape; and one dev command (below) starts
the double + tunnel and points the bot at both its Odoo and the tunnelled double.

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

**Automate the setup — one command, not a checklist.** Dev iteration and e2e testing should be
push-button. A single **launcher script** (the platform's "point-bot-at-local" pattern) brings up the
whole rig: start the double (§4c) + its tunnel, tunnel your local Odoo, mint the bot's scoped key,
resolve its channel, point the bot's uplink **and** its double at the tunnels, and re-deliver the
Talent — so running the graded suite (or handing the bot a job) is the only step you do by hand. Make
the launcher **idempotent** (reuse an already-running double + tunnel) so re-runs are fast, and give
it a **stub-only** mode (start just the double + tunnel) and a **one-shot** mode (double + uplink in
one go). The same setup can run inside a **test runner's setup phase** so the full e2e — *bring up the
rig → run the scenarios → tear down* — is a single command. (This is control-plane orchestration, so
the runner is a thin script or a `pytest` fixture that shells out to the launcher, **not** an in-Odoo
`TransactionCase` — the framework test class boots one Odoo, not a tunnelled live bot.)

*Worked example (Barney):* `point_barney_at_local.py` is the launcher — bare = uplink only,
`--stub-only` = just the meldloket double + tunnel, `--with-stub` = the one-shot e2e (double + tunnel +
uplink + point the bot); each is a VS Code launch config. Then `hermeshost test --ref <bot> --bundle
<bundle>` runs the graded scenarios against the live, side-effect-safe bot.

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
- **Watching a dispatched run — the verbose debug flag.** An isolated dispatched turn is
  **silent by design**: its unique per-message chat id is a throwaway session, so its reply
  never lands in the channel. To diagnose one, the dispatch may carry an **optional verbose
  flag** — a second pinned sentinel after the isolated one — and the adapter then streams a
  live trace into the channel: an immediate "starting…" ack (before the first, slow model
  call), one line per uplink tool call (✅ on success / ⚠️ + the failure class on error), and a
  "still working" heartbeat when a run goes quiet past an idle threshold. Each line is **plain
  text with an emoji marker** (Discuss renders a body as-authored — never inject HTML, it
  surfaces as literal tags) and is prefixed with the run's **work-token** so overlapping /
  parallel runs stay attributable in one channel. It is a **debug aid** — chatty and it costs
  channel writes — so it is **off** unless the workflow turns it on (Barney carries the flag on
  its claim transition); enable it to watch a filing run, disable it once the workflow's
  run-health is trusted.

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
- **Fail-closed** — every external proof is read from the confirmation, never constructed;
  a blocked adapter or a 403 escalates (with the exact escalate call in the skill); the
  success transition is server-guarded on the proof record; the bundle ships at least one
  **adversarial red scenario** inducing the failure and asserting the negative ground
  truth. (PASS/FAIL)
- **Workflow executor** — if the bot advances a workflow, its states/transitions are marked
  by generic role flags (queue/work/watch, claim/work/escalate); the owner's Odoo dispatches a
  transition by posting a flagged (isolated-sentinel) thin prompt — record id, not its data —
  into the bot's own channel, which the bot's existing poll runs as a fresh isolated turn (no
  external poller, no inbound webhook); the claim is idempotent, and a timeout reaper on the
  owner's Odoo backstops a dead run. (PASS/FAIL / N/A)
- **Owner-visibility** — the bot records each exchange as a session in the owner's Odoo over
  `/json/2/` (soft-linked to the record, idempotent bot identity, best-effort so a log
  failure can't fail the work); reviewable from a smart button on the record. (PASS/FAIL / N/A)
