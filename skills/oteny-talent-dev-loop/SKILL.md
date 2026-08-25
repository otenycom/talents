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
the primitives are the Oteny dev CLI verbs + named **connections** (odoo binds over
`/json/2/`), all scoped by **your own account's key** — you can only touch your own
(and granted/demo) bots.

> **Read first:** the rubric [`talent-authoring-standard`](../talent-authoring-standard)
> (what a bundle must satisfy) and the how-to [`oteny-talent-authoring`](../oteny-talent-authoring)
> (create → edit → package → publish). This skill is the *test/ship* rung on top.

## New here? The whole journey (write → prove → ship), plain English

A Talent is **content** (a persona + skills + a tool request + tests), not a server. You never
provision anything by hand — you edit files, **push**, and Oteny **pulls** your commit onto
a bot with **its** key. Your GitHub login stays on your laptop. The bot never runs `git clone`.
Full picture: [`how-delivery-works.md`](references/how-delivery-works.md).

The journey has three environments, and a git ref decides which bot each reaches:

| Environment | The bot | What the git ref is | How your change gets there |
|---|---|---|---|
| **Dev** | a **clone** you stand up (a throwaway, budgeted, *neutralized* copy of real state) — or a fixed dev bot | your working **branch** | `clone` once, then `reload` on every push (or a source in *follow* mode auto-delivers the branch HEAD) |
| **Staging** | the staging bot | a **staging branch** (`dev`) | merge your branch → the *follow*-mode source auto-delivers |
| **Prod** | the production bot | a **release tag** (`<talent>-v<semver>`) | cut the tag → the *pinned*-mode source delivers, on-VM gate + auto-rollback |

The one loop you actually run, and what each step *does*:

1. **Edit** the bundle on a branch. **Bump** `agent-profile.yaml: version:` (every change).
2. **Lint** offline (`oteny lint <bundle>`) — content sanity + safety, before you ever
   deliver. Also runs in CI on push.
3. **Get a container to test on** — `oteny clone --source <a source you may touch>` mints a
   disposable bot (`{ref: hh0…}`). This is the "set up a dev container" step — one command, no
   infra. (A business bot points its uplink at a **staging** business Odoo; `neutralize.yaml`
   repoints connections + stubs any real portal/mailbox before it serves.)
4. **Deliver your change** — push first, then `reload --ref <clone>`. Oteny pulls the
   pushed commit onto the clone (stage → swap → gate → auto-rollback). Unpushed files
   never reach the bot. Wait until `last_status` is `delivered` — `active` is not enough
   ([`how-delivery-works.md`](references/how-delivery-works.md)).
5. **Run the tests** — `test --ref <clone> --bundle <slug>` drives the bundle's
   `tests/scenarios/*.yaml` **live** and grades them green/red. Every `reload` is a fresh
   `git clone --depth 1` into a new tempdir, never an incremental pull — a removed file
   cannot linger and leave a false PASS, so there is no separate "clean the tree" step.
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

## Author surface vs Oteny staff (pit of success)

You are a **Talent author** (or a client team role-playing one). You hold an **account key** and
this public recipe. You do **not** need Oteny's private control-plane repo, node SSH, or an
**Oteny staff live run** (`commission --internal` with control-plane keys).

| Everyday author loop (default) | Oteny staff live run (not this skill) |
| --- | --- |
| Account key + **`oteny`** verbs (`test` / `traces` / `lint` / box `inspect`/`shell` / …) from [`packages/oteny`](../../packages/oteny/) | Private control-plane CLI + mgmt keys |
| Box access `inspect` / `shell` (your keypair + `cloudflared access tcp`) | Node / `runsc` into infrastructure you do not own |
| Business Odoo: hand the job → **Bot Activity** / Discuss | Staff-only harvest tools (`logs-pull`, …) |
| Reap / teardown your own author bots | Fleet terminate / reconcile of staff live-run bots |

If a doc tells you to run a private platform binary (`python -m hermeshost test` with staff
secrets) for ordinary Talent work, treat that as a **footgun** — use `oteny` instead.

### What still needs Oteny staff (honest gaps)

