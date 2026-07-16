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
  secure browser (`browser` + `browser_request_human` + `browser_download` +
  `browser_fill_form`) for portal filing; optionally a mailbox reader for an inbox
  round-trip; optionally a knowledge lookup; plus `send_message` / `memory` / `todo` as
  the job needs. Which tools exist and how to request them:
  [`tools-catalog.md`](tools-catalog.md); the exact call contracts (parameters, result
  shapes, worked examples): [`tools-reference.md`](tools-reference.md); the
  browser-driving discipline: [`browser-authoring.md`](browser-authoring.md). A complete
  runnable instance of this whole pattern: the
  [`oteny-permit-filer-demo`](../../oteny-permit-filer-demo/README.md) bundle.

The discipline is **list the minimum and stop** — "I'll add `terminal` just in case" is the
exact anti-pattern. Every tool you *don't* request is attack surface a hijacked or
prompt-injected bot has no way to reach.

**Trim the tools *inside* a toolset you don't need — `toolset_tool_exclusions`.** A toolset is
whole-toolset granular: requesting `browser` mounts *every* native browser tool, and a scoped
job rarely uses all of them — a filing bot never needs `browser_console` (raw JS eval; the
platform blocks form-value reads through it anyway, so every call is dead) or `browser_vision`
(screenshots — once `browser_fill_form`'s readback and `page_digest` give you the page state,
vision is never needed). Every extra tool the model can *see* is one it will occasionally
*probe* — wasted turns and wall-clock, and it hits weak/cheap tiers hardest. Declare the tools
your job never uses under `toolset_tool_exclusions:` in `agent-profile.yaml` (a flat list of
individual tool names); the platform drops them from the model's **visible** set at converge —
they never reach the tool list, so the model can't spend a turn on them. It's a cost/quality
trim, not a safety control: the scope-lock (above) is the safety boundary; this just keeps the
mounted toolset as tight as the job.

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

*Requesting `memory` is still fine* — a scoped bot may remember conversational context
(who the operator is, what was said) for continuity. The rule is about **dependence**:
nothing load-bearing (a workflow state, a filing outcome, an idempotency fact) may live
only in memory — the system of record (§3) is the truth, and the bot must behave
correctly on a box where memory came back empty.

## 2b. Your scope contract is adversarially gated — keep it coherent (D95)

Your `agent-profile.yaml` **is** the scope contract, and Oteny runs a **D95 adversarial probe
suite** against it on top of the authoring lint — a second pass with two halves you should author
for:

- **A static coherence check at delivery** (no box, always on): it *fails delivery* if your
  contract has a structural hole an attacker walks through. Keep it coherent:
  - if you declare `portal.real_url`, its host **must** be covered by `portal.fence_hosts` (else a
    non-prod bot could reach the live portal);
  - a locked bot **must** declare a `routing.signature` and a non-empty `routing.channel_prompt`
    (the scope anchor the guard holds to);
  - if you declare a data seam (§3), **do not also mount a generic shell/code toolset** — the seam
    is your system-of-record path, so drop `terminal`/`execute_code` (a demo with a local sqlite
    and *no* seam is the only place a bare `terminal` is allowed).
- **A live red-team** (`red-team` verb, run against a clone): the platform generates an adversarial
  corpus **from your contract** — instruction-override, jailbreak/persona, obfuscated evasion,
  indirect injection (a payload planted in data you read), shell/code execution, off-task tool use,
  credential solicitation, prompt-leak, open-domain drift, memory poisoning, real-portal breakout,
  credential-in-chat, fabrication, bulk exfiltration, off-job reads, destructive writes, and
  forged-authority — and grades whether your bot **refused** each (a deterministic floor + an
  LLM-judged refusal rate, composed fail-closed). Everything in §4b (fail closed, never fabricate)
  and §2 (mount the minimum) is exactly what makes these probes pass. The bar for a verified Talent:
  100% refusal, zero leaks, zero out-of-scope tool calls, zero scope violations.

You don't author the probes — they are generated from what you declare — but a tight, honest
contract (minimal toolset, a fenced portal, least-privilege grants, a fail-closed playbook) is what
turns them green.

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

**The concrete YAML** (the whole data-plane declaration in `agent-profile.yaml`). The
uplink client mounts as the tool named **`crewradar_json2`** — a platform tool whose
name predates its generalization; despite the prefix it is the *generic* Odoo
`/json/2/` client for **your** Odoo, taking `(model, method, kwargs)`. **The name is
pinned deliberately** (it sits in schemas, locks, and shipped Talents): write your
skill text as "the business-Odoo uplink tool" and use the literal `crewradar_json2`
in tool lists and calls. If a generic alias ever ships it will arrive with a
deprecation window and both names working — you need no defensive action now.
Declare it in both lists:

```yaml
toolset_contribution:
  - crewradar_json2          # the Odoo /json/2/ uplink client (the data plane)
tools:
  required:
    - crewradar_json2
seam:
  kind: odoo_json2
  uplink_user: yourbot.serviceuser   # the bot's OWN least-privilege login in your Odoo
  odoo_grants:                       # exactly what the job touches — nothing else
    read:  [your.workflow.model, res.partner, your.credential.model]
    write: [your.workflow.model, your.credential.model]
```

The platform binds the uplink URL/database/key onto the box at commission (the key is
delivered as a secret, never baked). Declaring `seam:` is also what makes
`neutralize.yaml` mandatory — a clone of a bot with a real uplink must be defanged
before it serves.

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
  out, a read returns 403, **or the adapter session dies mid-action** (a cloud browser
  hitting its hard session lifetime, a dropped connection, a killed sandbox), the action
  **did not happen**: write nothing, advance nothing, take the **escalate** transition to a
  human, and say why. **A session that dies mid-action is the same "it did not happen" case
  as one that was never reachable** — and a partial write-ahead marker the run may have left
  behind (a placeholder / `PENDING`-prefixed crash-fence row, armed before the action) is
  **not** proof, so the escalate path must stay open even with that marker present. A 403 is
  a STOP — never a method-name-guessing loop. Give the skill the **exact escalate call** (the
  same advance method through the escalate transition) — a model told to "escalate" without
  the mechanics will invent method names hunting for one.
- **The server refuses an unproven "done" (the claim guard).** Don't only trust the
  Talent's discipline: the workflow's single advance choke point exposes a guard hook, and
  the domain layer refuses the success transition unless the **proof record actually
  exists** (e.g. a captured, non-placeholder filing number on the credential). A run that
  skips the proof — on *any* model — is refused server-side, stays in-progress, and the
  timeout reaper hands it to a human. Escalation is **never** blocked by the guard: a stuck
  run must always be able to reach a person.

Grade both with **adversarial red scenarios** (below): induce the failure — portal down, a
revoked grant, **or the adapter session dying mid-action** (converge the bot with a 1–2-min
browser session lifetime so a cloud-browser session expires mid-fill) — and assert the
*negative* ground truth: the record did NOT advance, no real (non-placeholder) proof exists,
the reply escalates and never claims success. Name each such scenario `<failure>_no_fabricate`
(e.g. `portal_down_no_fabricate`, `cdp_death_no_fabricate`) so the fail-closed suite is
legible at a glance; each is its own **mutually-exclusive run** — the induced failure (portal
DOWN vs portal-UP-but-browser-UNSTABLE) is set per converge, not per turn, so it gets its own
seeded fixture and its own `test --scenario …` invocation.

## 4c. Your test double is YOUR fixture — self-host and tunnel it (the dog-food rule)

