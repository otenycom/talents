---
name: oteny-talent-dev-loop
description: "Run a Talent's test/clone/staging dev loop on Oteny — clone, reload, test, read traces, fix, green, tag."
version: 1.0.0
author: Oteny
license: MIT
metadata:
  hermes:
    tags: [authoring, testing, staging, clone, traces, verify, dev-loop, oteny]
    related_skills: [talent-authoring-standard, oteny-talent-authoring]
---

# The Oteny Talent dev loop

The verification loop for a Talent: prove it *behaves* — not just that it lints —
by running it against a real, disposable, neutralized **clone** on Oteny's prod
fleet, reading its debug traces, and gating a push *commit → staging → green/red*
before you tag a release. This is the recipe an AI coding agent (or you) follows;
the primitives are the Oteny dev CLI verbs + the `/json/2/` seam, all scoped by
**your own account's key** — you can only touch your own (and granted/demo) bots.

> **Read first:** the rubric [`talent-authoring-standard`](../talent-authoring-standard)
> (what a bundle must satisfy) and the how-to [`oteny-talent-authoring`](../oteny-talent-authoring)
> (create → edit → package → publish). This skill is the *test/ship* rung on top.

## New here? The whole journey (write → prove → ship), plain English

A Talent is **content** (a persona + skills + a tool request + tests), not a server. You never
provision anything by hand — you edit files, push, and the platform **delivers** your commit onto
a bot. The journey has three environments, and a git ref decides which bot each reaches:

| Environment | The bot | What the git ref is | How your change gets there |
|---|---|---|---|
| **Dev** | a **clone** you stand up (a throwaway, budgeted, *neutralized* copy of real state) — or a fixed dev bot | your working **branch** | `clone` once, then `reload` on every push (or a source in *follow* mode auto-delivers the branch HEAD) |
| **Staging** | the staging bot | a **staging branch** (`dev`) | merge your branch → the *follow*-mode source auto-delivers |
| **Prod** | the production bot | a **release tag** (`<talent>-v<semver>`) | cut the tag → the *pinned*-mode source delivers, on-VM gate + auto-rollback |

The one loop you actually run, and what each step *does*:

1. **Edit** the bundle on a branch. **Bump** `agent-profile.yaml: version:` (every change).
2. **Lint** offline (`lint-talent --dir <bundle>`) — content sanity + safety, before you ever
   deliver. Also runs in CI on push.
3. **Get a container to test on** — `clone --from <a source you may touch> --bundle <slug> --branch
   <branch> --byob <token>` mints a disposable bot (`{ref: hh0…}`). This is the "set up a dev
   container" step — one command, no infra. (A business bot points its uplink at a **staging**
   business Odoo; `neutralize.yaml` repoints the seam + stubs any real portal/mailbox before it
   serves.)
4. **Deliver your change** — `reload --ref <clone>` ships your pushed commit onto the clone
   (stage → swap → gate → auto-rollback). This is a "talent upgrade": the same delivery prod uses.