| Still staff-gated / partner-only today | Author substitute |
| --- | --- |
| Fleet admission / account mint for **arbitrary** outside authors (trusted partners already hold keys) | Offline lint + mock scenarios; Hand to Barney + Bot Activity when you have a bot but not the CLI key |
| Telegram DM transport on `oteny test` | Discuss (business bots); Telegram is Phase 2 |
| **`oteny test --transport cli`** — the channel-free hermes oneshot. It exits **rc=127** with empty stderr: the command runs a bare `hermes`, and on the box that binary sits at `~/.local/bin/hermes` under uid **1001**, which the account-scoped shell does not resolve (verified 2026-08-25) | Use `--transport discuss` on a business bot. That needs the target Odoo's uplink key **as well as** your account key, and its failure is a bare `HTTP 401 from res.users/search_read` that names neither. Otherwise drive the bot by hand and read `oteny traces`. |
| One-push CI drain (`request-staging-run` worker always-on) | Poll helpers exist on `oteny`; platform still drains the queue |
| Prod-tier real external portals, submit-deny, SMS 2FA | Stub / neutralized doubles |
| Private control-plane commission / `logs-pull` / node shell | `request_dev_bot` + `oteny` + box access |
| New business-account mint + connect Odoo + product “commission my bot” UX (**Path C** — hermeshost `plans/path-c-business-commission.md`) | Staff onboarding assist / D194 P0 scripted mint until the product surface ships |
| A **private git repo you own** that Oteny has never seen | A repo admin adds Oteny's read-only Deploy Key once. Public repos and Oteny-owned private repos (`otenycom/radar`) already work. See [`how-delivery-works.md`](references/how-delivery-works.md). |
| **`selector-audit` / `browser-diff`** (those verbs still live in hermeshost) | Harvest the accessible name from `oteny traces`. Put the observed name first. Do not copy a stub label. Promote the two verbs onto `oteny` so Path B can score a map without staff. |

*Business-bot canary:* a client repo (e.g. CrewRadar/Barney) provisions with
**`provision_barney.py --tier …`** (or launch **`barney-provision-*`**) + the Cuneus account key;
graded runs use **`oteny test --bundle-dir …`** from this recipe — not hermeshost staff secrets.
The platform returns **`claim_dev_bot_client_ingress`** as a three-token bundle (login-gate,
live-watch, replay-view); the provisioner writes those into the tier's broker seam every run.

## Four things version independently — know which one moved

Most "the bot is broken" reports are really "one of four things changed, and I assumed it was a
different one". Separate them before you debug, and the answer usually falls out.

| The thing | What it is | Who moves it | How it moves |
| --- | --- | --- | --- |
| **The box** | The container your bot runs in, and its memory/CPU/disk envelope | Oteny | A plan or size change; you ask for it |
| **The platform** | The agent runtime, the mounted tools, the browser broker — Oteny's software inside the box | Oteny | Converges on Oteny's schedule; you cannot trigger or defer it |
| **Your Talent** | Your instructions, skills, scenarios — files in **your** git repo | **You** | `oteny reload --ref <clone>` on a followed branch, or a release tag for a pinned bot |
| **The system it talks to** | The customer's Odoo/API/portal your bot reads and writes | The customer's team | Their own deploy |

Two consequences worth internalising:

- **Only the Talent is yours to version.** A platform converge restarts the agent, so an
  in-flight turn does not survive it and must be re-driven; your data and your delivered Talent
  do survive. If you need a quiet window for a demo or an acceptance session, ask for one — you
  cannot opt out of a converge yourself.
- **A followed branch and a pinned tag are different promises.** A dev or staging clone that
  follows a branch changes the moment you merge, which is what makes the loop fast. A production
  bot pinned to a tag changes only when someone cuts the tag — so "it worked on staging" is only
  meaningful if you tag the commit staging was actually running. Rollback is re-tagging the
  previous good version.
- **When your Talent is coupled to a backend, pin it to that backend's branch.** A Talent
  that names a field, a state or a transition only works against a deployment that has them.
  If your backend is promoted through branches — a dev branch, a staging branch, a
  production branch — then give each bot the branch **its own backend is built from**, and
  let both move together. One clock instead of two, and no release tag to cut or forget.

  This also makes an acceptance freeze free. A staging bot on the staging branch changes
  only when somebody promotes to it, so **the pipeline is the freeze** — there is no
  `<talent>-uat-<date>` branch to cut, and no un-freeze to forget. That un-freeze was a
  silent-staleness trap: a bot on a stopped branch keeps serving the frozen bundle, looks
  perfectly healthy, and every later edit lands nowhere with nothing reporting it.

  Two things still bite, whichever scheme you use:

  - **The bot clones the remote.** An unpushed commit can never reach it, however green your
    local tests are. Push before you test, and confirm what the box is actually running
    (`oteny inspect --ref <ref>`) before you conclude an edit "did not work".
  - **Delivery is a poll, and it does not know when your backend finished deploying.**
    Between a merge and a green build the Talent can be ahead of the schema. Promote before
    an acceptance session rather than during it, and when a bot misbehaves right after a
    release, check the deploy finished before reading anything into its behaviour.