A subtle ownership failure is putting the stub double (§4) on the *platform's* infrastructure.
Negate it: a business-bot author is **not** on the platform team, yet must be able to build, run,
and change their own double with only their repo + a laptop. So the double **and** the real
system's identity are **yours, in your repo**; the platform provides only the generic wiring.

- **The double is a fixture in your repo** — ideally **dependency-free** (any stdlib HTTP server)
  and shaped like the real system (its form fields, its confirmation format). You run it locally and
  expose it at a public URL with a **dev tunnel**; the platform points a non-prod bot's tool at that
  URL through a **generic tier knob** (an env var), never at a platform-hosted service. The platform
  hosts no double of yours.
  - **Make the double die with your dev session — otherwise it orphans and blocks the next run.** A
    stub server bound to a fixed port is a footgun the moment your terminal or IDE goes away without
    tearing it down: the process survives, keeps holding the port, and your next launch dies on
    `OSError: [Errno 48] Address already in use`. A launcher's own `atexit`/signal cleanup is **not
    enough** — it never runs when the IDE **force-stops** (SIGKILL) the launcher. The robust,
    launch-method-independent fix lives **in the double itself**: a tiny daemon thread that watches its
    parent and self-terminates when the parent dies (on macOS/Linux an orphaned process reparents to
    init, so a *changed* `os.getppid()` is the portable "my launcher went away" signal — it fires even
    on a parent SIGKILL). Barney's stub meldloket does exactly this (on by default). Build your double
    the same way, or your dog-food loop leaks a port-holder every hard stop.
  - **Use a NAMED tunnel, not a quick one — this is a footgun for a long-running bot.** A cloudflared
    *quick* tunnel (`cloudflared tunnel --url …`, a `trycloudflare.com` host) is best-effort: it drops
    under a multi-minute run and, fatally, **a reconnect hands out a brand-NEW hostname** — so your
    bot's uplink/portal, pinned to the old host, breaks mid-run and the record orphans. A **named
    tunnel** keeps the **same** hostname across reconnects (and runs several edge connections), so the
    bot survives a blink. Both the bot's Odoo uplink and your stub double should ride named tunnels for
    any dispatched/long-running work. (Barney's launcher provisions them automatically when you have
    Cloudflare API secrets; **without them it auto-falls back** to a free quick tunnel — no paid token
    required for short dev runs.)
  - **A named tunnel on a proxied zone applies Cloudflare's bot protection — the platform handles the
    common case.** A named tunnel on your own Cloudflare zone (e.g. `*.example.bot`) is *proxied*, so
    Cloudflare's **Browser Integrity Check** runs on it and bans a plain HTTP client outright — the
    bot's reply reads `could not reach the … uplink … HTTPError 403: error code: 1010`. The platform's
    uplink client already sends a **browser-like `User-Agent`**, which passes that check, so a proxied
    named tunnel works out of the box. If you still see 1010 (or a `1020`), your zone has the stronger
    **Bot Fight Mode** (it fingerprints TLS/JA3, not just the UA) — add a WAF/Bot-Fight-Mode **skip
    rule** for your dev hostname, or point the uplink at a quick (`trycloudflare.com`, off-zone) tunnel,
    which has no such rule. A quick `curl --resolve … → 200` confirms the tunnel itself is fine and the
    block is Cloudflare's, not yours.
- **You declare your external systems in the Talent; the platform binds each by tier.** Every
  outside-world system the bot touches is **named in the agent profile** — `external_systems:` is a
  list of `{name, env_var, real_url, fence_hosts}`, and `portal:` is sugar for a single system bound
  to a default env var. The concrete YAML:

  ```yaml
  portal:                              # sugar: ONE system on the default env var
    real_url: https://portal.example.gov     # what a PROD bot gets
    fence_hosts: [portal.example.gov]        # what a NON-prod browser is blocked from
  # …or, for several systems, the general form:
  external_systems:
    - name: mailbox
      env_var: OTENY_MAILBOX_BASE_URL        # a non-reserved OTENY_* name you pick
      real_url: https://mail.example.com
      fence_hosts: [mail.example.com]
  ```

  For each, the platform binds **one** URL by the uplink tier — **prod → the
  Talent-declared `real_url`; any non-prod tier → the stub** — and exposes it to the bot's tool as
  `<env_var>=<base>`; on a non-prod tier it also fences the browser off the **union** of every
  declared `fence_hosts`. The platform *binds/fences whatever you named* and hard-codes no third
  party's address, so it stays generic across every client's bot. **The prod identity (`real_url` +
  `fence_hosts`) lives in your Talent** and is versioned with it; the throwaway stub value does not
  (next bullet).

  **`$OTENY_*` is a tool-target convention, not a template language.** Writing
  `$OTENY_PORTAL_BASE_URL` in skill prose works where the bot **resolves it to make a call**
  (`browser_navigate` to `$OTENY_PORTAL_BASE_URL/portal`) — that is the intended usage, and the demo
  bundle models it. Nothing interpolates it in a **human-facing** message: a reply or escalation
  telling an operator to "check `$OTENY_PORTAL_BASE_URL`" ships the literal token to a person who
  cannot resolve it. In any text a human reads, instruct the bot to write the **resolved value**.
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

## 4d. Make the double faithful — harvest the operator's walkthrough (page graph, not flat form)

A flat "all the fields on one page" double proves plumbing, not the filing. Your bot's skill text
and the double **co-evolve against the real system**, and the cheapest source of truth is the
**human operator who does the task today**: ask them for a click-by-click walkthrough of ONE real
run — a screenshot per screen plus a sentence of what they click next. Then:

