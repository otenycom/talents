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

## 1. Channel routing — Discuss usual, Telegram allowed (check 5)

A B2C bot routes to Telegram. A business bot **usually** routes to an Odoo
**`discuss.channel`** — the chat built into the business's Odoo, where the team already
works all day — but **Telegram is allowed** when that is the team's surface. Channel is
where humans talk; it does **not** gate the data plane (§3).

**Discuss (typical internal team):**

```yaml
routing:
  channel: discuss
  home_connection: crewradar       # Discuss poll target only — omit on Telegram
  channel_prompt: |
    You are <bot>, the team's <job> desk in this Odoo Discuss channel. Load the
    <bot> skill and follow its triage and hard rules. Never ask for a password or a
    one-time code in chat. Reply in the operator's language; keep replies chat-short.
  signature: "<bot>"
```

- **No public inbound, no separate app** — the chat is inside the business's Odoo.
- The `channel_prompt` is the standing instruction injected every turn — same discipline
  as a B2C bot (who it is, which skill to load first, the hard rules), tuned for a team
  channel rather than a 1:1 DM. The platform renders it into the box on **every
  delivery** — delivery = activation, so pushing a Talent change changes who the bot *is*
  with no extra step.
- Add **`preload_skills:`** (top-level, beside `skills:`) naming the persona/umbrella
  skill + the main working skill: the platform injects their full text at the top of
  every fresh session — including each dispatched isolated run — so the job starts with
  its procedure in the cached prefix instead of spending calls on `skill_view`.

### 1a. Two lanes: the casual desk and the declared role channel

One bot serves **many** Discuss channels, and the pair above is the **casual lane** — the
persona and preload the bot uses in *any* room a staff operator adds it to. That is the
whole configuration a simple business bot needs.

A bot with a real, auditable job wants a **second lane**: a room that is only that job, so
the run lands with the job's persona and its procedure already in context, and the room's
own history is the record of the work. Declare it as a **role** — a name, not a channel id.
The Talent never learns the client's channel ids; the client's own Odoo binds the role to a
room (`oteny.bot.channel`), and the adapter pairs them at runtime:

```yaml
routing:
  channel: discuss
  home_connection: crewradar
  channel_prompt: |                # LANE 1 — the casual desk, used in every other room
    You are <bot>, the team's <job> desk. Say what you can and cannot do, …
  channels:                        # LANE 2 — the declared job rooms
    - role: mfnl_filing            # must match the client-side oteny.bot.channel role
      channel_prompt: |
        This channel is <job> only. …
      preload_skills:
        - <bot>
        - <the-working-skill>
  signature: "<bot>"
preload_skills:                    # the casual lane's preload — keep it LIGHT
  - <bot>
```

Rules that make the split worth having:

- **Keep the casual preload light.** Preloaded text is paid for on every fresh session in
  every room; the heavy working skill belongs on the role lane, where the work happens. A
  casual turn that genuinely needs it can still `skill_view` it.
- **Every hard rule that is about safety, not about the job, stays in BOTH prompts** —
  never ask for a password or a one-time code, never scan `mail.message`, never invent
  data. A prompt-injected turn in a casual room must hit the same wall as one in the job
  room. Only the *job* half is lane-specific.
- **A role is attention, not authority.** The toolset lock, the connections, and the
  client-side ACLs are identical in both lanes — the role picks which persona and which
  skills load, and nothing else. Do not write a prompt that implies a casual room is
  "read-only": it is not, and a rule the platform does not enforce is not a rule.
- **Fallback is safe by construction.** A client that binds no role at all keeps today's
  single-room behaviour: the bot's home channel plays the first declared role. Omit
  `channels:` entirely and every room is the casual desk.

**Telegram + odoo data plane** (when the team lives in Telegram):

```yaml
routing:
  channel: telegram
  # no home_connection — that is Discuss-poll-only
  channel_prompt: |
    You are <bot>, the team's <job> desk on Telegram. …
  signature: "<bot>"
# still declare connections: + odoo_client in toolset_contribution — see §3
```

## 2. Minimal locked toolset (checks 1 + 9)

A B2C assistant requests the wide set (`[terminal, execute_code, cron, send_message]`) —
breadth *is* the product. A business bot requests **only the tools its one job needs**, and
the generic toolsets are **OFF**:

- **OFF for a scoped bot:** `terminal`, `execute_code`, filesystem, and the open-web
  search tools. None of these mount unless the job genuinely needs them. (The gateway
  keeps a small `skills`/`clarify` **read floor** mounted — `skill_view` must work for the
  bot to load its own composing skills; what's off is skill *creation/self-editing*, see
  the lockdown below.)
- **ON, named explicitly:** `odoo_client` (the data plane — §3, always with `connection=<name>`);
  optionally the secure browser (`browser` + `browser_request_human` + `browser_download`)
  for portal filing; optionally a mailbox reader for an inbox
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
(screenshots — a snapshot already gives the page state,
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

## 2b. Your scope contract is adversarially gated — keep it coherent

Your `agent-profile.yaml` **is** the scope contract, and Oteny runs an **adversarial probe
suite** against it on top of the authoring lint — a second pass with two halves you should author
for:

- **A static coherence check at delivery** (no box, always on): it *fails delivery* if your
  contract has a structural hole an attacker walks through. Keep it coherent:
  - for every **portal** connection (`connections.<name>.kind: portal`), the host in
    `real_url` **must** appear in that connection's `fence_hosts` (else a non-prod bot could
    reach the live portal);
  - a locked bot **must** declare a `routing.signature` and a non-empty `routing.channel_prompt`
    (the scope anchor the guard holds to);
  - if you declare an **odoo** connection (§3), **do not also mount a generic shell/code toolset**
    — `odoo_client` is your system-of-record path, so drop `terminal`/`execute_code` (a demo with
    a local sqlite and *no* odoo connection is the only place a bare `terminal` is allowed).
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

## 3. Named odoo connections + `odoo_client` (checks 2 + 6)

A B2C bot's source of truth is a local SQLite db under `~/.hermes/data/<bot>/`. A business
bot's source of truth is **the business's Odoo**, reached over authorized **`/json/2/`**
calls through the **`odoo_client`** tool — it reads and writes real business records, not a
local db. This data plane is **channel-agnostic**: declare `connections:` + request
`odoo_client` on Discuss **or** Telegram (or web). Only Discuss also sets
`routing.home_connection` (the poll target).

- The bot connects with its **own least-privilege bot user + a scoped API key** (delivered
  by the deployer as a secret, never baked — check 4 + the `secret` artifact class). It is
  not a human's login and not an admin key.
- Each odoo bind is a **named connection** under `connections:` with `kind: odoo`. Declare
  **`odoo_grants`** on that connection — the explicit list of models/operations the bot user
  may touch. A grant the manifest doesn't name is a record the bot cannot read or write,
  even if its prompt tries.
- Every `odoo_client` call passes **`connection=<name>`** (the same name as in `connections:`).
  The platform binds `OTENY_CONN_<NAME>_URL`, `_DB`, and `_KEY` on the box; the tool resolves
  them — never hard-code URLs or keys in the bundle.
- `required_artifacts.yaml` declares the uplink as the readiness condition (the bot user
  resolves + the scoped key is present + a probe read returns), the business-bot analog of
  "db file exists + tables present." A bot with no reachable odoo connection is NOT-READY
  and must not serve.
- **Namespacing still holds (check 6):** any *local* scratch the bot keeps stays under
  `~/.hermes/data/<bot>/`; the authoritative records live in the business's Odoo, reached
  only through the granted `/json/2/` scope.
- **Keep call shapes lean in `SKILL.md`:** long exact `odoo_client(…)` examples belong in
  `references/` — a child skill body over **20 000** characters fails both the offline lint
  and on-bot delivery (`last_status=gate_failed`). See `oteny-talent-dev-loop` readiness.

**The concrete YAML** (Discuss — poll + data plane):

```yaml
toolset_contribution:
  - odoo_client              # Odoo /json/2/ — pass connection=<name> on every call
tools:
  required:
    - odoo_client
connections:
  crewradar:                 # name is yours → OTENY_CONN_CREWRADAR_*
    kind: odoo
    uplink_user: hr.otenybot # the bot's OWN least-privilege login in your Odoo
    odoo_grants:             # exactly what the job touches — nothing else
      read:  [riverflow.service, res.partner, rivercreds.credential]
      write: [riverflow.service, rivercreds.credential]
routing:
  channel: discuss
  home_connection: crewradar # Discuss polls this odoo bind (OTENY_HOME_CONNECTION)
```

**Telegram + same data plane** (no poll target):

```yaml
toolset_contribution:
  - odoo_client
tools:
  required:
    - odoo_client
connections:
  crewradar:
    kind: odoo
    uplink_user: hr.otenybot
    odoo_grants:
      read:  [riverflow.service, res.partner]
      write: [riverflow.service]
routing:
  channel: telegram
  # no home_connection
```

> **EXAMPLE — Barney (Cuneus MFNL):** the live bundle names the odoo connection `crewradar`,
> sets `home_connection: crewradar`, and adds a portal connection `meldloket` for
> postedworkers.nl filing (§4c). Copy the *shape*, not the model names, for your vertical.

**Discuss pull + gateway startup-restore (platform footgun authors see as “dual browser”).**
Discuss is a **pull** adapter: its poll loop can start while Hermes is still in
`_startup_restore_in_progress`. If the adapter advances the per-channel marker (or claims
dispatch) and hands the event to the runner **inside** that window, the runner *queues*
the turn; when the gate opens, drain re-delivers the same `mail.message` → two agent turns
on one plain-channel post → two cloud-browser sessions. Platform fix (hh-discuss overlay
89): **skip the whole poll body** while startup-restore is set, and persist a once-only
**`dispatched` claim ledger** beside the marker. If you ever see two Steel sessions for one
Discuss message after a bot upgrade/restart, check that overlay before blaming the Talent.