5. **Run the tests** — `test --ref <clone> --bundle <slug>` drives the bundle's
   `tests/scenarios/*.yaml` **live** and grades them green/red. (Run `reinit` first for the result
   you trust — a clean tree so a removed file can't leave a false PASS.)
6. **Review results** — a red run tells you which turn failed and why; open `traces --ref <clone>`
   (the tool-by-tool debug eye) or `logs --ref <clone>` (live gateway markers). Fix, push, repeat.
   For a business bot you can also just hand the job in the business Odoo and read the bot's
   activity log — same truth, no CLI.
7. **Decide to promote** — green + lint-clean → **merge** to the staging branch (auto-delivers to
   staging), shake it out live, then **tag** the release for prod. Roll back = re-tag the last good
   version. That's the whole ladder.

Everything below is the detail of those steps. Two equivalent fronts run the same machinery:
**interactive** (you drive the verbs) and **CI** (`request-staging-run` + poll → a green/red commit
status). All of it is scoped to **your own account's key** — you can only touch your own, granted,
and Oteny demo bots.

## When to use

- You changed a Talent (copy, a child skill, a tool request, a state-shape
  migration) and need to prove it still works before shipping.
- You are adding a `migrations.yaml` entry and must prove the migration runs
  against **real prior-shape state**, not just a fresh box.
- You are an external author wiring a one-push **green/red** gate into your repo CI.

## The loop in one picture

```
edit bundle on a branch ──► git push
   │                          │
   │                          ▼  (CI) request a staging run over /json/2/
   │                          │   hh.talent.staging_run.request_staging_run(source_id, commit_sha)
   │   lint-talent --dir      │      → poll staging_run_status(run_id) to GREEN / RED
   │   (offline gate)         │
   ▼                          ▼
 clone ──► reload ──► test ──► traces ──► fix ──► (green) ──► tag a release
 (your throwaway prod bot)    (debug)
```

Two equivalent fronts: **interactive** (you drive `clone`/`reload`/`test`/`traces`
yourself) and **CI** (`request-staging-run` + poll → a green/red commit status).
Same machinery, same record-rule scope.

## The verbs (every one returns a JSON DTO; non-zero exit on failure)

| Step | Verb | What it does |
| --- | --- | --- |
| Lint | `lint-talent --dir <bundle>` | The static authoring-standard gate, **offline**. Run before you ever clone. |
| Clone | `clone --from <source> --bundle <slug> --branch <dev> --byob <token-file>` | Stand up a disposable, **neutralized**, budgeted clone of a permitted source's real state. Source is never touched. |
| Reload | `reload`/`deliver-external-talents --ref <clone>` | Deliver your pushed commit to the clone (D35 stage→swap→gate→rollback). |
| Test | `test --ref <clone> --bundle <slug> [--scenario <glob>]… [--junit out.xml]` | Run the bundle's `tests/scenarios/*.yaml` LIVE against the clone; green/red + trace. Repeatable `--scenario` (name or glob on the file stem) selects a subset — how mutually-exclusive scenario classes run as separate invocations; a glob matching nothing fails loud. |
| Traces | `traces --ref <clone> [--session <id>]` | The structured session/turn/message debug trace — the agent's debugging eye. |
| Logs | `logs --ref <clone> [--lines N]` | Tail the clone's live gateway-log markers while iterating. |
| Selfcheck | `selfcheck --ref <clone> --bundle <slug>` | Run the bundle's `selfcheck.py` on the clone (`{ready, missing}`). |
| Migrate | `migrate-talent --ref <clone> --bundle <slug> [--apply <id>]` | Drive `migrate.py --status` / `--apply <id>` on the clone. |
| Reinit | `reinit --ref <clone>` | Re-create the clone clean — run before a *gating* test so a removed file can't leave a false PASS. |
| Reap | `reap --ref <clone>` | Destroy the clone (container + snapshot). Source untouched. |

CI path: `request-staging-run --source-id <id> --commit <sha>` → poll
`staging-run-status --run-id <id>` until terminal.

## The tight loop

```bash
oteny-talent-lint skills/oteny-flatbelly-talent           # 1. offline gate, fix violations
clone --from <canary> --bundle oteny-flatbelly-talent --branch dev --byob ./bot.token
# → { ref: hh00231, ... }
reload --ref hh00231                                       # deliver your branch
test   --ref hh00231 --bundle oteny-flatbelly-talent      # green/red
traces --ref hh00231                                       # read what it did, fix, push, repeat
reinit --ref hh00231                                       # before the gating run (clean tree)
test   --ref hh00231 --bundle oteny-flatbelly-talent      # the result you trust
reap   --ref hh00231                                       # done
```

## Business-bot Talents (Discuss / a workflow trigger, not a chat DM)

A **business-bot** Talent (one whose `routing.channel` is an Odoo `discuss` channel and whose
source of truth is a business Odoo over the `/json/2/` uplink, not a local sqlite db) tests the
same way, with three differences:

- **Scenarios are `live_only`** and assert **`uplink`** ground truth, not `state` over a local
  db — the effect lives in the business Odoo, so a turn declares
  `expect.uplink: [{model, domain, equals/count}]` (read back over the uplink) instead of a
  `state` query. There is no mock backend to seed.
- **A `hand_off` turn triggers the REAL workflow path.** Instead of `user:` (a chat message), a
  turn may declare `hand_off: {model, domain, to_state}` + an optional `reply_timeout`: the
  driver writes the record into its bot-queue state over the uplink — exactly as a human hand-off
  does — which fires the platform's own token-fenced dispatch, then waits for the bot's channel
  narration. Use `hand_off` (not a driver-posted flagged message) so the scenario exercises the
  real claim fence, not a legacy path. Fixture must match **exactly one** record (seed/reset it).
- **The clone points its uplink at a STAGING business Odoo** (never prod), and `neutralize.yaml`
  repoints the seam + confirms any side-effecting adapter (portal/browser/mailbox) is the stub.
- **Adversarial red scenarios run in their OWN invocation.** A red scenario (the fail-closed
  proof — see the authoring standard's `behavioral-scenarios.md`) needs its failure **induced
  at converge/setup** (point the clone's portal env at a down/blocked URL, or revoke the bot
  user's grant on a needed model), each with its own fresh `hand_off` fixture. Red and happy
  classes need **opposite** portal/grant states, so never run them in one `test` invocation —
  select the class with the repeatable `--scenario` flag, e.g. the portal-UP class
  `test --ref <clone> --bundle <slug> --scenario <happy_path> --scenario red_team`, then the
  portal-DOWN class `… --scenario <portal_down_probe>` after re-converging.
  A fail-closed run is SHORT — the pass condition is the record did **not** advance and no
  proof was written, with an escalating reply.

`test --ref <clone> --bundle <slug>` runs these the same way; the driver skips the gateway's
progress frames ("⏳ Working…") and grades the final narration + the uplink asserts.

**Reading a business-bot run (the same eye, three front-ends).** When a dispatch is running you
get a live tool-by-tool picture — `✅`/`⚠️` per `/json/2/` call, with the method and, on a failure,
the HTTP class **and the offending model** (e.g. `⚠️ … riverflow.service.search_read — 403
access-denied (crewradar.site.type)`). An **operator** sees this narrated straight into the Discuss
channel (a verbose-flagged dispatch); **you, the author, read the identical picture** — you do not
need the operator's channel or any SSH — three ways, all record-rule-scoped to your own bots:
`traces --ref <clone>` (per-turn, tool-by-tool), the **Author Logs portal**, and, for a business
bot, the **Bot Activity log in the business Odoo itself** (hand the job, read the run — no CLI).
Each failing call carries Odoo's **native** error text, which names the **denied** model, not the
one you called — so you map a `403` straight to the missing grant (see the silent-failure entry
below).

## See inside your bot's box (inspect + shell — your box, over your account key)

Sometimes the traces aren't enough: you need to see the box's **resolved config** (what URL is
your bot's browser actually pointed at? did the stub binding land?) or query the Talent's own
sqlite state, tail a log live, delete a poisoned row and re-dispatch. Two self-serve, out-of-band
windows into a box **your account owns or is billed for** (dev **and** prod) — both driven over
your account key on `hh.box_access_request`, never a bot tool:

**`inspect` — a one-call, redacted snapshot.** Request it, poll to `done`, read `snapshot`:

```
request_box_access(ref="hh0xxxx", kind="inspect")     # → {accepted, request_id}
box_access_status(request_id=<id>)                    # poll → {state: "done", snapshot: {...}}
```

The snapshot carries: `external_env` (the **resolved values** of the non-secret levers — your
Talent's declared `OTENY_*` external-system URLs, the uplink URL/db, the discuss channel — the
exact thing that root-causes a "why is it pointed at the wrong host" bug), `env_keys` (every other
`.env` line as **name + length only** — a secret value is *never* returned), `manifest`,
`talents_tree`, a scrubbed `config_yaml`, `log_tails` (agent + gateway, scrubbed), and
`sudoers_present` (the hardened-box posture). Start here — it's cheap and answers most questions.

**`shell` — an ephemeral SSH shell into the sandbox as your bot's own user (`hermes`, uid 1001).**
The box runs standard Linux + standard Hermes, so a shell is the highest-value primitive. You
connect with **your own private key** (the platform never sees a secret):

You reach the box through a Cloudflare tunnel with the [`cloudflared`](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/)
CLI (install it once), in **two steps**: run a local bridge, then SSH to it.

```
# 1. generate a throwaway keypair (or reuse one)
ssh-keygen -t ed25519 -f /tmp/box -N ""
# 2. request the window with your PUBLIC key + an optional TTL (minutes; default 120, cap 480)
request_box_access(ref="hh0xxxx", kind="shell", ssh_pubkey="<contents of /tmp/box.pub>", ttl_minutes=120)
# 3. poll to state == "active" and read connect_info (hostname + bridge_command + ssh_command + note)
box_access_status(request_id=<id>)   # → {state: "active", connect_info: {hostname, bridge_command, ssh_command, note}}
# 4a. run the bridge (a local listener on 127.0.0.1:2222) — leave it running in one terminal:
cloudflared access tcp --hostname <hostname> --url 127.0.0.1:2222
# 4b. in another terminal, SSH to the local port with YOUR private key:
ssh -p 2222 -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=/dev/null -i /tmp/box hermes@127.0.0.1
```

(`accept-new` + a throwaway known-hosts file because the box's dropbear makes a fresh hostkey each
window — there's nothing stable to pin. The `note` field in `connect_info` is the ready-to-paste
version of both commands.)

The bot's state DB is `~/.hermes/state.db` (and per-Talent dbs under `~/.hermes/data/<slug>/`);
the image ships **no `sqlite3` binary**, so use the stdlib: `python3 -m sqlite3 ~/.hermes/state.db`.

**The contract you must honor:**
- The window is **TTL-bounded and auto-reaped**. On expiry or when you `close_box_access(request_id=<id>)`,
  the platform kills the tunnel, removes your key, and **rotates the box's model key** (you saw the
  `.env` — it's treated disclosed). Don't leave a window open; close it when you're done.
- Every open is an **append-only audit row** on your account.
- **Prod etiquette:** a shell on a real customer's prod bot is snapshot-first (reversible) but it's
  their live bot — check no dispatch is mid-run before you mutate state, and prefer `inspect` unless
  you genuinely need to change something.

`close_box_access(request_id=<id>)` tears a shell down early (don't wait for the TTL).

## The readiness contract: `active` is not enough — wait for `talent_delivered`

When you commission a fresh dev bot (`request_dev_bot`), poll `dev_bot_request_status` and treat a
bot as **e2e-ready only when `state == "active"` AND `talent_delivered == true`**. `active` alone
means the box booted (on defaults) — for an **external-Talent** bot the private bundle is delivered
*inline* just after, so `active` can briefly precede the Talent actually being on the box (the
skill-not-found race). `talent_delivered` is the true "your Talent is on the box" signal (a
catalog-only bot is `true` by construction). On `active` without delivery, the async belt still
converges it within ~5 min — poll `hh.talent.source.last_status == "delivered"` (visible to your
account key) before you start testing, or read `talent_delivery_error` for the reason.

## Proving a migration (the case a fresh box can't cover)

Ship the migration the normal way (append a `migrations.yaml` entry + a
`tests/scenarios/<x>.yaml` with `requires_migration: <id>`), then:

1. `clone --from <a real prior-shape bot>` — captures real old state + its
   `migrations.json` ledger (this is what makes the forward migration actually fire).
2. `reload --ref <clone>` your branch — `preflight` now surfaces `MIGRATIONS: pending`.
3. `migrate-talent --ref <clone> --bundle <slug> --apply <id>` (or let the agent
   drive the checklist turns).
4. `test --ref <clone> --bundle <slug>` — the `requires_migration` scenario flips
   from `skip` to `pass`, and prior rows are preserved. **Pass = no regression on
   real state.**

## The rules the loop enforces (don't fight them)

- **Provisioned/active means delivered — for an inline-delivery Talent.** A private/business-bot
  Talent (delivered from a private git bundle, not the public store) is delivered **inline at
  commission**: when the dev tooling reports the bot **provisioned / active**, the Talent *and* its
  tier-bound stub binding (§4c of the business-bot pattern) are already **on the box** — it is
  e2e-ready, run the suite. This is **not** universal: a Talent delivered **out-of-band** (an async
  delivery belt) is not on the box just because the container is active — wait for the source
  `last_status` to read *delivered* before you test.
- **What you can and can't see.** You diagnose your own bots — everything below is record-rule-scoped
  to your own (and granted/demo) bots — from three windows: **`traces`** (per-turn tool calls, the
  bot's LLM calls, and the session's **diagnostic events** — crashes/restarts, fail-close and browser
  blocks), the **Author Logs portal**, and the source **`last_status` / `delivered_at`** (the
  delivery outcome + timing). What you **cannot** see is the box's **effective config or filesystem** —
  the delivered `.env`, the on-disk talents tree, the node record are operator-only (a `403`).
  Diagnose box-config from **behavior** (a fail-close, the wrong host fenced, a stub not taking) in
  `traces`, not by reading the box.
- **Neutralize is default-ON.** Every clone runs the bundle's `neutralize.yaml`
  *before it serves a turn* (outbound crons off, seams repointed to staging,
  external logins swapped). If your Talent has any outbound action it **must** ship
  a `neutralize.yaml` (the lint enforces it). `--no-neutralize` is ops-only and only
  on a bot you own.
- **Redaction is automatic.** A clone of someone else's (granted/demo) state lands
  with third-party secrets stripped and the bot token / model key replaced. You can
  never extract another tenant's credentials through a clone.
- **You can clone only what you may.** `clone --from` is record-rule-scoped to your
  own bots + Oteny demo/templates + bots explicitly **granted** to you — never an
  arbitrary customer.
- **Billing.** A clone is free infra for 7 days; metered tool use bills *your*
  account from day 0 (a low spend cap bounds a runaway loop). At day 7 it converts
  to a Lite subscription or is reaped.
- **A dev-bot request can legitimately wait several minutes.** When the shared fleet
  is momentarily full, your request is **queued while the platform adds a server**
  (~3–6 min) — it is NOT failing; keep polling. It fails only if capacity can't be
  added within ~20 min ("no capacity after autoscale window"). Size your poll budget
  to outlast that window; don't give up at a few minutes and re-request (that just
  queues a second bot).
- **Your dev-bot footprint self-recycles.** You can hold a bounded number of live dev
  bots (default 5). Requesting one **at the cap recycles your own oldest dev bot**
  automatically (it stops counting immediately; its infra is destroyed within
  ~15 min) — you're only refused when nothing of yours is reapable. And there is
  **one live dev bot per Discuss channel**: re-commissioning onto a channel recycles
  your previous bot on it (two bots polling one channel answer each other's messages
  — the platform prevents it at the source). Corollary: exit your launcher cleanly
  (Ctrl-C / SIGTERM both tear down) so a session's bot doesn't linger until the
  reaper catches it.
- **Traces are yours.** `traces`/`logs` and the **Author Logs portal** show only
  your own (and granted/demo) bots — the same record-rule boundary, two front-ends.

## Troubleshooting (read the failure, don't guess)

- **`test` red, reply matcher failed** — read `traces --ref <clone>` for that turn: the reply
  is graded on `contains`/`not_contains`/`regex`; a genuine refusal or a differently-phrased
  success both show there. Loosen a brittle `contains` to a trace/`uplink` assertion (the
  behavioral truth) rather than pinning exact wording.
- **`test` red, trace marker missing/unexpected** — the tool you expected didn't run (or a
  forbidden one did). `logs --ref <clone>` shows `tool <name> completed`; a missing
  toolset means the platform lock or a `check_fn` gate dropped it (a business bot mounts only
  its `toolset_contribution`).
- **The run looks "silent" — no reply, or a near-empty `()`** — not a lost run; a **silent
  failure**. Read `traces --ref <clone>` for the turn: the tell is tool calls whose results
  carried **no signal** (an ACL/403 error, an empty envelope) followed by a near-empty final
  reply. Judge each tool/`uplink` result's error class, not just the reply — fix the cause (a
  missing grant, a wrong call shape), don't loosen the matcher. (`traces` is authoritative here:
  the gateway `logs` log successes as name + result-size only, so a run of silent no-signal
  results is invisible there.)
  - **A `403` result names the model it DENIED, not the one you called.** The result `error`
    is Odoo's native message ("_… not allowed to access 'Ship Type' (`crewradar.site.type`)
    records_") — e.g. a `search_read` on `riverflow.service` that pulls a computed DTO field can
    403 on a *reference* model behind it. Grant your bot's seam user read on **that** model;
    don't chase the called model. (A 403 that starts the bot **inventing** method names is a
    Talent bug — its rule must be "a 403 is a STOP: report the denied model and escalate"; the
    `read_403_no_guess` scenario pins it.)