1. **Transcribe exhaustively before you build.** For every screenshot capture the exact field
   labels (in the system's language, with diacritics), each control's type (text / select / radio /
   checkbox / date), what is **pre-filled vs typed vs carried over**, required markers, and the
   warnings. The transcription — not your memory of "roughly what the form wants" — is what the
   double and the skill are written against.
2. **Cross-check every constant against your data plane.** Expect to find real bugs: transposed
   digits in a constant your docs have carried for weeks, a label that is close-but-wrong, an
   "always X" that is actually per-record (Barney: a one-digit VAT transposition; an SBI code that
   depends on the vessel; a start date that is *always entered one day early*; an "optional" field
   the docs marked required). **Business rules discovered this way go into the DTO** (computed,
   deterministic — the skill says "type `periode_van` verbatim"), never into prose the model must
   re-derive per run.
3. **Rebuild the double as the real page graph.** Replicate the wizard's page ORDER, its step
   rail, the lookup interludes (search → result row → select), values that **carry over** between
   pages, blocking confirmations (a modal, a required "I agree" checkbox — make submitting without
   it re-render with an error, so the agent can recover), and interaction quirks (a filter checkbox
   that must be unchecked before the needed option exists). The test of fidelity: **the same skill
   text drives the double and the real system with zero branching.**
4. **Mark what you haven't seen.** Screens the walkthrough skipped stay in the double as
   best-effort with an explicit *unverified* note, and your field map keeps an "open unknowns" list
   you burn down with the operator. Re-harvest whenever the real system changes (your skill's
   portal-change detection is what catches that).

*Worked example (Barney):* Kirsten's 24-screenshot walkthrough of one real meldloket filing was
transcribed screen-by-screen, cross-checked against CrewRadar (surfacing the VAT transposition, a
per-ship SBI rule, the −1-day/+1-year date convention, and an optional-BSN the DTO wrongly
required), and the double was rebuilt from a single form into the real 8-step wizard with two
register-lookup interludes, date carry-over, and the consent gate.

## 4e. Resilient selectors + the selector manifest (audit before, diff after)

**Two layers — keep them apart.** A browser Talent is authored in **two** layers, and conflating
them is the trap that turns a high-level work instruction into a brittle screen-scraping script:

1. **The work instruction** — the SKILL.md prose: the workflow, which DTO field fills which
   logical field, the escalation and fail-closed rules. It is **employee-style and
   selector-free** — you tell the bot *what* to do the way you'd brief a new hire, never *which
   CSS id* to click. **This is your IP** and it stays high-level; a site redesign does **not**
   touch it.
2. **The page runbook** — the selector map (`references/form-selectors.md`) + its machine twin
   (the expected-selector manifest below). Treat it as a **generated, disposable artifact**, not
   work-instruction content: **harvest** it once at authoring time from the real page's devtools
   (or your faithful stub), **converge** it against reality by observe → `browser-diff` proposals
   → author accepts, and **regression-net** it by back-porting each fix to the stub. When the
   portal is redesigned you **regenerate the runbook** — you never rewrite the instruction.

That split is the reconciliation of "a Talent is a high-level work instruction" with the hard
platform fact that the model **cannot read CSS selectors off a live page** (`browser_snapshot`
exposes accessibility refs, never ids — see [`browser-authoring.md`](browser-authoring.md)): the
selectors have to ship *somewhere*, so they ship as a **compiled artifact beside** the
instruction, not woven **into** it. The rest of this section is how you build and maintain that
artifact.

Your dev stub (§4c) has clean, stable ids you chose; the **real third-party site does not** — its
ids are framework-generated, its custom widgets aren't native controls, and a re-skin renames both
without warning. A skill whose `browser_fill_form` selectors were written against the stub's tidy
`#first_name` drives the stub perfectly and then **misses on the real page**, mid-filing, where a
miss is a stalled job (or worse, the wrong field filled). So author every selector as a **resilience
ladder**, not a single guess, and verify it twice — **statically before** a run, and **against the
real page after** one. Two generic CLI verbs do this from an author-supplied **expected-selector
manifest**.

### The resilient-selector pattern (why the format has a fallback ladder)

- **A fallback ladder, most-durable rung last: `id → name → label-for → role+accessible-name →
  text`.** The tool tries the rungs in order. Early rungs are precise but fragile (an id or a `name`
  a re-skin renames); the late rungs are **semantic anchors** — *role + accessible name* (what the
  control IS + what its label reads), a `<label for>` association, or visible text. The semantic
  anchor is the rung a real site is **least** likely to change: a "Continue" button stays a button
  named "Continue" across a re-skin that renumbers every id. A bare `#id` / `[name=…]` / `.class`
  with **no** ladder is **brittle**; a ladder that never reaches a semantic anchor is **risky** (id
  *and* name can both move on a re-skin). **Resilient** = a ladder that bottoms out on a semantic
  anchor, or a semantic-first primary.
- **Lead the ladder with the LABEL when a real third-party site is your target.** The order above
  is the general shape; a *third-party* site adds a catch — its `id`s and `name`s are **not yours**.
  You invented the tidy ones on your stub (§4c), but the real page's are framework-generated and
  different, so an id-first ladder spends its *first* attempt on a rung that can't match reality. The
  one thing that reliably tracks the real site is the control's **visible label / accessible name** —
  the words the operator actually sees. So for any field whose primary selector is a stub-invented
  id, **promote the semantic rung to the front** (`label=` / `role+accessible-name` first, the
  id/name kept only as later best-effort rungs), so the first attempt is built on what the real page
  shows. Label-first is the resilient default whenever the bot's live target is a site whose ids you
  don't control.
- **Assert exactly one submit.** A page with more than one submit control — a *Back* beside a
  *Next*, or a "Save draft" beside "Submit" — turns a generic `button[type=submit]` into a coin
  flip. Either set `expect_unique: true` (the audit fails the page if it has ≠1 submit control) or
  pin the button by its text. This **generalizes the §6 submit-line rule** (ship an explicit per-page
  submit selector the model copies verbatim); here the audit *proves* that line is unambiguous before
  you spend a live run on it.
- **An exact option string is brittle.** A `select`/radio pinned to one exact option
  (`option: "Yes, permanent"`) breaks the moment the site changes wording or casing. Declare
  `option_fallbacks` (alternate spellings, casings, **and spacing**) — which also clears
  `selector-audit`'s **risky** grade for that exact-option field — and where the control exposes a
  stable value, prefer matching by value over display text.
- **Quote an attribute value that contains a comma or a space.** Targeting a radio/checkbox by its
  option text — `input[name=agree][value=Yes, I consent]` — is, **unquoted**, an invalid CSS selector:
  the comma is a selector-list separator, so `querySelectorAll` throws a SyntaxError and the step is a
  **guaranteed 0-match miss** (benign only if the field is already at that value; otherwise the
  verified-submit gate fail-closes and the page **stalls**). Write it quoted:
  `input[name=agree][value="Yes, I consent"]`. The platform's `browser_fill_form` now **auto-quotes**
  an unquoted attr-value selector as a belt (a bare-identifier value like `[value=Yes]` is left
  untouched), but author it quoted so the runbook is correct on its face — the model copies structure,
  not prose. This is the value-targeting analogue of the exact-option-string rule above.

Every rule is the same bet — **the real site's ids and triggers differ from your stub's** — so encode
what won't change (semantics) as the floor, and flag every place a single exact string is load-bearing.

### The expected-selector manifest (the machine-readable contract)

Both verbs parse one author-supplied YAML file — the machine-checkable twin of the in-skill selector
map ([`browser-authoring.md`](browser-authoring.md), "The selector map"). It declares, per wizard
page, the fields you fill and what each should resolve to:

```yaml
version: 1
stub_walk:                                          # optional — lets `manifest-check` walk YOUR stub
  start_path: <path manifest-check opens first>
  id_from_url: <rule to pull a record key out of a stub URL>
pages:
  - page: <stable logical key for the wizard page>
    stub_path: <per-page path template on your stub>   # where manifest-check finds THIS page
    url_contains: <substring of the page URL>      # optional page matcher
    title_contains: <substring of the page title>  # optional page matcher
    submit:                                          # optional
      selector: <primary submit selector>
      expect_unique: true          # assert exactly one submit control on the page
    fields:
      - name: <logical field name>                   # used to match a real control on a miss
        selector: <primary selector>
        kind: fill|select|check|uncheck|click|press
        fallbacks: [<selector>, ...]                 # the resilience LADDER, ordered
        expect: {id: <id>, name: <name>, role: <role>}   # optional — what the resolved element should be
        option: <exact option string>                # select/radio only; flags exact-string brittleness
        option_fallbacks: [<alt>, ...]               # optional
        stub_dynamic: true                           # control appears only AFTER an interaction → UNVERIFIED, not MISSING
```

- `page` is your stable logical key; `url_contains` / `title_contains` bind a manifest page to a real
  page in the trace.
- `name` is the logical field name — when a selector **misses**, the diff uses it to guess which real
  control you meant.
- `expect:` is optional ground truth (id / name / role the selector should resolve to) — so a silent
  *RENAMED* (the field filled, but a **different** control) is caught, not just a total miss.
- `doc_twin:` names your **human-readable** per-page map (the `.md` twin of this manifest). Declare it —
  the authoring lint's **check 17** then asserts the two files list the *same* concrete `#id`/attribute
  field+submit selectors and **FAILs on drift**, so a selector edited in one twin but not the other can
  never ship silently. (Fallback ladders and radio option *values* stay yaml-only by design — the doc
  documents the primary anchor + the ellipsis pattern, not every rung; the check normalizes both out.)
  Omit it and you get only a soft warning that the pair is unguarded.

### The workflow — `selector-audit` BEFORE, `browser-diff` AFTER

The platform captures, server-side and **PII-free**, a per-action trace of every `browser_fill_form`
step your bot runs — the selector it tried, how many elements matched (0 / 1 / N), and the **actual**
element the page rendered (id / name / role / aria-label / text / tag / type) — plus a per-page
inventory of the page's form controls. These are your own bot's real browser interactions on your
**account-key dog-food surface** — no operator access needed.

1. **`hermeshost selector-audit --manifest <file>` — static, before a live run.** Scores each
   selector against the rules above and **exits non-zero if any is brittle** — the "is my runbook
   flexible enough for the real website?" check. Harden what it flags (add ladder rungs down to a
   semantic anchor, add `expect_unique`, add `option_fallbacks`) until it passes. No bot needed —
   run it in CI.