The platform binds each connection on the box at commission (keys delivered as secrets, never
baked). Declaring **`connections:`** (odoo or portal) is also what makes `neutralize.yaml`
mandatory — a clone of a bot with real binds must be defanged before it serves.

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
- **Interactive stub login walls stay ON for human dog-food.** If your double has a
  login gate (portal credentials, MFA hand-off), non-prod provision should leave that
  gate **enabled** so Hand-to-Barney / Bot Activity exercise the same login path as
  prod. Automated `test` scenarios that need a pre-authed session disable the wall
  only for that class of run — never as the default for an interactive staging tier.

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
- **ERP-sourced identity keys are blockers, not prompts.** Keys the bot must type into an
  external system that already live on the owner's ERP record (a chamber-of-commerce number,
  a vestiging id, a VAT keyed to that entity) belong on the DTO with **`severity: error`**
  when empty. The Talent **halts and escalates** — it does **not** invent them, open-web
  look them up, or `search_read` sibling records to “find” a substitute. A portal register
  lookup that *confirms* a DTO number is fine; discovering a missing number outside the DTO
  is not.
- **The server refuses an unproven "done" (the claim guard).** Don't only trust the
  Talent's discipline: the workflow's single advance choke point exposes a guard hook, and
  the domain layer refuses the success transition unless the **proof record actually
  exists** (e.g. a captured, non-placeholder filing number on the credential). A run that
  skips the proof — on *any* model — is refused server-side, stays in-progress, and the
  timeout reaper hands it to a human. Escalation is **never** blocked by the guard: a stuck
  run must always be able to reach a person.
- **Gate the ENTRY on the state, not on the transitions into it.** The mirror of the guard
  above. It is natural to hang the data check on the hand-off button — a confirm wizard that
  refuses on any `severity: error`. That check is only as complete as the list of buttons you
  remembered. Count the transitions **into** your bot's queue state: there are usually more
  than you think, and the one you forget is the *retry* lane — the record that came back
  **rejected**, which is by definition the one most likely to carry bad data. Put the same
  check in the **claim guard**, keyed on the state. A gate on a transition is bypassed the
  day somebody adds another transition; a gate on the state holds however the record arrived,
  and it also catches data that **degrades between the hand-off and the dispatch**, which no
  wizard can. Keep the button wizard too — it is what gives the human an explanation at the
  moment they act. Write the regression test against the state's **inbound edges**, not
  against a list of transition names, or the next lane re-opens the hole silently.
- **One external question = one DTO answer key. The bot types; it does not decide.** Emit
  the literal answer the external system expects, under a key named for the field it fills —
  never the underlying facts plus an instruction to infer. Two costs otherwise. The model
  re-derives business logic per run, so the same record can answer differently twice. And a
  wrong reading gets baked in where nobody reviews it: collapsing two *similar-sounding*
  questions into one answer is the classic form. "Do you **hold** permit X?" and "have you
  **applied** for permit X?" are different questions, and a form that asks both separately is
  telling you they are. Answering the first from the second states something untrue to a
  regulator. When the operator walks you through the real form, count the questions and emit
  exactly that many keys — then keep the derived facts on the DTO as well, for the issue
  banner and for the human reading it, but never as the thing the bot types.

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
  - **Keep the connector `--token-file` until the cloudflared process exits.** Named tunnels take
    `--token-file` (0600 temp, never argv). Unlinking that file in a `finally` right after spawn can
    leave a healthy-looking connector that later exits 255 on reconnect / token re-read. Delete the
    file only when tearing the process down (or hold it for the held-child lifetime).
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
- **You declare outside systems as named connections; the platform binds each by tier.** Every
  side-effecting system the bot touches gets an entry under `connections:` with `kind: portal`
  (browser-facing URL + fence). The concrete YAML:

  ```yaml
  connections:
    meldloket:                           # name → OTENY_CONN_MELDLOKET_BASE_URL
      kind: portal
      real_url: https://meldloket.example.gov   # what a PROD bot gets
      fence_hosts: [meldloket.example.gov]      # what a NON-prod browser is blocked from
    mailbox:
      kind: portal
      real_url: https://mail.example.com
      fence_hosts: [mail.example.com]
  ```

  For each portal connection, the platform binds **one** URL by tier — **prod → the
  Talent-declared `real_url`; any non-prod tier → the stub** — and exposes it as
  `OTENY_CONN_<NAME>_BASE_URL` on the box only (there is no separate `OTENY_PORTAL_BASE_URL`
  alias). On a non-prod tier it also writes `OTENY_PORTAL_FENCE_HOSTS` — the **union** of every
  declared `fence_hosts` — so the cloud browser cannot open those real hosts. That fence list is
  not a connection bind; the URL the bot must navigate is always the named `OTENY_CONN_*_BASE_URL`.
  Discuss (and webchat) append the **resolved** named URL into the channel prompt because a
  toolset-locked bot cannot shell-expand `$OTENY_…` itself. The platform *binds/fences whatever
  you named* and hard-codes no third party's address. **The prod identity (`real_url` +
  `fence_hosts`) lives in your Talent** and is versioned with it; the throwaway stub value does
  not (next bullet). Pass the stub at request time under the connection **name** (e.g.
  `stub_endpoints.meldloket`), not a legacy `portal` key unless your Talent's connection is
  literally named `portal`.

  **`$OTENY_CONN_*` is a tool-target convention, not a template language.** Writing
  `$OTENY_CONN_MELDLOKET_BASE_URL` in skill prose works where the bot **resolves it to make a
  call** (`browser_navigate` to `$OTENY_CONN_MELDLOKET_BASE_URL/portal`) — that is the intended
  usage, and the demo bundle models it. Nothing interpolates it in a **human-facing** message: a
  reply or escalation telling an operator to "check `$OTENY_CONN_MELDLOKET_BASE_URL`" ships the
  literal token to a person who cannot resolve it. In any text a human reads, instruct the bot to
  write the **resolved value**.

  **Footgun — cloud browser "private/internal address" on navigate.** Almost always the prompt
  never carried a public stub URL (missing `OTENY_CONN_*_BASE_URL` on the box, or the bot
  improvised a loopback). Confirm with box `inspect` that the named portal env is the public
  tunnel/stub host, then re-hand the service. Fresh-restoring the client ERP DB does not fix a
  missing bot-box bind.
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

*Worked example (Barney, the Dutch posted-worker filer):* the meldloket double is the CrewRadar
**`/mfnl-stub`** controller on neutralized tiers (minting a bare 9-digit number — the real portal's
shape); the Talent declares `portal.real_url` + `portal.fence_hosts`; the server-side claim guard
refuses a "filed" whose number isn't the right shape; and **`provision_barney.py --tier local`**
(or launch **`barney-provision-local`**) commissions the bot, wires uplink + stub + broker tokens,
and holds the local uplink tunnel.

**A restored ERP database severs your rig — reprovision before the first hand-off.** Every piece
of the bot binding lives *inside* the owner's ERP database: the adopted bot record, the uplink
key, the broker seam tokens, and the stub bind. A restore (or a replaced DB) erases them all,
while your launcher's local state file still names a bot that no longer matches. The failure is
silent and looks like bot trouble: the first hand-off **claims** the work item into the bot-owned
in-progress state and posts the dispatch into a channel **nothing polls**, so the owner's activity
log shows *Working* forever. The DB tells are unambiguous — the run was never consumed (the
run-started stamp stays empty) and the bot record carries no ref. Two rules compose: **re-run your
tier provisioner after *any* ERP restore, before the first hand-off**, and **serve the ERP with a
cron worker** — the dispatch re-post belt and the SLA reaper (§4h) are ordinary crons, and with
them dead the stuck claim never recovers, while with them alive the reaper hands the item back
within the state's SLA and you simply re-hand it. (Live case, 2026-08-24: a restored CrewRadar
served by a cron-less debug config held a claim stuck for five hours; a cron worker + reprovision
recovered it in one reaper tick, and the re-hand was consumed in seconds.)

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

   **Match each control's WIDGET SHAPE, not just its label and options.** A field your double
   renders as a native `<select>` where the real system renders a trigger plus a popup listbox is
   a fidelity gap, even though both hold the same options and both post the same value. Your
   skill teaches the recipe for the real widget — click the trigger, then click the option — so
   on the double the bot finds no list, improvises, and **burns a model action per field
   discovering the difference**. A wizard with nine such fields pays nine actions plus the
   context they carry, which is the exact cost a double exists to avoid. So render the trigger,
   the listbox and the option rows your step-1 observation recorded, and keep a hidden input on
   the same `id`/`name` if the double still needs a plain form post to work. Declare the same
   shape in the runbook (§4e, "The real page is not your stub") so the two never drift.

   **A stub that cannot fail the way production fails is a false-green machine.** Write one
   red test per fidelity gap **before** you make the double more faithful. Cite the measured
   case in the test name or docstring. Run those tests against the **current** double and
   leave them red. A later session implements the double so the tests go green. A session
   that both writes the trap and springs it cannot tell you the trap works. Keep the
   existing happy-path stub suite on its own tag so a full green run does not hide the
   traps.

   **Honour injectable fidelity knobs. Do not turn them on by default.** A later
   session that makes the double faithful should generalise delay, mutation, and
   login-origin knobs the happy-path suite already uses. Sleep only when a
   millisecond param is set, so the existing suite stays fast. After a radio or
   checkbox POST, rotate element ids so a prior snapshot id is gone. Keep the
   first-load semantic ids the happy-path tests already look up. Put the login
   hop on a second origin (a localhost path or host that embeds the real IdP
   name is enough). Do not call the live identity provider. A cookie on the
   portal path must not authenticate that hop.

   **The product path is the live accessible name, never a stub shortcut.** The Talent must
   be fastest on the live site. The double exists so the same `role+name` click works on
   both. Pass that selector **without an `@` prefix**. `@e5` is a snapshot ref. A named
   selector that carries `@` matches nothing.

   The host strips a stray `@` before the browser daemon sees the click, so a clean
   `role=…[name="…"]` now reaches the page.

   A `browser_type` that cannot prove the text stuck reports **failure**, not
   success. Believe that error. Do not walk on. The host reads the field the
   selector names. An empty field after type is a failed write.

   **State one legal click method. Do not ban both.** The legal method is
   `browser_click` / `browser_type` with a named selector
   (`role=…[name="…"]`), with no `@` prefix. Do not hand-drive the raw
   browser protocol for an ordinary click. A snapshot ref goes stale after
   a mutation, so do not prefer it. A runbook that forbids refs *and*
   forbids the raw protocol, while the click tool only accepted a ref,
   left no legal path. The host now delivers a named selector. Keep that
   one method in the skill. Ship the skill edit in the **same release** as
   the host wrap. An isolated transition turn does not keep a lesson.
   Keep trail output in a gitignored pack. Do not paste page quotes into
   the repo.

   The host halts a second identical `Unknown ref` on the same session
   and target. The first miss still tells you to snapshot and use a
   named selector. The second miss returns `halt: true` and does not
   call the browser again. Do not `browser_navigate`. Do not fall
   through to `browser_cdp`. Escalate to the operator.

   Hidden inputs, stub `#id`s, and CDP `element.value` writes are POST / debug
   affordances — they are **not** the fill recipe. A wrapper the HTML parser closes before
   the listbox (`<p>` around a `<ul>`), or a radio group wrapped so a centre-click hits the
   question text, trains the bot to cheat on the double and miss on the live page. Render a
   combobox so the listbox is inside the wrapper (`aria-controls`); a click on list chrome
   must pick the nearest **visible** option, never close the list. Render a radio group as
   `<fieldset>` + `<legend>` + a visible native radio so the snapshot is
   `role=group[name="…"] >> role=radio[name="…"]`. A generated shared `name` across a live
   group cannot be the primary. Old `input[name=]` rungs stay fallbacks only.

   Expect a **fidelity** win, not a speed win. Measured on one bot's two graded scenarios, the
   same change moved one run about 9% faster and the other about 4% slower. What you buy is that
   a green run on the double now exercises the technique a live run needs, so the two stop
   drifting silently. **Keep the skill's dual-shape handling anyway** — read the control's shape
   off the snapshot and handle a native `<select>` too. A real third-party page may serve one, so
   that rule teaches a browser fact, never a fact about which tier the bot is on.
