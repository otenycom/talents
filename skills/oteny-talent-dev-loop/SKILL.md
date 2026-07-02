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
| Test | `test --ref <clone> --bundle <slug> [--junit out.xml]` | Run the bundle's `tests/scenarios/*.yaml` LIVE against the clone; green/red + trace. |
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

`test --ref <clone> --bundle <slug>` runs these the same way; the driver skips the gateway's
progress frames ("⏳ Working…") and grades the final narration + the uplink asserts.

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
- **`hand_off matched N records` (N≠1)** — the fixture is absent or duplicated; seed exactly
  one matching record in the *from* state (reset a consumed one) before the run.
- **Clone won't serve / `neutralize_status: failed`** — the fail-closed gate refused (a seam
  still points at prod, or a required stub is missing). Fix `neutralize.yaml`; a clone never
  serves un-neutralized.
- **A long run is reaped mid-task** — the agent budget (`agent.max_turns`) is too low for the
  Talent's work; raise it per-tenant (an operator `config_overrides` knob) and re-run.
- **`clone`/`test`/`traces` says "not permitted"** — you can only touch your own + granted +
  Oteny demo bots; `clone --from` a source outside that scope is refused by the record rules.

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