2. **Run the bot** — a scenario or a handed-off job — against the real (or stub) site so it emits
   `browser_fill_form` traces.
3. **`hermeshost browser-diff --manifest <file> [--observed <traces.json> | --ref <ref>]` —
   dynamic, after the run.** Diffs the observed `hh.browser.trace` rows against the manifest and
   **proposes** a verdict + fix per field:
   - **OK** — matched exactly one control, as expected.
   - **RENAMED** — matched, but a different id/name than declared (the site moved it) → adopt the new
     selector.
   - **AMBIGUOUS** — the selector matched **N>1** controls → tighten it.
   - **MISSED** — matched **0** → the control the page actually rendered (found via `name`) suggests
     the real selector.
   - **SUBMIT_NOT_UNIQUE** — the page had ≠1 submit control → set `expect_unique` / pin the submit by
     text.
   - **NOT_EXERCISED** — the run never reached this field/page → your scenario didn't cover it.

   Fixes are **proposed, never auto-applied** — you read them, decide, and edit **your own** skill's
   selector map + manifest. Read the raw rows yourself with `hermeshost traces --ref <ref>` (it
   returns a `browser_traces` list + a `browser_summary`) to tune the runbook by hand.

**`hermeshost manifest-check --manifest <file> --stub-url <base>` — the third verb: is my double
faithful to my manifest?** `selector-audit` proves the ladders are *flexible* and `browser-diff`
proves they *matched* a page the bot reached — but neither catches a control your manifest **names**
while your **stub never renders** it. That field simply never appears in a trace, so `browser-diff`
files it as **NOT_EXERCISED** (silently green) and the whole offline suite passes while the runbook
and its own double have quietly **drifted apart**. `manifest-check` closes that blind spot: it walks
your stub and asserts every manifest-declared control is actually reachable there — a genuine
false-green catcher you run in CI beside `selector-audit`, no bot and no live run.

- **It walks your stub with zero stub-specific platform code — the routing is in the manifest.** The
  manifest carries a **`stub_walk`** block (a `start_path` to open first and an `id_from_url` rule to
  pull a record key out of a URL) plus a per-page **`stub_path`** template, so the generic verb knows
  how to visit each page of *your* stub without the platform hard-coding anything about it.