4. **Mark what you haven't seen.** Screens the walkthrough skipped stay in the double as
   best-effort with an explicit *unverified* note, and your field map keeps an "open unknowns" list
   you burn down with the operator. Re-harvest whenever the real system changes (your skill's
   portal-change detection is what catches that).
5. **Model the LANDING page, not only the forms.** The easiest screen to get wrong is the one
   nobody calls a form: the dashboard, worklist or inbox the run starts and ends on. It decides
   where a run **finds** work — a resume, a retry, a "did my last run leave residue?" check — so a
   row filed under the wrong heading is a real defect, not cosmetics. Copy its **actual tab
   structure and row semantics**: which list holds your own drafts, which holds tasks the *other
   side* raised, and which holds finished items. Model the per-row **controls you intend the bot
   never to press** (a delete, a copy-to-new) rather than leaving them out — a control that is
   absent from the double cannot be pressed by mistake in a test, only in production. Then write
   the "leave it alone" rule in the skill, where it belongs. Assert on the **section**, not on the
   page: a whole-page `assertIn` cannot tell a corrected layout from the broken one.

   *Worked example (Barney):* the double rendered the portal's "My tasks" tab as a hard-coded
   empty state and filed drafts under "submitted for review" — exactly the opposite of the real
   dashboard, where a draft IS a task and sits beside tasks the ministry raised. The forms had
   been harvested carefully; the index page had been guessed. It went unnoticed for weeks because
   the happy path never reads the dashboard — only a resume-and-correct run does.

   Persist the portal's draft id on the ERP record after save. Isolated dispatch
   is thin: the next run reads a DTO. It does not remember the last browser row.
   If the skill saves a Concept and never writes the Meldingnummer back, the next
   Hand treats the key as empty and starts a new filing. Empty on the DTO means
   start new. A stored number whose row is gone means stop.

*Worked example (Barney):* Kirsten's 24-screenshot walkthrough of one real meldloket filing was
transcribed screen-by-screen, cross-checked against CrewRadar (surfacing the VAT transposition, a
per-ship SBI rule, the −1-day/+1-year date convention, and an optional-BSN the DTO wrongly
required), and the double was rebuilt from a single form into the real 8-step wizard with two
register-lookup interludes, date carry-over, and the consent gate.

**Keep a thin page for login and queue tests.** The full wizard proves
selectors and fill. A shared-login or one-live-slot walk only needs
Needs Login → Open → donate → adopt → linger → drain → *Draft ready*.
Pay that with a stub-only one-field page, not with nine screens.
Keep the real page graph for selector proof. Do not flip a global
flag that shortens every filing. Branch on a fixture flag the DTO
already carries. Barney's stub does this at `/mfnl-stub/dummy-file`
when `mfnl_json.thin_file` is true (Thinpath / Thinpeer).
Score the broker log, not wizard completeness. Drain the next card
in the occupant's own write (`_bot_drain_peers`). A queued sibling
wins. If none waits, drain resumes one fresh SLA-less login park
(`_bot_resume_login_park`). The 3-min cron is the belt for queue.
It does not promote parks. Mid-turn (`linger_until == 0`) is not
adoptable.
Live cookie-carry on the real portal is a go-live eval. It is not
a pre-go-live SMS walk.

**A form that changes its questions by country needs a per-country branch — in the double
AND in the selector manifest.** One happy path plus a hard halt for everything else is not a
design; it is the narrowing of §5b wearing a different hat. When the operator says *"if you
fill in not Netherlands but Luxembourg, then it changed down under the questions"*, that is a
page graph with a branch in it, and an unwalked branch is an unknown, not an impossibility.

Two honest ways to close it, and you must pick one out loud:

- **Walk it.** An attended capture session with the operator, then encode the branch in the
  double, the selector manifest and the doc twin.
- **Let the bot walk it, in draft mode, and harvest the trace.** Give it the branch's data in
  the DTO plus an explicit instruction to read the page and escalate on its own judgement,
  and keep the run non-committing (save a draft, never submit). Its trace is then the capture
  session, and it is a better one — you can diff it against the manifest.

The second is cheaper and usually right. It only works if three things hold, and you should
state them in the same breath: **non-committing** for the first runs, **every value still
comes from the DTO** (no invented identifiers), and **the scope verdict stays out of the
bot's hands**. If any of those slips, walk it instead.

Either way, **mark the branch UNMAPPED rather than leaving it silently absent** in the
manifest and the doc twin. An absent branch reads as "there is no branch".

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
   work-instruction content: **harvest** it once at authoring time from an **observed live
   trace**, **converge** it against reality by observe → `browser-diff` proposals
   → author accepts, and **regression-net** it by back-porting each fix to the stub. When the
   portal is redesigned you **regenerate the runbook** — you never rewrite the instruction.
   Do **not** copy a stub label as the live primary. The stub carries names a human
   transcribed. The trace carries the accessible name the page really exposes.

**A page owns its advance control.** Never name one global Next button for a
whole wizard. A later page may say *Summary* or *OK* where earlier pages said
*Next*. Scroll that control into view **before** the native click. A control
below the fold reads as a naming bug and costs a whole model turn.

**A click can return success and change nothing — that usually means the target sat
outside the viewport.** The snapshot is viewport-independent, so a clipped control looks
exactly like a visible one, and some click executors dispatch at the target's coordinates
without scrolling first (a below-fold click is then a silent no-op that still reports
success — this halted a real filing on the last radio group of a form, 2026-08-25). The
platform now scrolls every ref-click's target into view for you, but keep the corrective
in the instruction because it is executor-independent: when the verify snapshot shows no
state change after a "successful" click, scroll the control into view and **click AGAIN,
then verify**. A scroll alone changes nothing, and one post-scroll click beats stopping at
the harness's repeat warning. The controls most at risk are the LAST fields of a long
form — everything the fill pass auto-scrolled past works, and the bottom few do not.

That split is the reconciliation of "a Talent is a high-level work instruction" with the hard
platform fact that the model **cannot read CSS selectors off a live page** (`browser_snapshot`
exposes accessibility refs, never ids — see [`browser-authoring.md`](browser-authoring.md)): the
selectors have to ship *somewhere*, so they ship as a **compiled artifact beside** the
instruction, not woven **into** it. The rest of this section is how you build and maintain that
artifact.

Your dev stub (§4c) has clean, stable ids you chose; the **real third-party site does not** — its
ids are framework-generated, its custom widgets aren't native controls, and a re-skin renames both
without warning. A skill whose `#id` selectors were written against the stub's tidy
`#first_name` drives the stub perfectly and then **misses on the real page**, mid-filing, where a
miss is a stalled job (or worse, the wrong field filled). Prefer
`role=group[name=…] >> role=radio[name=…]` and `role=combobox[name=…]`. So author every selector as a **resilience
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
  `input[name=agree][value="Yes, I consent"]`. Prefer a role+name locator
  (`role=radio[name="Yes, I consent"]`) so you never write that CSS. If you
  must keep a CSS fallback, quote the attribute value so the runbook is
  correct on its face — the model copies structure, not prose. This is the
  value-targeting analogue of the exact-option-string rule above.

Every rule is the same bet — **the real site's ids and triggers differ from your stub's** — so encode
what won't change (semantics) as the floor, and flag every place a single exact string is load-bearing.

### The real page is not your stub — declare each control from observation

Your double renders native HTML controls because you wrote it that way (§4c). A real third-party page
often does not, and the gap is not cosmetic — it decides whether a step *can* run at all. So every
control in the runbook is declared from **what the real page reported** — a snapshot, a
`form_inventory`, the operator's devtools — never from what your stub renders and never from what the
label makes you assume.