- **Empty transcript/turns, but the run spent tokens/time (and a business bot's Bot Activity is
  stuck at "dispatched")** — different from the "silent" case above: the transcript is built from the
  clone's persisted session, flushed when a turn **finishes**, so a run that **crashed or looped
  without finishing** leaves it empty *even though it ran* and never wrote its result back. Read it as
  a crash, not a no-op: `traces --ref <clone>` still carries the session's **diagnostic events** (the
  gateway error stream — a dropped uplink/tunnel, a restart loop) and its token/model-call counters,
  recorded independently of the transcript. Fix the cause (restore the uplink/tunnel, clear the stuck
  process), don't re-run blind.
- **`hand_off matched N records` (N≠1)** — the fixture is absent or duplicated; seed exactly
  one matching record in the *from* state (reset a consumed one) before the run.
- **Clone won't serve / `neutralize_status: failed`** — the fail-closed gate refused (a seam
  still points at prod, or a required stub is missing). Fix `neutralize.yaml`; a clone never
  serves un-neutralized.
- **A long run is reaped mid-task** — the agent budget (`agent.max_turns`) is too low for the
  Talent's work; raise it per-tenant (an operator `config_overrides` knob) and re-run.
- **`clone`/`test`/`traces` says "not permitted"** — you can only touch your own + granted +
  Oteny demo bots; `clone --from` a source outside that scope is refused by the record rules.