- **A control that only appears after an interaction is UNVERIFIED, never a false MISSING.** A field
  the stub renders only *after* a step — a post-search result link, a summary gated on a seeded row —
  is marked **`stub_dynamic: true`** on that field. `manifest-check` reports it **UNVERIFIED** (a
  static walk can't reach it) instead of a false **MISSING**, so a genuinely static control that
  vanished is still caught while an inherently dynamic one isn't a false alarm.

The loop closes the §4c dog-food gap from the selector side: **audit** hardens the runbook before you
spend a live run, and **diff** turns each real-site mismatch into a concrete fix you apply yourself —
never the platform reaching into your bundle.

**Reading a one-off timeout/miss — don't chase weather.** A single live run that shows a step time out
(matched 1, never actioned) or a `MISSED` is **n=1 evidence**. `browser_fill_form` **auto-waits for
actionability** (a control that renders a second or two late still fills), so a step that fails only
after the *full* per-action timeout usually means a genuinely stuck/slow page in that one run — an
environmental transient — not a broken selector. Before treating it as a bug: check whether the field
is even conditional (read the page, not your assumption), re-run once, and — fastest of all —
**reproduce the page mechanics offline against your own stub** (a real headless browser is enough; no
live infra) before spending a bring-up chasing it. A selector that misses on *every* run is real (the
`browser-diff` verdict tells you which); a selector that misses once is a coin toss until a second run
confirms it.

### Observe mode — reconcile against the real portal before the first side-effect

`selector-audit` and `manifest-check` harden the runbook offline, and a stub run proves it drives
*your double* — but none of that has yet touched the **real** site. Before the bot's **first real
side-effect**, close that last gap with an **observe pass**: arm the submit-deny belt (§4f), hand the
bot a real record, and let it **walk the real portal all the way to — but never through — the
submit**, emitting `browser_fill_form` traces the whole way. Then reconcile, iterating four steps
until the diff is clean:

1. **Observe** — the belt-armed bot walks the real site; the platform captures the per-action traces
   (as above).
2. **Diff** — `hermeshost browser-diff --manifest <file> --observed <traces.json>` scores the observed
   reality against your manifest (RENAMED / AMBIGUOUS / MISSED / …).
3. **Harden** — apply each proposed fix to **your own** selector map + manifest, **and back-port the
   observed reality into your stub** (the real ids, the real option strings, any page the original
   walkthrough missed) so the **offline suite stays the authoritative regression net** — the stub, not
   a live run, is what every future deploy checks against.
4. **Fill-verify** — re-run against the now-faithful stub until the offline suite is green.

Iterate **observe → diff → harden → fill-verify until the diff is clean**, and only *then* disarm the
belt and let the bot perform the **real** side-effect. The submit-deny belt (§4f) is exactly what
makes step 1 safe to run against the live site as many times as convergence needs.

## 4f. Rehearse against the real site — the per-bot submit-deny belt

Converging selectors (§4e) and observing the real workflow (above) are fastest against the **real**
third-party site — its real ids, real widgets, real page graph — but you must reach that page
**without ever performing the real side-effect** (a legal submit, an irreversible "confirm" click).
The obvious move — add a "never click submit" rule to the Talent — is **wrong**: the *same* Talent
files for real in prod, so a Talent-wide submit block would gag the real bot too. The safe mechanism
is a **per-bot submit-deny belt** — a knob on *this one rehearsal bot*, not on the Talent every bot
shares.

- **A commission-time, per-bot knob, empty by default.** Arm it when you spin up a rehearsal clone:
  `commission --submit-deny-patterns <comma,list>` records a `config_overrides["browser.submit_deny"]`
  value on **that** bot, which the box receives as the env var `OTENY_BROWSER_SUBMIT_DENY`. A normal
  bot carries **no** patterns and submits freely; only the bot you armed refuses.
- **The secure browser enforces it structurally.** With the belt armed, `browser_fill_form` refuses
  any **click / check / submit** step whose **selector string** *or* **resolved element text** matches
  one of your patterns, returning a blocked result instead of acting. The **resolved-text leg** is
  what makes it robust: it catches a generic `button[type=submit]` whose *visible label* is the submit
  word, even though the selector itself names no button text. Feed it the site's submit words (in the
  site's language) and the belt fires on the real button however its selector is written.
- **It stacks on top of the softer layers — structural, not a hope.** The belt is a third,
  *structural* line behind the prompt-level "never submit" instruction and the **server-side proof
  guard** (§4b): the prompt is a wish, the proof guard refuses an unproven *done*, and the belt refuses
  the *click itself* at the browser. A rehearsal bot that drifts and tries to submit is stopped at the
  browser, not trusted to obey.
- **Honest residual — the native per-field click.** The belt matches on text, so a *native per-field
  click* tool (one that actions a single element **by reference**, not by a text-bearing selector) is
  caught only **procedurally**: its pre-check sees an element ref, not a label, so the text leg cannot
  fire. Submitting that way therefore takes **deliberate, off-instruction clicks** — the kind a
  watching operator sees in the live trace — not an accidental one. Rehearse with an operator watching
  the run, and treat a per-field click on the submit control as the one gap the belt can't close for
  you.

**Rule:** *arm the belt on the rehearsal bot; leave the Talent's real-submit path intact.* The belt is
how you spend live runs converging selectors (§4e) and reconciling the real workflow (observe mode,
above) without ever filing for real — the same tier-below-the-Talent discipline as the stub doubles
(§4), but for the one bot you deliberately point at the live site.

### The graduation ladder — from rehearsal to unattended prod

A side-effecting bot does **not** go from green tests straight to filing on its own. It climbs a
ladder, and each rung has an objective exit gate — so "is it ready to run unattended?" is a
measured fact, not a judgment call:

- **Stage 0 — stub-green.** The full `tests/scenarios/*.yaml` suite passes on the neutralized clone,
  **including every red (fail-closed) scenario**. Exit: all green.
- **Stage 1 — observe on the real site.** Point the bot at the **real** third-party site with the
  **submit-deny belt armed** (§4f) and run observe passes until `browser-diff` is clean — the
  runbook matches reality, and the belt has stopped any drift-to-submit. Exit: `browser-diff` clean,
  zero belt-caught submit attempts.
- **Stage 2 — attended prod.** The bot files for real, but the **approval-gate workflow state is ON**
  (the attended default — see "The attended approval gate", §6) and an **operator watches** each run.
  Every filing is human-approved before submit.
- **Graduate to unattended.** The exit criteria from attended to unattended, the **ratified default**
  (tune per bot, record the number on the bot): **5 consecutive clean attended filings, including at
  least one rejection/exception path, with zero submit-deny-belt trips and zero server-side
  proof-guard refusals.**

**Who disarms attended mode: the operator, at commission time, recorded on the bot record — never the
author, and never the bot.** The Talent author ships the *capability*; turning off the human gate is a
deliberate operator act on one specific bot, logged, and reversible. A bot can no more graduate itself
than it can rewrite its own Talent.

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

**The driver waits for the bot to go quiet before grading.** A long dispatched run (§6) narrates
an opening line, then works for minutes (a tool line per call, a periodic "still working"
heartbeat), then posts its final reply. So the live driver **debounces**: it grades the newest
non-heartbeat reply only after the channel has been **silent** for a quiet window — any new frame
resets the clock — so a filing is never graded on its opening line nor interrupted mid-run by the
next scenario. The window is sized above the heartbeat idle by default; a chat-only bundle that
wants faster runs can shrink it via `reply_quiet_period_s` in `tests/discuss.yaml`. Practical
consequence for **happy-path** scenarios that trigger a long run: assert on the **final** state
(e.g. "Filed"), and prefer driving one long job as a **single isolated hand-off** rather than
racing several scenarios into the channel at once.

**A side-effecting scenario CONSUMES its fixture — give each scenario its OWN, or reset between
them.** A scenario that files a record, advances its state, or otherwise mutates a business record
leaves that record no longer matchable by the next scenario's `hand_off`. If three scenarios all
`hand_off` "the record for worker X in state *New*", the first one to succeed moves X out of *New*
and the other two either re-consume a half-finished record or fail with "0 records matched — seed/
reset the fixture". So **seed one distinct fixture per side-effecting scenario** (worker X for the
happy path, worker Y for the fail-closed case, …), or add an explicit re-seed/reset step so each
scenario starts from a known clean record. A prod-copy database is NOT a reliable fixture source —
its data is whatever production has, so pin the suite to seeded, named fixtures on a test tier.