- **A control that looks like a dropdown is frequently not a `<select>`.** Angular Material, React
  Select, OutSystems and Lightning all render a trigger plus a popup listbox. You do not have to know
  which: `kind: 'select'` with the option's **exact visible text** drives both, and the platform picks
  the widget route when the element turns out not to be native (`kind: 'pick_option'` forces it). What
  you **must** do is record the widget kind and the exact option strings beside the field in the
  runbook, from observation — the option text is the whole targeting key on a widget, because there
  are no option *values* to fall back on. Never hand-drive one with `click` steps (§6): that route
  leaves no evidence.
- **A generated id that encodes a component tree is not an anchor.** Some frameworks build ids from
  the rendered container path (`P652-C4-C1-C0-…`); they renumber on any layout change, and a radio
  group's members share **one** generated `name`, so `input[name=…][value=…]` cannot pick a member.
  Trust an id only where it is plainly **hand-authored** — typically the sign-in chrome and a
  vendor-named data table. Note which class each id is in, let the hand-authored ones lead their
  ladder, and keep every generated one as a late best-effort rung behind role + accessible name.
- **The accessible name and the visible label are two facts — record both.** They drift most around
  required markers: the DOM label reads `Start date *` while the accessibility tree spells the
  requirement out as a word (`Start date Required`, in the site's own language). The automation engine
  matches the **accessible** name, and the raw `role=…[name="…"]` form is **exact and
  case-sensitive** — only the higher-level helper relaxes it to a substring. So write the semantic rung
  as `role=<role>[name=/…/i]` (the observe-mode rule below), keep both strings in the runbook, and
  never "fix" one into the other: the mismatch belongs to the page, it is not a typo in your notes.
- **Drive a dependent cascade one step at a time.** Where one choice repopulates the next
  (sector → subsector → code), the later options do not exist until the earlier write has landed. This
  is the §6 "never batch across a server round-trip" rule in its most common shape: one action, one
  settle, then read the page again before choosing.
- **An ambiguous fallback rung is fail-closed — and it costs a live window.** A rung that matches
  **N>1** controls (a bare `role=radio[name="Yes"]` on a page with several yes/no questions) does
  **not** tick the wrong one: locator actions are strict, so the step raises and stops. That is the
  right failure and an expensive one — it burns the attended run you were spending, and live etiquette
  forbids retrying selectors against a third party's production system. Resolve ambiguity **offline**:
  scope each semantic rung to its own question or group, set `expect_unique`, and let `selector-audit`
  (below) fail it in CI instead of on the portal.
- **The instrumented fill path is also the EVIDENCE path — fix it, don't route around it.** The
  per-step trace and the per-page control inventory are emitted by the platform's own fill and
  snapshot tools. A run that drops to a lower-level driver — raw CDP, per-element refs, a hand-rolled
  click loop — still performs the actions but captures **nothing**: the pages the bot actually filled
  produce no inventory, so `browser-diff` files them **NOT_EXERCISED**, i.e. silently green. The
  workaround destroys the very evidence the live window was for. So treat a batch fill that reports
  *unavailable*, or that cannot see the page, as a **defect on the fill path** to fix before the next
  attended run — not a step to work around.

**Rule:** *observe first, declare second.* Every line of the runbook that says what a control **is** —
its widget kind, its id class, its accessible name — is a recorded observation of the real page;
anything you have not observed is an open unknown (§4d), not a guess you ship.

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

### Watch the live browser from Bot Activity

While a dispatched run is still open, the business Odoo's **Bot Activity** row gets
**Watch live** as soon as the first brokered `browser_*` tool opens a session (session
ids publish mid-run via `attach_browser_sessions`, not only at turn end). Use it when a
portal step stalls and the tool trace is opaque. After the agent turn ends, **Replay**
covers the same run for 48 h (the chip says *Replay available* only when a replay-view
bearer is wired — otherwise *Recording kept · replay not configured*). Clicking Replay
closes a lingering open session and opens the recording; if it says the recording is still
finalizing, wait a minute and retry. Both need that uplink tier claimed with `live-watch` +
`replay-view` credentials; a login-gate token alone cannot mint a viewer. If the row says
**No browser used** while Discuss shows an active filing, redeliver/converge the bot (stale
discuss plugin) or ask Oteny to wire the purpose tokens.

A run that **adopts** a human-login session (the owner signed in from the
start transition, so the bot inherited that browser) is watchable like any
other run. The one window that is
never watchable is the human sign-in itself: while the owner still has the login tab open,
Watch refuses. The live view is a bearer link, so possession is control, and the platform
will not hand out the tab where a person is typing an identity-provider password. Watching
opens the moment the owner clicks OK and the session passes to the bot.

### The workflow — `selector-audit` BEFORE, `browser-diff` AFTER

The platform captures, server-side and **PII-free**:

- a per-action trace of every native `browser_click` / `browser_type` your bot
  runs — the target it tried, how many elements matched, and the **actual**
  element the page rendered (id / name / role / aria-label / text / tag / type)
  when the broker captured it;
- a per-page **form-control inventory** (`page_snapshot`) after each successful
  `browser_snapshot` / `browser_navigate` — so an **observe walk that only
  snapshots and clicks** still leaves structured inventory for `browser-diff`.
  Scraping `~/.hermes/state.db` (conversation/tool blobs) is the **wrong**
  store for selector tuning — use account-key `traces` (`browser_traces` /
  `form_inventory`).

These are your own bot's real browser interactions on your **account-key dog-food surface** —
`traces --ref <bot>` is the selector-tuning eye. Box `shell` / `inspect` (you already have them)
  stay for Talent DBs, logs, and forensics — not a substitute for `browser-diff` input.

1. **`selector-audit --manifest <file>` (Oteny author CLI) — static, before a live run.** Scores each
   selector against the rules above and **exits non-zero if any is brittle** — the "is my runbook
   flexible enough for the real website?" check. Harden what it flags (add ladder rungs down to a
   semantic anchor, add `expect_unique`, add `option_fallbacks`) until it passes. No bot needed —
   run it in CI.
2. **Run the bot** — a scenario, a handed-off job, or an **observe walk**
   (snapshot/navigate/click/type) against the real (or stub) site so it emits
   `browser_traces` (step rows and/or `page_snapshot` inventories).
3. **`browser-diff --manifest <file> [--observed <traces.json> | --ref <ref>]` (Oteny author CLI) —
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

   A run driven by native `browser_click` / `browser_type` is graded differently, because its
   rows target a snapshot ref (`@e50`) and a ref matches no selector. Such a row is matched to a
   manifest field by the **identity** it resolved to (`el_id` / `el_name`), and it earns one of
   three further verdicts:
   - **CLICK_NO_OP** — the click reported success and the control is **still unchecked**. This is
     the silent class: the target was outside the viewport, or covered, or the handle was stale.
     Neither the tool result nor the accessibility snapshot can show it, so the run walks on past
     a field it never set. Treat it as a failed step.
   - **ACTION_FAILED** — the browser tool itself errored on that ref.
   - **VALUE_MISMATCH** — the field does not hold the text that was typed (compared by digest, so
     no value is ever read).

   Fixes are **proposed, never auto-applied** — you read them, decide, and edit **your own** skill's
   selector map + manifest. Read the raw rows yourself with `traces --ref <ref>` (author CLI — it
   returns a `browser_traces` list + a `browser_summary`) to tune the runbook by hand.
   `browser_summary.click_no_ops` is the one number that surfaces the silent class across a whole
   run, so check it before you call a green transcript green.

**`manifest-check --manifest <file> --stub-url <base>` (Oteny author CLI) — the third verb: is my double
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
(matched 1, never actioned) or a `MISSED` is **n=1 evidence**. A native click
or type that fails only after the *full* per-action timeout usually means a
genuinely stuck/slow page in that one run — an environmental transient — not a
broken selector. Before treating it as a bug: check whether the field is even
conditional (read the page, not your assumption), re-run once, and — fastest of
all — **reproduce the page mechanics offline against your own stub** (a real
headless browser is enough; no live infra) before spending a bring-up chasing
it. A selector that misses on *every* run is real (the `browser-diff` verdict
tells you which); a selector that misses once is a coin toss until a second run
confirms it.

### Observe mode — reconcile against the real portal before the first side-effect

`selector-audit` and `manifest-check` harden the runbook offline, and a stub run proves it drives
*your double* — but none of that has yet touched the **real** site. Before the bot's **first real
side-effect**, close that last gap with an **observe pass**: arm the submit-deny belt (§4f), hand the
bot a real record, and let it **walk the real portal all the way to — but never through — the
submit**. A snapshot/navigate/click/type walk is enough for inventory —
every successful snapshot/navigate lands a PII-free `page_snapshot` in
`traces` (structured broker capture — not something you scrape from
`state.db` over shell).
Then reconcile, iterating four steps until the diff is clean:

1. **Observe** — the belt-armed bot walks the real site; pull `traces --ref <bot>` (account key).
   Look at `browser_summary.pages_captured` / `controls_captured` and each `page_snapshot`'s
   `form_inventory` — that is your selector ground truth. **If a control has empty `id`/`name`,
   lock with `role=<role>[name=/…/i]` from `role` + `aria`/`label`/`text` — do not invent `#ids`.**
2. **Diff** — `browser-diff --manifest <file> --ref <bot>` (or `--observed <traces.json>`) scores
   the observed reality against your manifest (RENAMED / AMBIGUOUS / MISSED / …).
3. **Harden** — apply each proposed fix to **your own** selector map + manifest, **and back-port the
   observed reality into your stub** (the real ids *or* role+name anchors, the real option strings,
   any page the original walkthrough missed) so the **offline suite stays the authoritative
   regression net** — the stub, not a live run, is what every future deploy checks against.
   When live CDP or click-order evidence differs from the map, fold that evidence into
   the selector map in the same session. The stub then follows that map.
   Do not keep a second fill-tool path beside the live-derived native path.
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
- **The structural belt was `fill_form`-only, and that tool is gone.**
  `config_overrides["browser.submit_deny"]` still renders to
  `OTENY_BROWSER_SUBMIT_DENY`. The residual broker path honors it if
  anything still calls `POST …/fill_form`. The agent fill path is native
  `browser_click` / `browser_type`, and those calls are **not** refused
  by the belt. Rehearse with an operator watching. Do not click the
  irreversible button on a rehearsal bot. Do not add a new click-deny
  unless a later stage asks for it.
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