- **A just-created bot isn't visible to your key for a moment** — right after you stand up a new
  bot, its bot/source records may not yet fall inside your account's record-rule scope (a brief
  staleness), so a `traces`/`test` against it can read empty or "not permitted" for a beat even
  though the bot exists. Give it a moment / re-fetch before concluding the stand-up failed.
- **A red scenario passes when it shouldn't / the happy path is red** — you ran the
  portal-up and portal-down scenario classes in one invocation; they are mutually exclusive
  (opposite induced states). Re-run each class under its own converge-time config, selecting
  it with `test … --scenario <name-or-glob>` (repeatable).

## Publish gate

When `test` is green and `lint-talent` passes, tag the release
(`<talent>-v<semver>` — the trailing semver must equal the committed
`agent-profile.yaml: version:`). A green staging run **auto-grades** the Talent:
an all-green run lists with no human review (`auto_passed`); a red/partial run
goes to the operator review queue. Community flags can quarantine a listing — keep
your Talent honest and your reputation rises in the Bot Market.

## Verification checklist

1. `lint-talent --dir <bundle>` exits 0 (no violations).
2. A clone stands up neutralized (`neutralize_status: ok`) and the source stays up.
3. `test` is green over every `tests/scenarios/*.yaml` (run after `reinit`).
4. A migration scenario reconciles real prior-shape state idempotently.
5. `traces` shows the expected tool calls and no approval stall / unbounded loop.
6. The release tag's semver equals the committed `version:`.