**Ship a seed/reset TOOL with your bundle, and make it prove itself.** The fixture rule above only
holds if seeding is one repeatable command, so put an idempotent seeder in your repo (the business-
Odoo side, next to your other operator tools) and have the launcher (§ below) run it: it
find-or-creates one clearly-synthetic, complete fixture per side-effecting scenario (names no real
record could carry — they double as the scenarios' match tokens), **resets** a consumed fixture
(state back to the queue state, side-effect artifacts deleted, any stale claim fence cleared), and
**verifies each fixture with the scenario's EXACT `hand_off` domain** — failing loud on zero or
ambiguous matches instead of half-seeding. Two footguns the verify step exists to catch: your
business system may **auto-create** the workflow record when the fixture's parent is created — the
seeder must detect and **adopt** the auto-created record (a manual create alongside it becomes a
duplicate the `hand_off` trips over; *how* to trigger/observe that auto-create is a data-plane
implementation detail — document it with your seeder). And a seeded fixture ages out of validity
windows (refresh dates on every run). Cover the seeder with an offline framework test (seed →
exact-domain match → idempotent re-run → reset-after-consume) so fixture bugs never cost a live run. Mutually-exclusive scenario
CLASSES (portal-up happy path vs portal-down red probe) still run as separate invocations — select
the class with the repeatable `test … --scenario <name-or-glob>` flag.

**Drive the channel the bot is actually on, not a hard-coded constant.** A dynamically-commissioned
test bot (one a launcher points at your local Odoo) is wired to whatever channel exists on THAT
Odoo, recorded on its tenant record at commission — which a per-tier constant committed in
`tests/discuss.yaml` cannot know (and can't be committed without breaking the other tiers). The
platform driver resolves the bot's real channel from its record and only falls back to the bundle's
`channel_id` for a static fixture; so keep the committed `channel_id` as the staging-fixture default
and let the launcher supply the per-deployment channel — never hard-code your local channel into git.

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

**A launcher that HOLDS the rig must not tear it down on one unverified liveness read.** Once it is
up, the launcher blocks holding its children (the double, the tunnels). Three rules keep that hold
honest:
- **`poll()` is not proof of death — confirm a claimed exit against the process table.**
  `subprocess.Popen.poll()` reports a **live** child as exited whenever something else reaps it
  first: a debugger, an IDE test runner, a shell job-control layer, or any library doing a wildcard
  `waitpid`/`SIGCHLD` reap consumes the child's status; CPython's `waitpid` then raises `ECHILD` and
  `_internal_poll` **assumes the child died**, setting `returncode = 0` (cpython bpo-15756). The
  signature is a rig that holds for minutes from a plain shell and detaches seconds after printing
  its own success banner **under the debugger**. So never act on a bare `poll() is not None`:
  confirm it (`os.kill(pid, 0)` → `ESRCH` = genuinely dead; still present = `poll()` lied) and
  **resolve ambiguity to ALIVE**. Apply it to every liveness read, the startup gates included — a
  false read there kills a rig that came up fine.
- **Never send a held child's output to `DEVNULL`.** A tunnel that dies silently is an
  undiagnosable outage. Give each held component its own log file and print its tail when it dies.
- **Restart a genuinely-dead component in place — but only a NAMED tunnel.** A dead component is not
  a reason to tear the whole rig down. A **named** tunnel's hostname is stable (§4c), so restarting
  it keeps the bot's already-delivered coordinates valid — restart it. A **quick** tunnel's hostname
  **rotates on reconnect**, so restarting one strands the bot on a host it can no longer reach: a
  quick tunnel is deliberately **not** restartable. Bound the restarts (a few, then stop), and when
  you do detach, name the component, its exit code, and its log tail.

*Worked example (Barney):* `point_barney_at_local.py` is the launcher — bare = uplink only,
`--stub-only` = just the meldloket double + tunnel, `--with-stub` = the one-shot e2e (double + tunnel +
uplink + point the bot), `--seed-fixtures` = run the bundle's fixture seeder (`seed_mfnl_fixtures.py`:
one synthetic worker per hand_off scenario, reset-on-rerun, verified against the scenarios' exact
domains); each is a VS Code launch config. Then `hermeshost test --ref <bot> --bundle <bundle>
[--scenario <glob>]…` runs the graded scenarios against the live, side-effect-safe bot.

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

### Choosing the model tier — blast radius, not scenario pass-rate (D235)

The fleet default is *"declare the cheapest tier your scenarios pass on"* — right for a
chat assistant, **wrong for a business bot that acts on the world.** A bot whose failure
mode is an **irreversible external side effect or a consequential false claim** (a filing,
a payment, a submission) defaults to a **builder floor** (`model_tier: builder`), because
the cost of a wrong action dwarfs the model-price delta.

**Why — the measured evidence (D235, from D189/D233).** In a live A/B, the reference
business bot on the cheap (Flash-class `assistant`) tier **invented an identifier, guessed
method names, and mis-advanced a legal filing to a done state**; the *same* Talent on the
`builder` tier escalated cleanly instead of fabricating. The D233 replay grid quantified it:
the honesty/provenance rules were **ineffective on the cheap tier yet decisive on builder**
(cause of a stop stated correctly 60→90%, claims backed by provenance 70→100%). You are
buying honesty and long-horizon compliance, not raw capability.

**The floor is your *only* model lever — per-task escalation does not apply here.** A
locked business bot is structurally escalation-exempt (empty `task-policy.json`,
`switch_persona(task=)` refused), so there is no per-task "upgrade for the risky step" —
the static `model_tier` floor is the whole decision. Get it right.

**Tier and authoring rigor are decoupled — never substitutes.** A stronger model does
**not** buy you scaffolding-free authoring: the checklist / selector-map / submit-belt
architecture in this doc is mandatory on **every** tier. Measured: prose-inferred submit
selectors were obeyed on only **2/12 calls even on builder** — structure buys determinism
no model provides. The inverse is also banned: **do not coax a weak model** with
Flash-specific behavioral prose (exact-call recipes, anti-fabrication paragraphs D233
measured *inert* on the cheap tier). If a behavior needs a stronger model, **raise the
tier** — don't write more prose at the cheap one.

**Downgrading below the floor needs evidence, not a hunch.** To run a side-effecting bot
below builder, prove it: **N consecutive graded greens including every red scenario** on
the target tier, within a declared variance bound, at the **current** Talent version.
Absent that measurement, the builder floor stands.

### Declare the run's turn budget — `agent_max_turns` for a long job

A dispatched turn runs under a **tool-turn budget** — the max number of tool calls the agent
may make before the host cuts it off. The default is tuned for a chat assistant (~90 calls). A
long multi-step job — driving a portal wizard, reconciling a batch, a browser-heavy filing — can
easily exceed that, and the failure is quiet and nasty: the run does almost all of its work, then
**caps mid-finalize** (it took the action but never wrote the proof / advanced the record), which
reads like a stall but is a budget cap (the gateway log shows `api_calls=<max>` at the finalize).

Declare the ceiling **in your `agent-profile.yaml`**, as a sibling of `model_tier`:

```yaml
model_tier: builder       # side-effecting bot → builder floor (see "Choosing the model tier", D235)
agent_max_turns: 200      # this bot's one job is a ~200-call portal filing — raise the ceiling
```

The platform renders it into the box's runtime budget **at commission**, the same way it honors
`model_tier` — so **every** bot built from your Talent gets the right budget, a self-serve **dev**
bot included, with **no per-tenant operator override**. Size it to your job's real worst case (count
the tool calls in a full run and add headroom); omit it and you keep the safe default. This is the
*platform provisioning* knob — separate from any per-transition budget your **workflow** may also
declare on the owner-Odoo side (that governs the dispatch spec; this governs the container). Verify
after a delivery in the gateway log (`Agent budget: max_iterations=<n>`), and prefer **fewer calls**
(batch form-fills, trim mid-run narration) over an ever-larger ceiling — a smaller budget is a
tighter safety bound.

### Batch independent inputs — one fill, one verify per group

The biggest lever on a long browser-driven run is **doing fewer round-trips**, and the finest-grained
trap is treating every field as its own observe-act-verify cycle. Each cycle is a browser round-trip
plus a model call; a thirty-field form becomes sixty serial steps and minutes of wall-clock — enough
to run into the session cap. **Batch the typing, never the thinking:**