## 4g. There is no batch fill tool

`browser_fill_form` is gone from the control plane. Fill a page with
`browser_snapshot`, `browser_click`, and `browser_type`. Prefer
`role=group[name=…] >> role=radio[name=…]` and `role=combobox[name=…]`.
Do not write a form value through CDP or `Runtime.evaluate`.
Do not request the removed tool in `tools.required`.

**Draft-only is a rung on the ladder, not a permanent product lock.**
The government submit rides `browser_click`.
Submit-deny covered the removed batch tool only, so it does not cover
that click.
The honest response is to ship **draft-only first**: the bot saves a draft, and a
human clicks the government submit.

Ship it that way while the bot is still converging on the real site.
Do **not** treat it as the end state, and do **not** wait for a native click-deny
before you turn file-through back on.
The gate is the graduation ladder below, not one more browser belt.
A bot earns the real submit by climbing that ladder attended.

What stands behind a native submit click is the rest of the stack, not the belt.
That stack is the server-side data gate, the work-token check, a write-ahead
intent that fences a crash, the proof guard that refuses an unproven *done*
(§4b), and a tier-bound stub double that keeps a non-prod bot off the real site
(§4).
Name that residual out loud when you re-enable file-through, and rehearse it with
an operator watching.

**Rule:** *arm the belt on the rehearsal bot; leave the Talent's real-submit path intact.* The belt is
how you spend live runs converging selectors (§4e) and reconciling the real workflow (observe mode,
above) without ever filing for real — the same tier-below-the-Talent discipline as the stub doubles
(§4), but for the one bot you deliberately point at the live site.

## 4h. Size the in-progress SLA to bot work, not to the worst thing you can imagine

A dispatched run can die silently. The model stream hangs mid-turn, or the box's gateway
dies, and nothing tells your workflow. So the state machine needs a reaper: a per-state SLA
that hands an over-age in-progress record back to a human.

**The SLA is not a safety margin. It is the recovery time.** Until it fires, the record stays
claimed. If your workflow serializes bot work — a one-live-slot gate, a shared login, a single
browser session — a claimed record blocks every other queued item for exactly that long.

So size it to **bot work only**, from a measured run:

- Measure a healthy end-to-end run. Take 3–4x that as the SLA.
- Count no human wait. A wait for a person belongs in its own **human-owned** state, which
  carries no SLA at all — a reaper must never interrupt a person.
- Re-read the SLA whenever you add a step. An estimate ages; a measurement does not.

The failure this prevents is specific, and it is easy to write by accident. Barney's filing
state carried a 120-minute SLA, justified as "a long filing PLUS the SMS-2FA wait". But the
2FA wait happened in a different, human-owned state — the filing state only ever held bot
work, and a measured run was 10.5 minutes. So when a model stream hung, one dead run held the
single live slot for two hours, for work the gateway watchdog had already abandoned. The fix
was to size the SLA to the bot: 45 minutes.

Pin it with a test. An SLA is a number in a data file, and numbers drift upward every time
someone sees a slow run and does not measure it.

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

## 4i. An identifier that exists in only one country is a country-scoped PAIR

A national register number is not a field. It is a **(register, country, number)** triple, and
a DTO that carries only the number has silently hard-coded one jurisdiction.

The failure is quiet, because the identifier looks universal in the country you built for. A
Dutch client is identified by a KvK number plus a vestigingsnummer, and both were flat
required keys on the DTO — `severity: error` when empty. That was fine while every client was
Dutch. The moment the scope widened it blocked **every** foreign filing on its own, because no
foreign company has a Dutch KvK number: measured over the client's whole active fleet, 0 of 16
non-Dutch operators carried one, while 10 of 16 carried their own country's register number in
a field nothing read.

So carry the register **kind** and its **country** beside the number:

- A boolean-ish key that answers the form's own branching question (here: *"registered with
  the Dutch chamber of commerce?"*), driven by the **data**, never by the country — a foreign
  company **can** hold a domestic register number, and in this case the bot's own employer
  does.
- The domestic pair, required only on the domestic branch.
- The foreign register number **plus its country**, required only on the other branch.
- The identifier that crosses borders — here a VAT number — required on **both**.

**The guard must not turn into a hole.** Exactly one branch always demands a number. And a
domestic company with a *missing* domestic number is a **data gap, not a foreign company**:
answering the form's branching question with "not registered" would be a false statement on a
government record. Keep it blocked, and say so in the message.

Two traps worth stating in the code:

- **Never write a foreign number into the domestic field.** Register fields are often wired
  into something else — this one feeds Peppol e-invoicing under a country-scoped scheme, so a
  German number in the Dutch KvK field mints a wrong participant address.
- **Emit free-text register fields verbatim, never parsed.** Odoo's stock `company_registry`
  is free text and real databases hold values like `"KvK.nl 78219574 - Vestigings
  000045864136"`. The bot types what the DTO says.

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

*Worked example (Barney):* **`provision_barney.py --tier {local,test1,test2,prod}`** is the tier
provisioner — one command per CrewRadar tier (local holds the uplink tunnel; remote tiers exit after
wire-up). Launch configs: **`barney-provision-local`**, **`-test1`**, **`-test2`**, **`-prod`**, plus
**`barney-teardown`**. Stub portal = **`<tier base>/mfnl-stub`** on neutralized tiers; prod binds the
real meldloket. Then the Oteny author CLI
`test --ref <bot> --bundle <bundle> [--scenario <glob>]…` (see [`oteny-talent-dev-loop`](../../oteny-talent-dev-loop/SKILL.md))
runs the graded scenarios against the live, side-effect-safe bot — account key only, not a
private platform checkout.

## 5b. Do not encode a jurisdiction assumption in the triage rule

**The rule that raises the bot's work is a customer fact, not a design choice.** It decides
which records ever reach a human queue at all. Get it wrong in the narrowing direction and
the work does not appear late — it does not appear, and nothing reports the absence.

The worked example cost a real client seven legally-owed government filings. A Dutch
posted-worker notification is owed for a third-country worker who starts work on a ship that
**sails** in the Netherlands. The author reasoned that a Dutch portal must be for Dutch
companies, narrowed the triage rule to `operator_country = NL`, and shipped it. The client's
own production system had been running the un-narrowed rule for over a year, and the
narrowing would have suppressed seven cards worth about €8,000 of fine risk each.

**Prefer fail-open triage plus an explicit opt-out transition.** Raise the card, and let a
named human close it with a reason. An extra card in a queue costs a click. A missing
regulatory filing costs a fine and a compliance finding, and no one finds out until the
regulator does.

Three rules follow:

1. **Never answer the customer's domain question internally.** If a question was on a list
   for the customer, ask the customer. The whole defect above traces to one line in a build
   log: *"They answered the Ask-Kirsten list themselves."* Nine questions went on that list;
   eight were closed without asking, and the ninth became a shipped belt.
2. **Measure the narrowing before you ship it.** Count the records the rule would suppress,
   on the customer's real data, and put the number in the commit message. "It would suppress
   7 filings" is a decision. "It only applies to Dutch operators" is a belief.
3. **Read the customer's live configuration before you change it.** In this case production
   already held the answer: the live triage rule had three leaves and no country filter, and
   non-Dutch records had always been raised. The repo disagreed with the customer's running
   system, and the repo was wrong.

### A negative domain leaf is a fail-open/fail-closed decision, not a spelling choice

When a triage rule must exclude a class ("not an EEA national"), the exact leaf decides what
happens to a record with a **missing** value — and that is almost always the case you care
about, because missing data is common and silent.

Five natural spellings of the same English sentence were measured against 445 records with no
nationality. They gave **five different answers**, and four of them failed CLOSED:

| Leaf | A record with no value |
| --- | --- |
| `("stored_code_on_the_record", "not in", [codes])` | **matches — fail-open** ✅ |
| `("related_id.code", "not in", [codes])` | no match — fail-closed ⛔ |
| `("related_id.group_ids", "not in", [group])` | no match — fail-closed ⛔ |
| `("related_id.group_ids", "not any", …)` | no match — fail-closed ⛔ |
| `("related_id", "not in", [<ids>])` | partial, and ids are database-specific ⛔ |

Only the **stored scalar on the record itself** fails open, because Odoo emits the `OR IS
NULL` for it. So: name the exact leaf in the code comment, say which way it fails, and write
a test that asserts a record with a missing value still matches. Also beware a stock country
group that looks right and is not — an EU-27 group silently omits Iceland, Liechtenstein,
Norway and Switzerland, and a "Europe prefix" group silently *adds* the United Kingdom, whose
nationals are third-country nationals since Brexit.

**A rule that only ever CREATES needs its inputs in `@api.depends`.** Auto-add machinery
typically creates a work item and never retries. So a field the domain reads must also be a
dependency of the compute that fires it, or a value corrected the next day raises nothing at
all. That is a second, quieter way for fail-closed triage to lose work.

## 6. The bot as a workflow executor (checks 5 + 6)

A business bot need not only *answer* a team in chat; it can be the **executor of a
workflow transition** — one isolated agent turn per bot-owned transition. The pattern: the
business's Odoo owns a state machine, and specific states/transitions belong to the bot;
each bot-owned record is driven through them by a **fresh isolated turn** — its own session,
not the team's running conversation.

**Scope it against the ERP's own assistant, not on top of it.** Most business customers
already run their ERP's built-in AI (in Odoo, an `ai.agent`, often on a cron). That
assistant answers questions and enriches records **inside** the system, and it should keep
doing so — do **not** rebuild it as a Talent to show off capability. Your bot earns its
place on the other side of a line the customer can feel: it **owns a transition** and the
responsibility for its outcome, usually with work **outside** the ERP (a portal, a mailbox,
a third-party system) under a named human's authorization. Two practical tests when you are
deciding whether something belongs in your Talent at all:

