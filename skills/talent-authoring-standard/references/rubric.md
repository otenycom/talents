# The rubric — 14 checks, in full

Each check is PASS / FAIL / N/A. `SKILL.md` carries a one-line digest of every check;
this file carries the full text, the inspection commands, and the examples. Grade a
bundle by running each check against the folder. Checks 4 and 9 add **context-aware
reads** (not keyword matches) — see [copy-and-tools.md](copy-and-tools.md).

### 1. Package structure
- `SKILL.md` with valid agentskills.io frontmatter (`name`, `description`,
  `version`). `description` is a **sharp ≤60-char trigger** (the router rule above).
- `agent-profile.yaml` (voice/persona, `channel_prompt` text, toolset
  *contribution*, baked|purchased, price). **`model_tier` is honored** — it sets the
  bot's default model (an operator override still wins). Declare the cheapest tier the
  job passes its scenarios (incl. red) on — **unless** the job performs an irreversible
  external side effect or makes consequential claims (filings, payments, submissions),
  in which case declare `model_tier: builder` as the floor (see
  [references/business-bot-pattern.md](business-bot-pattern.md) "Choosing the
  model tier", D235). A Talent **must** ship one.
- Optional `requires: {substrate, min_tier}` — a hardware need; lint check 15 enforces
  vm→max. Absent = any tier.
- Optional `task_escalations:` — steer a fabrication-prone **task** to a stronger model
  (never a whole-bot floor; lint check 16). Schema + rules:
  [references/model-escalation.md](model-escalation.md).
- Optional `doc_twin:` on a selector manifest — names its human-readable per-page map;
  **lint check 17** then FAILs on any drift between the twin `#id`/attribute field+submit
  selectors (see [references/business-bot-pattern.md](business-bot-pattern.md) §4e).
- `required_artifacts.yaml` present and complete (see above).
- `references/` for on-demand detail; `scripts/` for deterministic helpers (both
  optional). A multi-skill Talent: each composing skill independently valid.
- **Composition discipline (multi-skill Talents):** each composing skill owns **one**
  concern (engine / method / voice / visual / onboarding); they **cross-reference,
  never duplicate** — one canonical home per fact (SQL mechanics in one `references/`;
  the method math in the method skill; the welcome in onboarding). A master engine skill
  **triages and dispatches** to the others (see check 11).
- **Lean body, native sizing** (the sizing rule above); the first-run drill lives in
  `references/first-run.md`, not the body. Detail is one level deep in `references/`.

### 2. Setup goal well-defined
- Every artifact the bot needs is in `required_artifacts.yaml` with a **concrete,
  checkable** condition (a path, table names, field names) — no vague "set up
  correctly." If you can't write a one-line check for it, it's underspecified.

### 3. First-run is mechanical, idempotent, in `references/`, and approval-clean
Six graded rules — drill in **`references/first-run.md`** (not the body, D57);
declared scripts only (no improvised exec); cron pins `model`+`provider` as a
persona alias; one `sqlite3` per terminal call; readiness scripts are pure-stdlib
and never hard-fail (D237); third-party feature scripts ship a uv lock +
`talent-run`; collapse the per-turn preamble to one preflight (D38). Failure
chains + worked examples:
[`references/first-run-authoring.md`](first-run-authoring.md).

### 4. PII / secrets clean (method, not person) — and generic, not baked for one body
No personal data, tokens, or hardcoded chat/user ids. Method facts stay; body/
account specifics go. Owner settings live in the profile/override (D34/D53), not
the bundle — delivered files carry only generic defaults. Numbers that remain
must fit any tenant (%/relative, per-unit, derived from the profile) — never
tuned to one source user. Gate:
``grep -riE 'name-of-source-user|real_token|DEFAULT_TOKEN|[0-9]{8,}|api[_-]?key' <bundle>``
returns nothing meaningful.

### 5. Routing declared (not hand-edited into SOUL)
- A `routing` declaration: a per-group `channel_prompt` (persona **and** a "load
  `<skill>` first" directive) + an optional one-line DM hint. The reconciler
  applies it; the bundle never string-edits SOUL or `config.yaml` itself.
- Per-bot **voice lives in the skill**, not a global SOUL.
- Group/chat ids are **looked up at runtime** (from `channel_directory.json`),
  never hardcoded.
- **Scoped business bots usually route to Odoo Discuss** (Telegram allowed when that is
  the team's surface) — and shift the toolset (checks 1 + 9), data plane (`odoo_client` +
  named `connections:`, channel-agnostic — checks 2 + 6), and tests (check 14) accordingly;
  the full authoring delta is [`references/business-bot-pattern.md`](business-bot-pattern.md).
- **Every outside system is a named `connections:` entry**, and there are four kinds. A
  `kind: saas` entry names a third-party account the OWNER grants, so the platform can
  gate the Talent's readiness on it rather than letting the bot half-work. The declaration
  rules, the binding rules the registry enforces, and the readiness gate are in
  [`references/connections.md`](connections.md).

### 6. Namespacing (so bots never collide)
- Data under `~/.hermes/data/<bot>/` (D34); skills under
  `~/.hermes/skills/talents/<bot>/`; crons tagged by bot; config entries keyed by the
  bot's group id. No writes outside the bot's namespace; never into
  `~/.hermes/skills/tenant/`.
- **Sub-skill dirs globally unique across bundles** (`skill_view` refuses
  dupes — lint 16); tooling keys on `agent-profile.yaml`, not name globs.

### 7. Safety boundary (domain-appropriate)
- A boundary loaded with the voice: a "not professional advice" disclaimer,
  red-flag escalation for the domain (medical for food, financial for stocks),
  no invented facts about the user, and any sane hard limits. Present and wired
  into the persona, not buried.

### 8. Author in ENGLISH — the model localizes the reply on the fly (D148)
- **No per-tenant translation step.** Author every bundle in English; the model reads it
  and replies in the owner's own language, enforced every gateway AND cron turn
  (`_SYSTEM_DISCIPLINE` + hh-tools `pre_llm_call`). Author user-facing copy as a TEMPLATE
  the model renders, never a verbatim string; keep SQL/columns/numbers exact. (No
  `localized_bundle`/`.bundle_lang`/`skill-translator` — retired D148.)

### 9. Tool dependencies declared; charged tools stubbed
- External/charged tools are declared in the manifest. Absent ones ship as
  **stubs with graceful degradation** (the persona routes around them), and any
  cron that needs them is **gated** (`enabled_when: tool:<x>`). No real API key in
  the bundle.
- **What tools exist to request:** the full, current catalog — every requestable
  tool name, what it does, live/coming, and cost — is
  [`references/tools-catalog.md`](tools-catalog.md) (generated by Oteny).
  `scripts/lint_tools.py` checks your profile against it and **fails a stale claim**
  (a `stubbed` tool that is actually live). See
  [references/copy-and-tools.md](copy-and-tools.md).
  A browser-fill Talent uses the wrap's attached tree after each aim —
  scroll, press, and back peek under that same rule. Write that into
  the skill
  ([`references/browser-authoring.md`](browser-authoring.md)).
  `browser_type` needs a name (`role=textbox[name="…"]`). `@eN` on
  type is optional glue and must pair-check. A number-only type is
  refused. A last-page summary vs this turn's uplink DTO is Talent
  work, not wrap. The wrap does not judge a missing mapped field.
  Worked snapshot (role vs neighbour widgets vs remint):
  [`business-bot-pattern.md`](business-bot-pattern.md) §4g.
  Do not hand-edit generated `TOOLS.md` / `tools-catalog.md`. The bot-facing
  click / type / snapshot / navigate contract is the `hh-browser` schema wrap.

### 10. Discovery & progressive disclosure
- `SKILL.md` opens with intent (plain language), then a **quick-reference index**
  that loads `references/` on demand. The bundle exploits Hermes's native
  index → `skill_view(name)` → `skill_view(name, file)` disclosure rather than
  dumping everything up front.

### 11. Runtime-operable by a weak model
The Talent expansion of **the checklist-first bar**: the bundle must run day-to-day, not just
install (check 3 is one-time setup; this is steady state). Grade the full shape — **master
triage** every message (is-this-for-me YES/NO/unsure, **writes nothing on NO** → classify →
dispatch), **per-intent** sub-checklists, **completeness loops** that never restart from a partial
state, **grounded** reads (quote the store **this turn**, never from memory), and **no "enrich"
call** after a structured tool answers (a `web_search`/second grounded lookup is the Flash-tier
fabrication vector — durable fix is a feed/tool-gate/stronger tier, not prose). Detail + the
Talent nuances (jargon fade-ladder + glossary; hot-path-in-body):
[`references/checklist-first.md`](checklist-first.md). Owner **type-this** vs
bot **Bot notes** vs author docs:
[`references/audience-and-voice.md`](audience-and-voice.md).

### 12. Upgrade-safe (base/override split, D53)
The bundle is **fully replaced on every `update-talents`/converge** — so it must carry
**zero per-tenant state in its delivered files**. The control plane writes only the
base; per-tenant customization lives in the **override/data plane converge never
touches** (`~/.hermes/data/<bot>/` + a per-tenant override, D34/D53), never edited into
the shipped `SKILL.md` / `agent-profile.yaml` / profile. Three rules a grader checks:
- **No per-tenant facts baked** — reads tenant specifics from profile/intake/override
  (reinforces checks 4 + 6); anything written into `talents/<bot>/` is lost on the next
  converge.
- **Never rename a delivered slug** (`bot:` / dir name / `routing.channel`) without a
  migration — slug-keyed data orphans silently (belly→flatbelly would have).
- **Customization is a delta-only override** — corrections + additions only, one
  consolidated doc, **never a copy** of the base, so base improvements ship freely
  (D53 base/override rule, ported from Wilma).

**Mechanical gate.** [`scripts/lint_upgrade_safe.py`](scripts/lint_upgrade_safe.py)
(`python3 lint_upgrade_safe.py <bundle_dir>`) FAILS on a concrete **upgrade-safety**
violation (a shipped data-plane state file, an embedded secret, a hardcoded Telegram id)
**or a lean-authoring (D57) breach** (fat/unsharp bodies, approval-gate-tripping or
improvised commands, a first-run section in the body) — the script docstring is the
authoritative full list. Enforced in CI **and** by the deployer before ship.

### 13. In-box migrations (forward-only state reconciliation, D99)
A Talent with **mutable live state** (a db, or agent-registered crons) reconciles a prior
version's state **in-box, agent-driven** — never an operator editing the VM. It ships a
bundle-root `migrations.yaml` + the shared `scripts/migrate.py` + `references/migrations.md`,
and surfaces `MIGRATIONS: pending` from `preflight`. Mechanism + the D52 sidecar boundary:
[`references/in-box-migrations.md`](in-box-migrations.md).

### 14. Behavioral tests (the dev loop)
Ships **behavioral tests in the bundle** (`tests/{scenarios,fixtures,unit}`, never delivered)
run by [`run_scenario.py`](../../_shared/scripts/run_scenario.py): `--backend mock` (offline, free
in CI) + `--backend live`. Schema + examples: [`references/behavioral-scenarios.md`](behavioral-scenarios.md).