**Dev clones are deliberately temporary.** A clone left idle is reaped, and an account has a cap
on live dev bots — at the cap the platform recycles your own least-recently-used clone to admit
the new one, rather than refusing. So an unattended sixth clone quietly costs you the stalest
one. What a reap destroys is what lived only in the box (working state, conversation memory, the
delivered copy of the Talent). What survives is everything that never did: the customer's data,
and your Talent in git. Re-running your provisioning with the **same slot name** gets a working
bot back under the same identity.

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
   │   oteny lint              │      → poll staging_run_status(run_id) to GREEN / RED
   │   (offline gate)         │
   ▼                          ▼
 clone ──► reload ──► test ──► traces ──► fix ──► (green) ──► tag a release
 (your throwaway prod bot)    (debug)
```

Two equivalent fronts: **interactive** (you drive `clone`/`reload`/`test`/`traces`
yourself) and **CI** (`request-staging-run` + poll → a green/red commit status).
Same machinery, same record-rule scope.

## Install the author CLI (`oteny`)

The verbs below are the public **`oteny`** package in this repo (`packages/oteny`).
You do **not** need Oteny's private hermeshost checkout or staff `odoo-api-key`.

```bash
uv tool install "oteny @ git+https://github.com/otenycom/talents.git#subdirectory=packages/oteny"
# monorepo / Path B dog-food:
uv pip install -e ~/oteny/talents/packages/oteny
```

Auth: `--api-key-file` or `OTENY_ACCOUNT_KEY` → your **account** key file (0600).
Business-bot Discuss scenarios also need `tests/discuss.yaml` → `tester_key_file`
(CrewRadar tester — not the Oteny account key).

Transports for `oteny test`: **Discuss** (business bots / `hand_off`), **CLI**
(`hermes chat` oneshot over box-access — plain chat turns), auto-pick. **Telegram
DM is Phase 2** (not in this package yet).

## The verbs (every one returns a JSON DTO; non-zero exit on failure)

| Step | Verb | What it does |
| --- | --- | --- |
| Lint | `oteny lint <bundle>` / `oteny-talent-lint` | The static authoring-standard gate, **offline**. Run before you ever clone. |
| Clone | `oteny clone --source <ref> …` | Account-key clone **gate** (`request_clone`). Platform worker drains infra. |
| Reload | `oteny reload --ref <clone>` | Ask Oteny to **pull** the pushed commit onto this bot. Push first. Wait for `last_status=delivered`. Do not reload mid-turn (`deferred_busy`). See [`how-delivery-works.md`](references/how-delivery-works.md). |
| Test | `oteny test --ref <clone> --bundle <slug> --bundle-dir <path> [--scenario <glob>]…` | Run `tests/scenarios/*.yaml` LIVE; **`--bundle-dir` required** (local checkout — no deploy key). |
| Traces | `oteny traces --ref <clone> [--session <id>]` | The structured session/turn/message debug trace — the agent's debugging eye. `page_snapshot` browser rows cover EVERY turn of a run, including the turns after a human login hand-off (donated sessions) and every follow-up turn — since 2026-08-25; a run before that date can show gaps there. |
| Logs | `oteny logs --ref <clone> [--gateway-tail]` | Harvest traces (+ optional redacted gateway tail via box-access). |
| Selfcheck | `oteny selfcheck --ref <clone> --bundle <slug>` | Run the bundle's `selfcheck.py` on the box via account-scoped shell. |
| Migrate | `oteny migrate-talent --ref <clone> --bundle <slug>` | Drive `migrate.py` on the box. |
| Inspect / shell | `oteny inspect\|shell --ref <clone>` | Box-access look-inside / exec (your keypair + cloudflared). `shell` retries a transient open (worker `ProcessError` rc 128, 429 inflight, tunnel not ready) and waits for teardown before it returns. Do not wrap your own retry loop. |
| Staging CI | `oteny request-staging-run` / `staging-run-status` | Commit→staging→green/red poll (full suite on staging clone — not Path B stub). |

Private hermeshost `python -m hermeshost test` with staff secrets is a **footgun** for
author work — use `oteny` above.

## The tight loop

```bash
oteny lint skills/oteny-flatbelly-talent                  # 1. offline gate
oteny clone --api-key-file ./account.key --source <canary>
# → request accepted; poll until active (or use request_dev_bot / client launcher)
oteny test --api-key-file ./account.key --ref hh00231 \
  --bundle oteny-flatbelly-talent --bundle-dir skills/oteny-flatbelly-talent
oteny traces --api-key-file ./account.key --ref hh00231
```

## Business-bot Talents (workflow / team chat + odoo data plane)

A **business-bot** Talent (source of truth is a business Odoo over `/json/2/` via
`odoo_client` + named `connections:`, not a local sqlite db; chat is usually Odoo
`discuss`, Telegram allowed — see `business-bot-pattern` §1/§3) tests the
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
  repoints connections + confirms any side-effecting adapter (portal/browser/mailbox) is the stub.
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
need the operator's Discuss channel — three ways, all record-rule-scoped to your own bots:
`traces --ref <clone>` (per-turn, tool-by-tool), the **Author Logs portal**, and, for a business
bot, the **Bot Activity log in the business Odoo itself** (hand the job, read the run — no CLI).
Each failing call carries Odoo's **native** error text, which names the **denied** model, not the
one you called — so you map a `403` straight to the missing grant (see the silent-failure entry
below).

**Browser-driven bot?** `traces --ref <clone>` also returns a PII-free `browser_traces` list +
`browser_summary` — one action row per native `browser_click` / `browser_type`,
**and** `page_snapshot` form-control inventories from observe walks
(`browser_snapshot` / `browser_navigate`).
`browser_summary.pages_captured` / `controls_captured` tell you whether the walk left usable
inventory. `selector-audit` and `browser-diff` still live in hermeshost.
An outside author cannot run them on Path B today. Until they land on
`oteny`, harvest the accessible name from `traces` and put that name first.
Pattern + manifest format:
[`business-bot-pattern.md`](../talent-authoring-standard/references/business-bot-pattern.md) §4e.

**Grading a click: did it stick?** Since 2026-08-25 an action row carries more than
"the tool returned success". It names the snapshot ref your bot acted on, what that ref
resolved to on the page (`el_id` / `el_name` / `el_type`), and — for a radio or a
checkbox — the **`checked_state` read back after the click**. Read that field before you
believe a green step.

The reason it exists is a whole class of silent failure. A click can report success and
change nothing: the control was outside the viewport, or covered, or the handle was
stale. The accessibility snapshot cannot show you that, and neither can the tool result,
so a run walks on past a field it never set. `browser_summary.click_no_ops` counts
exactly that case — **a click that reported success on a control that is still
unchecked**. Treat any non-zero value as a failed step, whatever the transcript says.

A typed value never appears in a trace. It rides as `value_len` plus a `value_sha`
digest, and `value_matched` tells you whether the field ended up holding what your bot
typed. The same fingerprint appears on each control in a `page_snapshot` inventory, so
you can compare a page before and after without ever seeing a customer's data.
The intended loop is **`traces` → `browser-diff`**, not shell → `state.db`: conversation/tool blobs are the
wrong store for selector inventories. You already have box `shell` / `inspect` for Talent DBs,
logs, and forensics (below) — a different job.

**See the browser, not just the trace.** A dispatched run records the opaque cloud-browser
session ids it used onto its **Bot Activity** row in the business Odoo, which turns them into
two buttons: **Watch live** (a read-only view while the run is still going — the fastest way to
see *why* a form step is stalling; the ids land as soon as the first `browser_*` tool opens a
session — refresh the form if the button is still hidden) and **Replay** (the recorded session,
playable for 48 hours after the turn ends — the eye on a run that already failed; if the chip
says Replay available a moment early, click anyway — the platform closes the short linger and
opens the player, or asks you to wait while the recording finalizes). Nothing to add to your
bundle: you get both by using the brokered `browser_*` tools instead of your own automation.
That business Odoo needs **both** Watch and Replay credentials (not only the login-gate token)
— ask Oteny if the chip says replay is not configured. If the row still says **No browser used**
while Discuss shows an active filing, the bot's discuss plugin is stale (redeliver/converge) or
those purpose tokens were never claimed.

## When your live bot fails (post-incident repair)

The loop above is **pre-ship** iteration. Once a bot is **live in prod** the same loop runs in
reverse — a real failure becomes the next pinning scenario. This is the steady-state maintenance
recipe, and it is the *only* way a bot improves: never by editing the delivered bot in place.

**Trigger.** You act on one of: an **escalation the bot filed** (it handed a job back instead of
finishing), a **red row in the business Odoo's Bot Activity log**, or an **operator report** that
a run did the wrong thing.

1. **Read the run, don't guess.** Pull the evidence for that bot (all record-rule-scoped to your
   own bots): the escalation/handback text, `traces --ref <bot>` (per-turn, tool-by-tool),
   `logs --ref <bot>`, the **Author Logs portal**, and — for a browser bot — `browser-diff --ref
   <bot>` (it diffs the bot's real `browser_click` / `browser_type` traces against your manifest and
   **proposes** fixes).
2. **Classify the failure — three kinds, three homes.**
   - **Selector drift** (the portal moved: a field missed / the wrong control filled) → fix the
     selector map + its manifest twin, **back-port the change to your stub** so a scenario can
     pin it, re-run `selector-audit`.
   - **Behavior** (the model reasoned wrong: fabricated, skipped a check, mis-ordered) → fix the
     **skill prose/rules** (tighten the checklist, add a negative guardrail; do not "coax" a weak
     model — raise the tier instead, per the authoring standard's model-tier rule).
   - **Platform** (the harness / adapter / a mounted tool itself misbehaved) → **not** a Talent
     fix; report it to the platform maintainer, never patch around it in the Talent.
3. **Pin it before you fix it.** **Every live-caught failure class gets a new pinning red
   scenario** (`tests/scenarios/*.yaml`) that reproduces it and asserts the *safe* outcome — the
   service did **not** advance and no false proof was written. This is the rule, not a nicety: a
   fix without a pinning scenario re-opens the same hole on the next change.
4. **Ship it like code.** Bump the Talent `version` + a changelog line citing the incident,
   `lint-talent`, run the clone green (**incl. the new red scenario**), re-tag. Improvement ships
   **repo → lint → delivery** — the delivered tree is read-only.

**Who owns it.** The **Talent author** (author #1 under the owner's account) owns the repair.
When no author is on retainer, the **operator opens a repair ticket to the author and the bot
stays in attended mode** (approval gate ON — see the graduation ladder in
[`business-bot-pattern.md`](../talent-authoring-standard/references/business-bot-pattern.md) §4f)
until a fix ships. A business *user* never edits the Talent — they **report**; the author
**repairs**.

## Verify your bot's mounted tools (the contract is in the docs, not the box)

The **authoring contract** for every platform tool — parameters, result shape, error
modes, a worked example — is the generated
[`tools-reference.md`](../talent-authoring-standard/references/tools-reference.md)
(+ its machine twin `tools-contracts.json`). Author against **that**; never
reverse-engineer a tool from a live box — the runtime carries the *same* text, so
what you write and what your bot experiences cannot diverge.

The box lanes below are for **verification**, not discovery (remember the
chicken-and-egg: a scope-locked bot mounts only what your profile already
declares — deciding *what* to declare needs the catalog + reference first):

- **Quick check after commissioning:** ask your dev bot, in its channel, *"list
  your available tools and their parameter schemas."* The reply is the mounted
  surface — if a tool you declared is missing, your `toolset_contribution` /
  `tools.required` (or the delivery) is the bug, not your skill.
- **One live call beats a guess:** before writing a long skill around a tool, run
  one real call on your dev bot (e.g. a `browser_type` then a snapshot against your
  own stub page) and read the result shape with your own eyes.

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
Use shell for Talent DBs, config, logs, and forensics. **Do not** scrape `state.db` for form
selectors after an observe walk — that is conversation/tool history, not structured
`browser-diff` input. Selector tuning reads account-key `oteny traces` (`browser_traces` /
`page_snapshot` / `form_inventory`) instead.

**The contract you must honor:**
- The window is **TTL-bounded and auto-reaped**. On expiry or when you `close_box_access(request_id=<id>)`,
  the platform kills the tunnel, removes your key, and **rotates the box's model key** (you saw the
  `.env` — it's treated disclosed). Don't leave a window open; close it when you're done.
- Every open is an **append-only audit row** on your account.
- **Prod etiquette:** a shell on a real customer's prod bot is snapshot-first (reversible) but it's
  their live bot — check no dispatch is mid-run before you mutate state, and prefer `inspect` unless
  you genuinely need to change something.

`close_box_access(request_id=<id>)` tears a shell down early (don't wait for the TTL).
The CLI verb does that for you, then polls until the request is **terminal**. Close only
flags expiry — the row stays `active` until the drain reaps it, and that reap **restarts
the gateway** (the disclosed model key is rotated). A second `oteny shell --cmd` that
starts before that reap finishes races `runsc exec` on the bouncing box and used to
raise `ended before active: ProcessError … exit status 128`.

The verb retries a *terminal* 128 inside `packages/oteny` (`AuthorBoxAccess.shell`).
It does **not** open a second window while the first is still queued — that fills the
account inflight cap and every later open 429s. A 429 waits one drain tick (~60 s)
and retries `_open` only. Do not add a retry loop in a caller script.

**Two costs to plan around, because the retry hides neither.** First, **every close restarts
the gateway**, since the model key you saw is treated as disclosed and gets rotated. So a
string of one-off `oteny shell --cmd` calls pays that restart each time — budget roughly three
minutes per call, and prefer one `--cmd` that does the whole job, or one window you keep open
and run several commands in. Second, **an abandoned window still counts against you.** If you
Ctrl-C out without closing, the row stays inflight against the account cap (three by default)
until its TTL expires or the drain reaps it, and every later open 429s in the meantime. If the
CLI retries and still never gets a window, the failure is usually a node-hop `TimeoutError`.
That is a platform-side outage: the retry is correct but cannot fix it, so stop and report it
rather than looping.

## The readiness contract: `active` is not enough — wait for `talent_delivered`

When you commission a fresh dev bot (`request_dev_bot`), poll `dev_bot_request_status` and treat a
bot as **e2e-ready only when `state == "active"` AND `talent_delivered == true`**. `active` alone
means the box booted (on defaults). The git pull can still be running — that is the empty-tree
race. `talent_delivered` is the true "your Talent is on the box" signal (a catalog-only bot is
`true` by construction). On `active` without delivery, the async belt still converges it within
~5 min — poll `hh.talent.source.last_status == "delivered"` (visible to your account key) before
you start testing, or read `hh.talent.source.last_error` / `talent_delivery_error` for the reason.
Why pull-not-push: [`how-delivery-works.md`](references/how-delivery-works.md).

**`last_status=gate_failed` — read the lint text.** Delivery runs the same
`talent-authoring-standard` lint that you should run offline first. A frequent fail is a child
`SKILL.md` **body over 20 000 characters** (`… chars (>20000) — split detail into references/`).
Trim → push → `reload` (or wait for the follow-mode belt). Do not start graded `test` until
`last_status` is `delivered`.

## Proving a migration (the case a fresh box can't cover)

Ship the migration the normal way (append a `migrations.yaml` entry + a
`tests/scenarios/<x>.yaml` with `requires_migration: <id>`), then:

1. `oteny clone --source <a real prior-shape bot ref>` — captures real old state + its
   `migrations.json` ledger (this is what makes the forward migration actually fire).
2. `reload --ref <clone>` your branch — `preflight` now surfaces `MIGRATIONS: pending`.
3. `migrate-talent --ref <clone> --bundle <slug>` (drives `migrate.py` on the box; or let
   the agent drive the checklist turns).
4. `test --ref <clone> --bundle <slug>` — the `requires_migration` scenario flips
   from `skip` to `pass`, and prior rows are preserved. **Pass = no regression on
   real state.**

## The rules the loop enforces (don't fight them)

- **`active` is not enough.** Wait for `talent_delivered` / `last_status=delivered`
  before you test. The box can boot on defaults while the git pull is still running.
  See [The readiness contract](#the-readiness-contract-active-is-not-enough--wait-for-talent_delivered)
  and [`how-delivery-works.md`](references/how-delivery-works.md).
- **What you can and can't see.** You diagnose your own bots — everything below is record-rule-scoped
  to your own (and granted/demo) bots — from three windows: **`traces`** (per-turn tool calls, the
  bot's LLM calls, and the session's **diagnostic events** — crashes/restarts, fail-close and browser
  blocks), the **Author Logs portal**, and the source **`last_status` / `delivered_at`** (the
  delivery outcome + timing). What you **cannot** see is the box's **effective config or filesystem** —
  the delivered `.env`, the on-disk talents tree, the node record are operator-only (a `403`).
  Diagnose box-config from **behavior** (a fail-close, the wrong host fenced, a stub not taking) in
  `traces`, not by reading the box.
- **Neutralize is default-ON.** Every clone runs the bundle's `neutralize.yaml`
  *before it serves a turn* (outbound crons off, connections repointed to staging,
  external logins swapped). If your Talent has any outbound action it **must** ship
  a `neutralize.yaml` (the lint enforces it). `--no-neutralize` is ops-only and only
  on a bot you own.
- **Redaction is automatic.** A clone of someone else's (granted/demo) state lands
  with third-party secrets stripped and the bot token / model key replaced. You can
  never extract another tenant's credentials through a clone.
- **You can clone only what you may.** `oteny clone --source` is record-rule-scoped to your
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

- **Empty Talent tree after `active`, or `reload` does nothing.** You tested before
  delivery finished, or the commit was never pushed. Wait for `last_status=delivered`.
  Unpushed files never reach the bot. Push, then `oteny reload --ref`. An empty
  `auth_handle` on a deploy-key source is normal — not a missing credential. See
  [`how-delivery-works.md`](references/how-delivery-works.md).
- **`last_error` is `fatal: could not read Username for 'https://github.com'`.** The
  source URL is HTTPS and Oteny pulls with a deploy key (SSH only). The platform
  rewrites HTTPS → SSH at clone time. Retry `oteny reload --ref`. If a private repo
  **you** own has never had Oteny's Deploy Key added, that extra step is still required.
- **`test` red, reply matcher failed** — read `traces --ref <clone>` for that turn: the reply
  is graded on `contains`/`not_contains`/`regex`; a genuine refusal or a differently-phrased
  success both show there. Loosen a brittle `contains` to a trace/`uplink` assertion (the
  behavioral truth) rather than pinning exact wording.
- **`test` red, trace marker missing/unexpected** — the tool you expected didn't run (or a
  forbidden one did). `logs --ref <clone>` shows `tool <name> completed`; a missing
  toolset means the platform lock or a `check_fn` gate dropped it (a business bot mounts only
  its `toolset_contribution`).
- **A browser click "succeeds" but the verify snapshot never changes (a radio stays
  unchecked, an option stays unpicked)** — the target was probably **outside the viewport**.
  The AX snapshot is viewport-independent, so a clipped control looks identical to a visible
  one, and an executor that clicks at coordinates without scrolling reports success on a
  no-op (this halted a real filing on a form's last radio group, 2026-08-25 — the platform
  now pre-scrolls every ref-click, but the corrective is executor-independent). Teach the
  Talent: scroll the control into view, **click AGAIN, then verify** — a scroll alone
  changes nothing. The last fields of a long form are the usual victims, because the fill
  pass auto-scrolls everything above them into view and leaves the bottom few clipped.
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
    403 on a *reference* model behind it. Grant your bot's odoo user read on **that** model;
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
- **Discuss mute / Hand-to-Barney gets no reply; `traces` → `uplink_status: auth_failed`** — the
  box's ERP uplink key was revoked (mint always rotates). Re-run the business-bot provisioner for
  that tier (it probes `/json/2/` with the fresh mint and binds the Discuss channel to the current
  ref). Author Logs shows the same status. **Website login** (`/get-started/web` / `/app`) is
  **not** the debug path for this class — that lane is consumer onboarding.
- **No reply at all — not even the "starting" line — while `traces` says `uplink_status: ok`.**
  The box's gateway process is dead or frozen. This is a different fault from `auth_failed`
  above and from a hung turn below, and it needs the opposite action. A frozen event loop keeps
  the service unit up, so nothing about the box *looks* wrong. **Your `uplink_status` will not
  name it** — the author CLI derives only `auth_failed` / `unreachable` / `ok` / `unknown`. Read
  the `diagnostics` rows in the same `traces` DTO instead: a `health_alert` whose summary says
  the gateway is not alive is the tell. The platform raises it when the box stops writing its
  log for 90 s while the unit is still active. **Retrying is the one thing that cannot work
  here**, because a re-dispatch posts into a process that consumes nothing — you need a
  liveness signal, not another attempt. Recover with `oteny reload --ref <ref>`; the converge
  restarts the gateway.
- **The bot narrated a few steps, then went silent for the rest of the run.** The model stream
  hung mid-turn and the box is healthy — the opposite of the case above. The platform ends that
  turn for you after **480 s** of silence on the next model call, so you do not wait out the
  gateway watchdog. The run record carries `outcome=error` with `outcome_detail`
  `model stream timed out after 480s`, and a workflow-driven record is handed back through its
  timeout exit instead of sitting claimed until the owner's SLA reaper fires. Read that detail
  as a platform belt firing, **not** as your Talent refusing: the trace up to the last tool
  result is real work, and a re-run is the right next step.
- **`hand_off matched N records` (N≠1)** — the fixture is absent or duplicated; seed exactly
  one matching record in the *from* state (reset a consumed one) before the run.
- **A `hand_off` claims the record, the bot never runs, and it sits in the working state forever
  (local rig)** — the platform's re-dispatch belt and SLA reaper are **scheduled actions on the
  business Odoo**, so a local Odoo booted **without a cron worker** (`--max-cron-threads 0`, common
  in a debug launch profile) runs **neither**. The dispatch itself is inline, so the happy path looks
  healthy and only *recovery* is dead — the tell is a record claimed (sitting in the bot's working
  state) with no run and no re-post. Boot the Odoo you point a bot at with cron threads **enabled**.
  See [`business-bot-pattern.md`](../talent-authoring-standard/references/business-bot-pattern.md)
  "The timeout reaper — the owner's backstop".
- **Clone won't serve / `neutralize_status: failed`** — the fail-closed gate refused (a connection
  still points at prod, or a required stub is missing). Fix `neutralize.yaml`; a clone never
  serves un-neutralized.
- **A long run is reaped mid-task** — the agent budget (`agent.max_turns`) is too low for the
  Talent's work; raise it per-tenant (an operator `config_overrides` knob) and re-run.
- **Your keep-alive says the bot is gone, but the bot still answers.** A long-lived dev bot is
  usually held by an opt-in **`dev_slot`**, and a keep-alive job touches it by that slot rather
  than by `ref`, so a rebuild does not break the job. **A current rebuild keeps the slot.** When
  `ensure()` (`skills/_shared/scripts/dev_bot.py`) finds a failed reuse target, it re-issues the
  create with `force_create=True` and `dev_slot` intact. The platform then skips reuse, retires
  the slot's old holder, and stamps the slot on the replacement. So the keep-alive follows the
  rebuild.

  **The failure this replaced still bites on an Oteny that predates `force_create`.** There the
  rebuild had to drop `dev_slot` to force the reuse miss, so the replacement carried no slot at
  all and the slot stayed on the destroyed predecessor. Touching by slot then returned
  `not_found` forever, even though the new bot was healthy — and because nothing touched it, the
  idle TTL reaped it a day later. `ensure()` degrades to exactly that behaviour when the platform
  rejects `force_create`, and it logs `predates force_create` when it does. Watch for that line.

  Either way, read a slot `not_found` as **"prove it"**, never as "the bot is dead": list your own
  non-destroyed dev bots first. A live row with a blank `dev_slot` is this case. Re-provision so
  the slot is stamped again, then re-run the keep-alive and confirm it reports the new `ref`. The
  same reasoning applies to any tooling you key on `dev_slot` — a slot is only as durable as the
  last create that carried it.
- **`clone`/`test`/`traces` says "not permitted"** — you can only touch your own + granted +
  Oteny demo bots; `oteny clone --source` naming a source outside that scope is refused by the record rules.
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
your Talent honest and your reputation rises in the Talent Market.

## Verification checklist

1. `oteny lint <bundle>` exits 0 (no violations).
2. A clone stands up neutralized (`neutralize_status: ok`) and the source stays up.
3. `test` is green over every `tests/scenarios/*.yaml`.
4. A migration scenario reconciles real prior-shape state idempotently.
5. `traces` shows the expected tool calls and no approval stall / unbounded loop.
6. The release tag's semver equals the committed `version:`.

## References

- [`how-delivery-works.md`](references/how-delivery-works.md) — you push; Oteny pulls; `active` is not enough.