| The ERP's own assistant | Your business bot |
| --- | --- |
| Answers a question about a record | **Advances** a record through a state it owns |
| Runs inside the ERP's session and rights | Runs isolated, with its **own** login, mailbox, and machine |
| Nobody is accountable for a wrong answer beyond re-asking | A **named** human delegated the job and can be shown proof of what was done |

Getting this wrong is expensive in both directions: a Talent that duplicates the ERP
assistant competes with the customer's existing investment and is judged as a worse
chatbot, while a bot that owns a transition but leaves no proof trail cannot be delegated
to at all (see §4b fail-closed and §7 owner visibility).

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
  a hard-coded reference. **Steer the claim `bot_prompt` uplink-first:** tell the agent to
  `search_read` that record **by id** in one call (DTO / JSON field only) — never "service data
  below" or any phrasing that invites inventing filters, domains, or payloads from chat. The
  channel message stays identity-only; improvisation is a PII leak and a wrong-record risk.
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
- **Transition buttons name the action, not the result.** In the client's Odoo workflow, the
  transition `name` is the form-header button people click. Name **what the clicker does**
  (imperative: `Continue after login`, `Approve & submit`), never the destination state or a
  completed result (`Needs login`, `Login complete — continue`, bare `Confirmed`). States may
  still describe the situation (`Needs Login`). Bot-driven transitions (`bot_role` claim /
  work / escalate, or only the bot takes them) prefix the bot's display name
  (`<Bot>: ask HR to log in`, `<Bot>: mark filed`) so a human scanning the strip never
  confuses a harness exit for their own next step. Humans do not see `bot_role`
  `claim` / `work` buttons. Lowest sequence = primary button — put the
  state's **owner's** intended next action first.
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
- **Final replies: write `Service #N` / `record #N`, not URLs.** The Discuss adapter turns those
  mentions into clickable **same-origin** `/web#…` form links from the dispatch's work-claim
  model (never the bot's uplink tunnel host). Keep Talent prose free of hardcoded `/web#…`
  links (they break across DBs / tunnels). Approval summaries may use markdown pipe tables —
  Discuss renders them as HTML `<table>`.

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
(trim mid-run narration) over an ever-larger ceiling — a smaller budget is a
tighter safety bound.

### Fill the page the bot can see — click, type, snapshot

The biggest lever on a long browser-driven run is **doing fewer round-trips**, and the finest-grained
trap is treating every field as its own observe-act-verify cycle. Each cycle is a browser round-trip
plus a model call; a thirty-field form becomes sixty serial steps and minutes of wall-clock — enough
to run into the session cap. There is no batch fill tool. **One native
action at a time:**

- **Snapshot, then click or type the control the snapshot shows.** Prefer
  `role=group[name=…] >> role=radio[name=…]` and `role=combobox[name=…]`.
  A live accessible name may carry a trailing space — match the question
  text, do not require an exact quoted name. Do not snapshot after every
  radio or type just to confirm the fill. Snapshot before the named
  advance. Do not write `.checked` or
  `element.value` through CDP. Ship the page's **selector map in the
  skill** (a `references/` file). Name each page's advance control
  (`Next` / `OK` / a later *Summary*) so the model copies it. If the
  page does not change after that click, one native retry. Then halt.
- **Dropdowns: click the combobox, then the option.** Use the option's
  **exact visible text**. Copy it from the open list. Do not guess a
  translation. Do not write a hidden input. A cascade whose next list
  arrives from the server stays one action at a time.
- **Never batch across a server round-trip:** a search-then-pick, or a
  cascade where each choice populates the next. Those stay one action
  at a time.
- **Keep the page-boundary verify and the pre-commit read.** Snapshot
  before each named advance. Always take a fresh full read immediately
  before the irreversible action (§4b) and before reading any
  confirmation value off the page. Narrate at start / before that
  irreversible step / outcome, not per page.

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
- **Do not silently overwrite a computed SLA deadline** after a bot-to-human handoff.
  A write that freezes the displayed date can drop the stored rule. Review first.

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
  Before you call `browser_needs_login`, write **one diagnosis line** that names the URL you saw and
  the `controls` count from the last snapshot you already have. A false wall (empty first capture) and
  a real login page look the same in the trace without that line. Do not snapshot again just to log.
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
  client-side as tier config, exactly like a portal connection bind, so the test tier lands on its stub and
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
- **Name the post-login bot state after the job, not the login.** After the human
  marks login done, the bot-owned in-progress state's `name` is the current job
  (draft or file). The origin Bot Activity strip echoes that `name`. Do not leave
  a signing-in label on the state that runs after login is finished.
- **After Save, a dead browser player is a platform bug.** Do not tell the author
  to clear a Steel / browser profile. The broker donates the live login session
  and the next persist-true create adopts it. Authors do **not** invent client-side
  sleeps. A later queued create adopts the linger sibling only after the
  first turn has posted `/linger`. Mid-turn (`in_turn`) is not adoptable.
  After 10 minutes idle (default inactivity), a new login is normal. If a
  resume still hits the wall after a completed human login, that is belt-2
  escalate once (§ below), not a second SMS. Login lives **inside** the
  human start transition. Do not ship a side header that mints a session
  and does not advance the record.
- **Two stores.** `list_logins` / `connect_login` / `disconnect_login` are
  website passwords. `browser_list_profile` / `browser_save_profile` /
  `browser_clear_profile` are the cookie snapshot. Forget a password with
  `disconnect_login`. Clear the jar with `browser_clear_profile` or the
  owner portal Clear on OtenyBot Details. Never print a profile id.
  After the owner saves a login, a later run that still hits a wall is a
  **platform** bug. Do not tell the author to clear a browser profile
  unless the owner asked to start signed out.
- **Ask preflight: consult the one-live-slot gate before persist-true
  preflight.** When a sibling holds the slot, paint the queue note
  (`slot_queued`). Confirm queues. That paint is not `busy`. Do not mint
  while the sibling holds the slot. When the slot is free, start one
  persist-true window first (restore when a jar exists). Classify with
  the platform session status (`logged_in` / `login_wall` / `busy`). Then
  paint: signed-in confirms in the mode the form asked (a draft path does
  not submit); a wall keeps **Open login browser**; busy waits.
  **Open login browser** attaches the live viewer to that same persist-true
  writer. Do not mint a second persist-true window while the first is live.
- **Persist, attach, and 409.** The platform sets persist and attach. You
  do not pass those flags. A signed-in / live-view window is persist-true
  and attaches the snapshot. A scheduled or isolated window is
  persist-false and still attaches. A page-read (`web_extract`) is
  persist-false and attach-false, and it may sit beside a writer. At most
  one persist-true window is live. A second persist-true window **adopts**
  that live window. Persist-false plus attach while a writer is live
  returns HTTP 409 `session_jar_in_use`. A sixth new window returns HTTP
  409 `session_cap`. The plugin does not retry 409. Treat 409 as a stop,
  then wait or ask the owner.
- **Two ceilings, not “max 1 browser”.** The per-bot new-window cap is 5
  (`session_cap`). A separate fleet idle ceiling of 4 closes the oldest
  idle window. That idle close is not a 409. One live isolated turn per
  bot is a **workflow** rule (this section below), not a browser cap of 1.
- **Newest Open wins; two ceilings.** A second **Open login browser** closes the
  first tab. The owner must sign in in the **latest** window — Save donates that
  tab only. Portal OTP budgets stay a **human** rule (e.g. ≤3 SMS/day on some
  IdPs; abort if the code does not arrive; never retry into lockout). The
  platform separately hard-stops at **12 login-handoff mints per 24 hours**
  (`login_mint_max_per_window`, HTTP `429` `mint_rate_exceeded`) so a stolen
  key cannot drain Steel. Do not treat 12 as the portal OTP budget, and do not
  encode a client-specific “3” in platform code.
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

#### The attended login is a PHASE — mutually exclusive with runs

The single-user demo hides this: a business bot serves a **team**, and several people hand it work, approve
it and sign in for it at random times. The moment two of them overlap, the login gate stops being a tidy
hand-off and becomes a **shared-resource problem**, because the human's login browser and the bot's run
browser are the same browser tenant and the same cookie profile. Saving a login releases the tenant's other
sessions so its authenticated jar lands last (see the platform's finalize sweep) — which means a run that
happens to be filing at that moment loses its browser. Fail-closed, but a spurious failure on someone's
legitimate work, every time two colleagues are busy at once.

So treat the login not as a step but as a **phase**, and make the phases take turns:

> Per bot: the **RUN phase** (isolated turns that use the browser) and the **DANCE phase** (mint → human
> signs in → save) are **mutually exclusive**. At save time the only open sessions are idle ones, so the
> platform's sweep has no live collateral **by construction** rather than by luck.

Four rules make that true. **Every one of them must be bounded by wall clock** — see the liveness rule below.

- **Latch the bot for the duration of the dance (TTL'd).** Starting a dance sets a per-bot latch with an
  expiry (match it to the platform's handoff window — a dance that outlives the browser session it minted
  is over regardless). While it is held, **no new run is dispatched and no dispatched run may start**.
  Deferred is **never failed**: the record keeps its state and its claim epoch, and your dispatch cron
  re-drives it — so a defer costs one tick and nobody sees an error.
- **Latching future dispatches is not enough — gate the run's START too.** A latch cannot un-post a message
  already sitting in the channel (posted moments before the latch, or re-posted by a recovery belt while the
  gateway was down). Refuse it at the **run-consume** step instead — the deterministic checkpoint your
  dispatcher hits *before any model activity*. Refusing there is free: the dispatcher is fail-closed and
  drops the message without starting a turn, and your re-post belt re-fires it once the dance is over. This
  is the rule that turns "mutually exclusive" from a hope into a guarantee.
- **Refuse a dance while a run is live — and offer an explicit interrupt.** A person clicking *sign in*
  while the bot is mid-run should be told so, with the service named and the wait bounded. Give them a
  **separate, confirm-gated "interrupt and sign in" button** rather than silently overriding: the collision
  is then *chosen*, with its price on the label ("the running job loses its browser and goes back to the
  team"), not something that just happens to a colleague.
- **Supersede concurrent dances, never queue them.** Two people can start a dance at once (two screens, one
  leaked tab). Let the **newest click win** and release the older session; a takeover never waits, so a
  forgotten tab can never block anyone. Critically, **the superseded screen's save must fail loudly** — if
  it silently succeeds it reports the *later* dance's login as its own and advances the workflow on a login
  it never completed, which inverts the whole finalize-before-advance belt. The platform returns `409
  superseded`; surface its message verbatim and leave the record where it is. (Queueing instead is worse
  than it looks: many identity providers rate-limit one-time codes hard — a queued second dance burns one of
  a small daily allowance and can lock the shared account.)
- **Give the latch an OWNER, or every fence above is decorative.** This is the one that will bite you, and
  it is invisible in a single-user demo. The latch is per-**bot**; the screens that release it are
  per-**user** and per-**record**. So "stop the dance" must mean "stop **my** dance": mint an **epoch token**
  at every latch-start, hand it to the screen that took it, and make the release a **compare-and-clear**
  under the same mutex the start uses. Without it, the ordinary two-user path silently defeats P1 — a
  colleague clicking Cancel (or OK) on an unrelated record releases *your* in-flight sign-in, a run starts on
  the shared profile, and your save then sweeps it. No force button, no confirm, no warning. Three rules
  fall out: a screen that **never started** a dance releases nothing; a **superseded** screen holds a stale
  token and releases nothing; and the release must take the mutex, or a stop that read a matching token can
  still land its write *after* a takeover committed and destroy the new dance's latch. Storing "who started
  it" for the error message is **not** the same as enforcing ownership — if no code path reads the field, it
  is decoration.

#### One live isolated turn per bot — derive the slot from workflow state

A team will hand the bot several records in one minute. Process ("hand one at a time") is not a
control. The engine already has a gate at dispatch and at run-start consume. Use that gate. Do
**not** add a second occupancy record on the bot (fields, CAS, TTL). A TTL that expires while a
slow run is still live admits a second run. A missed release strands the bot forever.

Derive the slot from the records themselves:

- Flag login-park and login-resume states `bot_login_hold` in the workflow XML.
- Defer a **fresh** queue record when another record of the same workflow is claimed, or sits
  in a login-hold state.
- **Exclude-self:** a record in a login-hold state is never blocked by its own hold. That is the
  whole priority system — the parked record's resume is always admitted; fresh work is not. Two
  records both parked in a login-hold state must not deadlock each other.
- **Strict at dispatch** for fresh work: any other claimed peer defers (the extra card stays in
  the bot's queue state — visible, not secretly claimed).
- **Relaxed at consume / re-post / login-hold resume:** only a consumed, in-SLA peer defers
  (reuse the engine's live-claim predicate). A REPEATABLE READ race may post twice; the consume
  fence plus the box serializer admit one browser Open. A second Open is what burns a login
  code — that happens at consume, never at post.
- **Drain** is one hook: a record left a slot-holding state (`in_progress` or `bot_login_hold`)
  → try the oldest queued peer of the same workflow. The existing dispatch cron is the
  correctness belt. No per-exit trigger table. No new clock.

A second business bot inherits the control by flagging its login-park states and calling the
same predicate from `_bot_dispatch_gate`. Do not put client names in the engine.

Prove two overlapping Hands on the live queue. A graded scenario that waits
`done_when` serializes itself, so a green `oteny test` does not prove the
second Hand stayed queued. Two wizard saves a few seconds apart prove
**sequential defer** only. They do not open a REPEATABLE READ race. A true
overlap proof drives two `/json/2/` claims from two threads at the same
instant. Do not treat a green scenario as proof two Hands cannot race.

#### Humans and runs collide on the RECORD too — refuse a transition out from under a live run

The same "several people at once" reality has a second, sharper edge that has nothing to do with browsers.
An irreversible act (the submit) and the record catching up with it (write the proof, advance the state) are
**seconds apart**. A person clicking *Cancel* in that window leaves a real, filed, legally-binding side
effect behind a record that says cancelled — and there is no un-submit.

So **refuse human transitions out of a bot-owned in-progress state while a claim is live**, at your workflow
engine's transition-execution choke point — never per-workflow, and never in a view: it must hold for the
button click *and* the confirm, because a run can start while the screen sits open. The bot's own advances
and the timeout reaper go through the claim/token door instead, so they need no exclusion by role — they are
structurally on the other side of this fence.

#### The liveness rule — no fence may outlive its own bound

Every fence above **blocks somebody**, so every one of them must be **guaranteed to end by wall clock alone**,
with no cron, no sweep and no operator. This is not polish; it is what separates a fence from a wedge:

- Define "a run is LIVE" **once**, and key every fence on that one predicate: the record is claimed, its run
  was actually **consumed** (a claimed-but-never-started dispatch is a message waiting to be read, possibly
  by a dead gateway — never block a human on one), **and** the run is still inside its state's timeout SLA.
- **Past the SLA, the run is not live** — the reaper owns it. Treating a reaper-eligible zombie as live would
  park a human behind a job that is already over.
- **A state with no SLA has no bound, so its claim is never live.** An unbounded block is worse than no
  block. Liveness outranks the fence.
- **Never hold a lock while waiting on another lock.** If your dispatch path takes a per-bot mutex, take it
  **without waiting** (try-lock → defer) and always in the same order relative to row locks. A dispatch that
  defers comes back in three minutes; a dispatch that waits can sit in a cycle.
- **Every refusal message names its own end** ("wait a few minutes; if it never finishes it is handed back
  automatically within N minutes"). A refusal whose end the user cannot see is indistinguishable from a hang,
  and they will go looking for a way around it.

Grade this with a **randomized interleaving test**: seed a handful of records in mixed states, drive a few
hundred operations from a **seeded** RNG (hand-offs, approvals, dances, forced dances, cancels, dispatch
ticks, reaper ticks, time jumps), and assert the invariants after **every** step — never two live runs on one
bot; never a dispatch while latched; never a non-forced dance while a run is live; no human transition out of
a live claim; no screen releasing a dance it does not own; and, at the end, that the fleet **drains** (jump
every clock past every bound and assert nothing is left in an in-progress state). Print the seed on failure.
Jump time; never sleep.

Two things decide whether that test is worth anything, and both are easy to get wrong:

- **Model MORE THAN ONE user and MORE THAN ONE open screen.** A walk with a single user and a single wizard
  slot cannot generate the two-screen case — which is the whole reason supersede and the epoch token exist.
  It will grade an unowned latch **green**. (This is not hypothetical: it is exactly how the ownership bug
  above survived its first review.)
- **Assert the test's own coverage.** A seed that wandered only through idle states passes every invariant
  vacuously. Require the log to contain each interesting event — a refusal, a takeover, a non-owning cancel
  — and fail if the walk never reached them. A green that proves nothing is worse than a red.

And when you fix a concurrency bug, **mutation-test the fix**: re-introduce the bug, confirm the new test
goes red, then restore. A concurrency test you have never seen fail is a concurrency test you do not have.

**Your in-suite tests cannot prove a lock.** Odoo runs every test on ONE shared cursor, and a Postgres
session never conflicts with itself — so in-suite, a try-lock always succeeds and a row lock never
contends. Those tests prove your *logic*; they say nothing about your *lock*. Prove the lock in a small
standalone script that opens **two real connections** and races them through a start barrier (run it against
a disposable database — it commits). Two things it will teach you that the suite cannot:

- **Odoo cursors run REPEATABLE READ**, not READ COMMITTED. A transaction's snapshot is taken at its first
  read, so "take the lock, then re-read" does **not** see a commit that landed while you were waiting. If
  your design assumed lock-then-read-committed-truth, it is wrong.
- **What saves you is the serialization failure, not the re-read.** The blocked writer's own `write` raises
  `SerializationFailure`, and Odoo's RPC layer retries the whole request on a fresh transaction — which
  *does* read committed truth. Design for that path explicitly; it is the same one the record-claim CAS
  relies on.

Then state the residual honestly. A lock acquired *after* a transaction's snapshot leaves a window the
width of that transaction's prologue; make the outcome in that window fail-closed, measure it, and write it
down — an unstated residual is the one that surprises somebody at 2am.

**How the client's own system reaches Oteny (the client-integration hook).** The mint-on-click and the
attended-refresh above are triggered by the **client's own system** (its ERP / back-office) calling Oteny
**server-to-server** — not by the bot. That call rides a single **public HTTPS lane** the platform
operates, and the contract is deliberately tiny: **one base URL + one `Authorization: Bearer <token>`
header**, JSON body, synchronous response. The bearer is a **purpose-scoped client-integration
credential** — issued per client-integration, independently revocable, and **distinct from any model /
spend token** the bot uses — so exposing this hook can never leak model budget, and rotating it never
disturbs the bot. Treat the value like any secret: it lives in the client system's own secret store
(never in chat, never on the bot's box), and the synchronous response (e.g. an ephemeral human-login
viewer URL) is opened once and **never persisted or posted into a channel**. You do not build this lane —
the platform provides it; you only need to know the hook is *one bearer header to one URL*, so a client
integration is a config value, not a bespoke protocol.

**Rebind the client's credential every time the bot is (re)delivered — a stale bind fails GREEN.** The
client-integration credential authenticates a *specific bot instance*; a dev loop that rebuilds or
replaces its bot (a durable-slot rebuild, a fresh commission) silently strands a hand-wired credential on
the PREVIOUS instance. The failure is the worst kind: every step still reports success — the login
session mints, the human signs in, the save confirms — but the authenticated session lands in the *old*
bot's browser profile, and the *current* bot still hits the wall. Nothing platform-side can detect it
(the platform cannot know which bot the client's workflow meant). So the pattern is structural
freshness, not detection: at every delivery the platform mints a fresh purpose-scoped credential for the
delivered bot and exposes it as a **one-shot claim** on the commissioning request (claimed once, then
blanked); the dev-loop launcher claims it and **rewrites the client system's integration config on every run**.
Hand-wiring stays only for prod cutovers — and even there, rotate the credential as part of any bot
replacement, never after it.

### Watching an inbox for the outcome — the mailbox stub double

A workflow often completes only when a **counterparty replies** — an email confirming or rejecting
what the bot filed. A bot that **polls an inbox** for that reply is a side-effecting integration like
any other, so it takes the **same stub-double tier trick as a portal (§4)**: prod mounts the real
mailbox; **every non-prod tier mounts a stub inbox**, and the same Talent ships unchanged across
tiers.

- **The stub inbox serves seeded fixtures.** On non-prod, the mailbox poll points — via a tier-bound
  the portal connection's env var (§4c) — at a **stub inbox** shaped like the real mail API, serving seeded
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
  moment the bot first acts. Re-provisioning a **new** tenant ref must **bind** the Discuss
  channel to that ref (`oteny.bot.bind_discuss_channel`) — bare ensure alone can leave the
  channel on an orphan sibling while Hand-to-Barney stays mute. On a **fresh** box (new
  `uplink_ref` while the seeded xmlid row still carries the old ref), `ensure_bot` /
  `bind_discuss_channel` **rehome** that same-user seed onto the live ref and collapse any
  channel-holding fork — domain dispatch resolves the xmlid, so a mute seed + live fork is a
  hard fail mode, not a recoverable split.
- **Mute Discuss → `oteny traces`.** If the channel is silent, read
  `oteny traces --ref <ref>` for `uplink_status` (`auth_failed` = remint/re-provision). Mint
  rotates the ERP key; website login is not the Talent debug path.
- **Best-effort, never fatal.** Recording the activity is best-effort — a logging failure
  **must not fail the transition** the bot just did. The write-back wraps the real work; if
  the log write throws, the work still stands.
- **The trust model.** The log is the bot's **self-report**, scoped to its own bot identity
  (matched by its uplink reference — an uplink reaches only its own owner's Odoo, so there is
  no cross-tenant reach). The origin soft-ref is advisory and unvalidated. The owner reviews
  the sessions from a **smart button on the record** the bot worked, or a per-bot activity
  view — every exchange, in their own Odoo, without touching the bot host.
- **Surface the last isolated-turn outcome on the origin record.** A smart button that
  opens the log is not enough for day-to-day operators. Put the latest session's outcome
  pill, a short response (or an honest still-working sentence), the start time, the
  duration, and a link to that session **on the origin form**. The team then does not
  need the Discuss channel to know what the bot just did. Keep the chrome generic
  (`oteny.bot.session` helpers such as `search_latest_for_origin`). Place the strip in
  the consuming app, gated on that app's own workflow. Do not hard-code a client name
  in the generic bot addon. Also link the bot's Discuss home channel from the origin
  strip and the session form. Resolve it from `oteny.bot.discuss_channel_id` or the
  client's xmlid. Do not hard-code a channel id. Reload the origin form to see a new
  session; do not add a live ticker unless the session model writes `bus.bus`.
- **Render the short response as HTML from markdown — never as raw text.** The bot's
  reply is markdown (`**bold**`, bullet lists, links). Discuss shows it formatted
  because the platform's Discuss adapter converts markdown to HTML before posting.
  A `oteny.bot.session.response`/`request` field read straight into a `fields.Text`
  widget shows the literal `**`/`-` markers instead — the origin strip must render
  it the same way Discuss does, or it looks broken next to the channel. Add a small
  markdown-to-HTML helper (e.g. `oteny.bot.session._markdown_to_html`, using a
  markdown library with `nl2br`/`hard_wrap` so a single newline still breaks the
  line) and expose the truncated preview as `fields.Html`, not `fields.Text`.
  `html_sanitize()` the output — a bot's own markdown can still carry inline HTML.
- **Open the Discuss link in a new tab, not the current one.** Discuss carries no
  Odoo breadcrumb, so a same-tab open strands the operator with no path back to the
  origin form they came from. `discuss.channel._get_access_action()` returns
  `target: "self"`; override it to `target: "new"` before returning the action from
  your own "open the filing channel" button.
- **Show who owns the current workflow state on that same strip.** Encode bot vs
  human ownership in the state (`is_owned_by_bot`), not the responsible team. The
  header line must lead with the current state name and a bot/human owner pill.
  A last-run **OK** pill without that pair is read as "the bot still owns this
  job" after a hand-back (login wall, draft review, escalate).
- **Write the operator manual as a state table, not a staff runbook.** For each
  workflow state, list the **exact UI label**, who owns it (human team vs bot),
  what they click, and what happens next. Mark parked bot work (for example a
  watch state with no mailbox poll, or a hidden file-through button) as **not
  live**, so operators do not wait for a bot that will not act. Keep staff CLI,
  box access, and submit-deny out of that table. Put author/dev loop docs in a
  different file from the operator manual.

## 7b. A Talent coupled to a client ERP rides that ERP's branch

Your Talent and the client's ERP module are **one deployable thing**, not two. A step that
advances a named transition, or reads a named key off the DTO, only works against a database
that has them. Ship them on two clocks and you get the two failure shapes that clock skew
always gives you: the Talent behind the schema (a step that no longer matches the form), or
the Talent ahead of it (a step naming a field the database has never heard of).

**So pin each bot to the branch its own ERP deployment is built from.** If the client
promotes through branches — dev, staging, production — the bot follows the same branch, and
the two move together by construction.

What that buys, beyond the obvious:

- **No release tag.** The tag-and-remember-to-cut-it ritual disappears, and with it the
  question "which bundle is this bot actually running?" — the tier answers it.
- **The acceptance freeze becomes free.** A staging bot changes only when somebody promotes
  to staging, so **the pipeline is the freeze.** No frozen branch to cut, and no un-freeze
  to forget — and that un-freeze was a genuine silent-staleness trap, because a bot on a
  stopped branch keeps serving the old bundle and looks perfectly healthy.
- **The pin is derivable, not stored.** A reviewer answers "what is this bot running?" from
  the tier, instead of from a state file that can drift.

**Read the ref from the deployment map, never from the operator's checkout.** This is the
trap, and it is easy to write by accident. A provisioning script that takes the ref from
`git rev-parse --abbrev-ref HEAD` pins whatever branch the operator happens to be sitting
on — so provisioning **production** from a laptop on the dev branch quietly commissions the
production bot to follow **dev**, and every dev push then reaches the live bot. The map
almost always already exists somewhere in the repo (a `servers.json`, a deploy config); read
it, and fail loudly when a tier has no branch rather than falling back to the checkout.

**Two residuals to name in your own docs, because neither has a gate:**

1. **The bot clones the remote.** An unpushed commit cannot reach it, however green the
   local tests are.
2. **Delivery is usually a poll, and it does not know when the ERP finished deploying.**
   Between a merge and a green build the Talent can be ahead of the schema. You can engineer
   this away — have the bundle declare the module versions it needs and defer delivery until
   the tier reports them — but weigh it: a delivery that defers and *stays* deferred is a
   new silent-staleness failure of its own. If the client's releases land out of hours and
   the build is quick, accepting the window and writing "promote before the session, not
   during it" into the runbook is the honest trade.

## 8. A client's correction lands in four places at once

When the customer corrects a business rule, the correction is **never** one edit. It lands in
four places, and they are owned by different people on different clocks:

| Place | What it holds | Clock |
| --- | --- | --- |
| **The rule** | the triage domain / auto-add that raises the work | module version |
| **The DTO guard** | the `severity: error` set that gates the hand-off | module version |
| **The Talent instructions** | what the bot is told to do on the page | Talent delivery |
| **The human manual** | what the operator reads before clicking | doc repo, or the customer's own wiki |

**Miss one and the bot and the humans disagree** about the same record — which is worse than
either being wrong alone, because each side trusts the other.

Two failure shapes to watch for:

- **The rule changes and the manual does not.** The operator reads that a card only appears
  for case A, sees one for case B, and closes it as a mistake. You have automated a wrong
  answer into a human's habit.
- **The manual changes and the Talent does not.** The bot keeps refusing work the operator has
  been told to hand it, and the refusal message cites a reason that is no longer true.

There is usually a **fifth** place, and it is the easiest to forget: a page in the customer's
own knowledge base, which no lint of yours can reach. Name it explicitly in the change list
and get the customer to apply the same edit there, or the two will drift on the next
correction.

**Sentences that do two jobs are where this breaks.** One instruction in the Talent read
*"You never reason about countries."* It was doing two jobs: *never decide whether the filing
is in scope* (still true, and load-bearing) and *never choose which dropdown option means this
country* (now exactly the bot's job). Deleting it would license scope-guessing; keeping it
would block the new behaviour. **Split the sentence and write both halves**, or a model will
latch onto whichever half suits the turn.

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
- **Triage fail-open** — the rule that raises the bot's work carries **no unmeasured
  jurisdiction or eligibility narrowing**. Every narrowing is an explicit human transition
  with a reason, its suppressed-record count is measured on the customer's real data before
  it ships, and a negative domain leaf is tested against a record with a **missing** value.
  (PASS/FAIL)
- **Deploy coupling** — a Talent that names a field, state or transition of a client
  backend is pinned to the **branch that backend is built from**, and the ref is read from
  the deployment map rather than the operator's checkout. (PASS/FAIL / N/A)
- **Branching forms** — every branch the data plane can produce is rendered in the double,
  selected by its own fixture, and listed in the selector manifest. A branch nobody has walked
  is marked **UNMAPPED** in both twins, never left silently absent. (PASS/FAIL / N/A)
- **Owner-visibility** — the bot records each exchange as a session in the owner's Odoo over
  `/json/2/` (soft-linked to the record, idempotent bot identity, best-effort so a log
  failure can't fail the work); reviewable from a smart button on the record and from a
  last-session strip on the origin form. (PASS/FAIL / N/A)

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