- **Use `browser_fill_form` — one call per form page.** Pass `steps=[{selector|label, value}, …]`
  and it fills text inputs, selects native dropdowns, and checks boxes/radios through the real
  browser engine, then **reads every value back** — the per-field `ok`/`actual` in its result *is*
  the group verify, so a whole page costs one round-trip instead of one per field. Pass the page's
  next/continue button as `submit_selector`: it is clicked **only when every field verified**, in
  the same call — so a dynamic page cannot reset a field between your fill and your navigate (the
  classic lost-value loop). Steps run in order — sequence unlock-then-set interactions (a filter
  checkbox that hides options) inside the one call. Ship the page's **selector map in the skill**
  (a `references/` file): the browser snapshot shows accessibility refs and labels, not CSS ids, so
  the skill — not the snapshot — is where selectors come from (`label=` targeting works too).
  **Give each page an explicit `submit_selector` line in that map — a value the model copies
  verbatim — not just prose naming the *Next*/*OK* button.** A model that has to *infer* the submit
  selector from prose passes it on only a fraction of its fill calls (live-measured 2 of 12), losing
  the atomic fill-then-submit and burning a separate navigate turn per page; a per-page map with an
  explicit submit line binds far better than prose because the model copies structure instead of
  interpreting it. For a
  custom widget that is not a native control, use explicit `kind:'click'` steps (trigger, then
  option). If the tool reports *unavailable*, fall back to per-field fills with **one** snapshot
  verify per group.
- **Chain pages off `page_digest` — normally zero snapshots between pages.** A submitted call's
  result carries `page_digest` (headings + labels + buttons of the page you landed on): when it
  shows the expected page (per your shipped map), that IS your portal-change check and your next
  `label=` targets — go straight into the next page's fill call. Budget **at most one snapshot
  per form page**, and spend it only where you must *read values off the page* (a pre-filled
  verify page, a summary check, the confirmation read) or when the digest is missing/ambiguous
  or a field failed verify. Never snapshot to confirm a fill — the readback already did. And
  **narrate at page-count granularity, not per page**: each optional progress line costs a model
  turn; say you started, summarize before the irreversible step, report the outcome.
- **Never batch across a server round-trip** or anything that changes later fields: a search-then-pick
  (type a registration number → the site returns matches → select one), a cascade where each choice
  populates the next, or any control that loads a page the next field depends on. Those stay one action
  at a time — batching them races the site's own response.
- **Keep the page-boundary verify and the pre-commit read.** Batching changes *how many* fields you
  set between checks, never *whether* you check: fix and re-verify any field the readback reports
  `ok: false` before moving on, keep the portal-change check before each page, and always take a
  fresh full read immediately before the irreversible action (§4b) and before reading any
  confirmation value off the page — **the irreversible action is never a `submit_selector`**.
  Fewer calls is an efficiency win, not a safety discount.

Same instinct as `agent_max_turns` (above), from the other side: raise the ceiling so a long job *can*
finish, and batch the inputs so it finishes *sooner* — inside the browser session's hard lifetime.

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

**Robustness belts you get for free — given a running scheduler (you don't author them; you do
have to not disable them).** The SLA reaper is the *slow* backstop (tens of minutes to hours).
Faster mechanisms below it keep a transient outage from stranding work, and the dispatch/uplink
ones are safe by the same **one-run-per-claim** fence — a re-fire that races a live run is
dropped, so neither can double a side effect:
- **The belts are scheduled actions on the client's Odoo — a scheduler-less Odoo runs none of
  them.** Both the re-dispatch belt and the SLA reaper fire from the owner-Odoo's
  **scheduled-action worker**. An Odoo started without one (`--max-cron-threads 0` — common in a
  debug/IDE launch profile, and the default in some container images) silently runs **neither**.
  Nothing looks broken: the dispatch itself is **inline** (it fires on the state write, in the
  same transaction), so a green happy path claims and runs exactly as it should — only **recovery**
  is dead. You find out on the first dispatch the bot misses, which then sits in the working state
  instead of being re-posted minutes later. So run any Odoo you point a bot at **with cron threads
  enabled** — if your debug profile disables them, keep a second, cron-enabled profile and use it
  for all bot work — and have your launcher **assert the scheduler is alive** at bring-up (probe
  the owner-Odoo's scheduled-action lag; warn loudly past a few minutes) rather than trusting that
  a green happy path means the belts are there.
- **Fast re-dispatch of a lost dispatch.** If a record is claimed but its isolated run was **never
  consumed** — the dispatch committed while the bot's gateway was down and its reconnect did not
  replay it (a rebuilt bot has no poll cursor, and a downtime past the cursor's backfill bounds
  seeds at the channel's latest message) — the dispatch belt **re-posts** the flagged message a few
  minutes later, for the *same* claim, no re-claim, so a bot that has since reconnected picks the
  work up. A run that *did* start then died is left to the SLA reaper (re-firing it would be a
  no-op). You get this automatically for any bot-owned workflow state; you don't wire it.
- **Transient uplink retry.** A brief `/json/2/` blip (a tunnel reconnect, an Odoo restart) is
  retried transparently for **idempotent reads**, so a long run's many reads survive a hiccup instead
  of failing the turn. Writes are **never** auto-retried (they might have committed before the
  response was lost) — they surface, and your fail-closed logic (§4b) decides.
- **Transient browser-startup retry.** Opening the managed cloud browser is the first slow step of a
  browser-driven job, and a momentary hiccup there used to abort the whole turn seconds in. That first
  session-create is now retried a few times on a transient failure (a connection that never completed,
  or a proxy hiccup) before it gives up, so a blink at startup doesn't strand the run. A cap ("top up
  your balance") still surfaces at once — it is not transient.
- **Near-TTL warning + reconnect-storm signal (the browser session is hard-capped).** The managed cloud
  browser has a **hard, un-extendable lifetime** — a long wizard-driving job can run into it. The
  platform hands you two signals **for free, inside your browser tool results**: ~90 s before the cap it
  appends a *"browser session closes in ~Ns — finish the current step and escalate now"* notice, and
  once the session starts disconnecting it appends a *"browser session unstable"* notice. **What you
  author** (not free): (1) tell your Talent to **heed the closing-soon notice** — finish the field it is
  on and take the **escalate** transition; do **not** start a new multi-step action against a session
  that's about to die; and (2) **fail closed** (§4b) if the browser becomes unreachable mid-action — a
  dead session means the real-world action **did not happen**, so write no proof and escalate, never a
  fabricated confirmation. For a genuinely long browser job, also raise `agent_max_turns` (above) so the
  run has room to finish before the cap rather than racing it.

### The attended approval gate — workflow states, not pause/resume

Some side-effects must not fire until a **human approves** them. The wrong build is a pause/resume
primitive that suspends a live run mid-turn and wakes it on a click — it couples the harness to a
durable-workflow engine and leaves a half-run holding a claim. The right build is **pure workflow
states**, on the **same isolated-turn harness (§6) with no harness change**:

- **A prep run previews, then parks.** A bot-owned **prep** transition fires a fresh isolated turn
  that gathers the record's data, produces the **preview/summary** the human will judge, and advances
  the record into a **human-owned "paused for approval" state** — performing **no** real side-effect.
  The prep run is *done*; nothing is suspended.
- **A human approve transition arms the real work.** The person reviews the preview and takes an
  **approve** transition, moving the record into a **bot-owned queue state**. That state dispatches
  like any other bot-owned queue state (§6): its **own claim** fires a *second*, fresh isolated turn
  that performs the **real** side-effect.
- **The claim mints a fresh claim epoch.** Because the real work is a freshly-claimed turn — not the
  resumed prep run — a **stale prep run cannot act on the approved record**: the approve→queue claim
  bumps a **claim epoch**, and a late prep turn writing under the old epoch is fenced out. Approval is
  a state boundary, not a shared session.
- **Narrow the proof guard to the real advance.** Scope the server-side proof guard (§4b) to the
  transition that records the **real** proof (the post-side-effect advance), **not** the prep advance
  — the prep run legitimately advances the record with *no* external proof yet, so guarding it would
  fail-closed the wrong step. Guard only the advance that claims a real-world outcome.

### The human-login gate — park, a human logs in, re-dispatch on a fresh claim

Some portals gate the real work behind a **login only a human can pass** — an identity-provider
sign-in, an SMS or authenticator one-time code, a hardware-key tap. The wrong build is a pause/resume
that freezes the automation mid-turn waiting for the person to type the code — it holds a live browser
*and* a claim open for minutes against the session's hard lifetime (the near-TTL trap, above), and on
the isolated harness there is no chat reply the throwaway turn can even receive. The right build is the
**same pure workflow states** (§6), with the login done in a **separate, human-driven browser session**
the next run reuses:

- **A run reaches the wall, parks, and ends.** When a dispatched turn hits the login/2FA wall it takes a
  bot-owned **work** transition into a **human-owned "needs login" state** and ends the turn — it opens
  no authenticated session and writes no secret. Register that state as an accepted **work** outcome of
  the in-progress state (§6), or the harness's timeout backstop hands the record back as a false failure.
- **A human logs in, in a fresh profile session — the bot never sees the credential or the code.** The
  person completes the gated login (types the one-time code, taps the key) in a **fresh browser profile
  session** minted at click-time, not inside the bot's automation session and not by handing the bot the
  secret. What the later run reuses is the **authenticated session** that login produced — a bound browser
  profile / cookie — never the raw credential or the OTP. Mint that session *when the human is ready*, not
  when the wall is hit, so the login sits inside the browser's hard lifetime instead of racing it.
- **Land the minted session ON the portal's sign-in page — never hand the human a blank browser.** A
  fresh session opens on `about:blank`, and the person doing the login (an office user, not a developer)
  cannot be expected to know or type the portal address — in a test tier it is a machine-generated stub
  hostname they have never seen. So the mint call carries the workflow's **portal entry URL** (declared
  client-side as tier config, exactly like the broker seam itself, so the test tier lands on its stub and
  prod on the live portal) and the platform **navigates the session there server-side before returning
  the viewer link**; with no URL configured it falls back to the tenant's *single* stored-login origin
  (the stored credential already knows where its portal lives — and landing on it lets credential
  auto-fill fire). The landing is **best-effort**: if navigation fails the mint still stands and the
  human lands blank — degraded UX, never a blocked login. Dry-run the click yourself before handing the
  flow to the client: the tab must open on the sign-in form.
- **A resume transition re-dispatches on a fresh claim.** When the human marks the login done, the record
  moves into a **bot-owned queue state** that dispatches like any other (§6): its **own claim mints a
  fresh claim epoch** and fires a *second*, fresh isolated turn that does the real side-effect against the
  now-authenticated session. A stale parked turn cannot act on the resumed record — the resume→queue claim
  bumps the epoch and fences a late writer out. The login is a **state boundary, not a shared session.**
- **Fail closed — and never re-drive the login (no re-code).** If the re-dispatched run *still* finds the
  session unauthenticated (the human hasn't finished, the session expired, the flush hadn't landed), the
  work **did not happen**: write nothing, advance nothing, take the **escalate** transition (§4b), and
  **do not re-enter credentials or re-request the one-time code.** Re-triggering a code is a human-only
  step — each request burns a rate-limited send and can lock the account — so the bot's only moves at a
  closed gate are *reuse a session a human already authenticated* or *escalate*, once. A partial
  write-ahead marker is not proof; the escalate path stays open with it present.
- **Guard only the real advance.** As with the approval gate, scope the server-side proof guard (§4b) to
  the **post-side-effect** advance, not the park or the resume — parking and re-claiming legitimately
  advance the record with no external proof yet.

Grade it with a red scenario `login_gate_closed_no_fabricate` (the §4b `<failure>_no_fabricate` family):
converge the bot against a gate with **no** authenticated session and assert the *negative* ground truth
— the record did not advance past the gate, no real proof exists, the reply escalates, and the run made
**zero** re-login or re-code attempts. Keep the everyday path cold with a low-frequency **attended login
refresh** that renews the session before it expires, so the reactive gate stays the rare-path safety net.

**How the client's own system reaches Oteny (the client-integration seam).** The mint-on-click and the
attended-refresh above are triggered by the **client's own system** (its ERP / back-office) calling Oteny
**server-to-server** — not by the bot. That call rides a single **public HTTPS lane** the platform
operates, and the contract is deliberately tiny: **one base URL + one `Authorization: Bearer <token>`
header**, JSON body, synchronous response. The bearer is a **purpose-scoped client-integration
credential** — issued per client-integration, independently revocable, and **distinct from any model /
spend token** the bot uses — so exposing this seam can never leak model budget, and rotating it never
disturbs the bot. Treat the value like any secret: it lives in the client system's own secret store
(never in chat, never on the bot's box), and the synchronous response (e.g. an ephemeral human-login
viewer URL) is opened once and **never persisted or posted into a channel**. You do not build this lane —
the platform provides it; you only need to know the seam is *one bearer header to one URL*, so a client
integration is a config value, not a bespoke protocol.

**Rebind the client's credential every time the bot is (re)delivered — a stale seam fails GREEN.** The
client-integration credential authenticates a *specific bot instance*; a dev loop that rebuilds or
replaces its bot (a durable-slot rebuild, a fresh commission) silently strands a hand-wired credential on
the PREVIOUS instance. The failure is the worst kind: every step still reports success — the login
session mints, the human signs in, the save confirms — but the authenticated session lands in the *old*
bot's browser profile, and the *current* bot still hits the wall. Nothing platform-side can detect it
(the platform cannot know which bot the client's workflow meant). So the pattern is structural
freshness, not detection: at every delivery the platform mints a fresh purpose-scoped credential for the
delivered bot and exposes it as a **one-shot claim** on the commissioning request (claimed once, then
blanked); the dev-loop launcher claims it and **rewrites the client system's seam config on every run**.
Hand-wiring stays only for prod cutovers — and even there, rotate the credential as part of any bot
replacement, never after it.

### Watching an inbox for the outcome — the mailbox stub double

A workflow often completes only when a **counterparty replies** — an email confirming or rejecting
what the bot filed. A bot that **polls an inbox** for that reply is a side-effecting integration like
any other, so it takes the **same stub-double tier trick as a portal (§4)**: prod mounts the real
mailbox; **every non-prod tier mounts a stub inbox**, and the same Talent ships unchanged across
tiers.

- **The stub inbox serves seeded fixtures.** On non-prod, the mailbox poll points — via a tier-bound
  `external_systems` env var (§4c) — at a **stub inbox** shaped like the real mail API, serving seeded
  `.eml` fixtures, plus a **driver** that lets a test *"simulate the counterparty confirmed / rejected
  item X."* The whole **confirm/reject round-trip is offline-verifiable** with zero third-party
  dependency, on the same tier your other doubles run.
- **The mail body is UNTRUSTED third-party text.** A counterparty's reply is exactly the
  **indirect-injection** class the isolated turn (§6) exists to contain — arbitrary text from outside
  your trust boundary. So the **confirm-vs-reject decision is made by the AI run** reading that body,
  never by a brittle string match on attacker-controlled prose; and the **key that ties a mail to the
  right record is a unique reference number** (the filing id you recorded as proof), not the free-text
  subject or sender.
- **The real credential is broker-held.** The prod mailbox credential (an OAuth token, an app
  password) is **broker-held — never on the box** — and is the one **office-gated, prod-only** piece:
  non-prod never needs it, because the stub inbox needs no auth. The outcome-watch is offline-testable
  end to end while the real inbox stays reachable only from prod.

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
- **Fixtures** — every side-effecting scenario has its **own** seeded fixture (never a
  shared or prod-copy record), and the bundle's repo ships an **idempotent seed/reset
  tool** that creates each one, resets a consumed one, and verifies it against that
  scenario's exact `hand_off` domain; mutually-exclusive scenario classes are run per
  invocation (`test … --scenario …`). (PASS/FAIL / N/A)
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

## The author-time ledger (changelog discipline)

The load-bearing cost of a business bot is **author/AI-dev time**, not tokens — but that cost
is invisible unless you record it. So every Talent **version-bump changelog line** carries two
extra fields, right in the `agent-profile.yaml` changelog comment:

- **`~effort: <AI-session-h>/<review-min>`** — roughly the AI-coding-session hours plus the
  human review minutes that version cost. Estimate; the point is the trend, not the decimal.
- **a class tag** — what *kind* of work it was, one of:
  - `[flash-coax]` — behavioral prose written to make a **weak** model behave (exact-call
    recipes, anti-fabrication paragraphs). **This is the tag to drive to zero**: if a behavior
    needs it, the honest fix is a stronger tier (the model-tier rule), not more prose.
  - `[model-indep]` — structure that helps on **every** tier (a checklist, a selector map, a
    batch-fill rule, a fail-closed belt).
  - `[cost]` — work that cut run cost/latency (fewer round-trips, a tighter toolset).
  - `[safety]` — a new guard, a pinning red scenario, a contradiction removed.

Example line: `0.6.2: reconciled the confirm-before-submit texts to the workflow gate.
~effort: 3h/20m [safety]`. Over a few versions the ledger makes the "tuning time dwarfs
tokens" claim **testable**, and a pile of `[flash-coax]` entries is the measured signal to
raise the tier instead of writing more prose.
