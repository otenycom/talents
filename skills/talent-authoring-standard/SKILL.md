---
name: talent-authoring-standard
description: "Author or grade an Oteny Talent bundle."
version: 0.5.0
author: Oteny
license: Apache-2.0
metadata:
  hermes:
    tags: [authoring, validation, talent, rubric, quality-gate]
    related_skills: [oteny-flatbelly-talent, oteny-stock-talent]
---

# Authoring & validating an Oteny Talent

An Oteny Talent — Flatbelly-talent, Stocks-talent — is a folder of plain files that
teaches a tenant's agent to behave like a specialist and to **set itself up on
first use**. This skill is the standard those folders must meet, and a checklist a
capable LLM can apply to **grade** one and say "ship it" or "fix these first."

It serves two jobs from one rubric:
- **Author** — write a new bundle to this standard.
- **Validate** — inspect an existing bundle and emit a PASS/FAIL verdict.

It is the Talent-library counterpart to
[`skill-writing`](../../../skills/skill-writing/SKILL.md) (the *design* library); the full
rationale lives in [`skill-library`](../../../skills/skill-library/SKILL.md), and
[`oteny-flatbelly-talent`](../oteny-flatbelly-talent/) + [`oteny-stock-talent`](../oteny-stock-talent/)
are the worked examples.

## Defer to the native authoring skill (don't fork it)

An Oteny Talent **is** a Hermes skill bundle, so the GENERIC rules — frontmatter, the
canonical section structure, `references/`/`scripts/`/`templates/` placement, and
**sizing** — are owned by the native upstream skill
**[`hermes-agent-skill-authoring`](https://github.com/NousResearch/hermes-agent/blob/main/skills/software-development/hermes-agent-skill-authoring/SKILL.md)**
(the tenant has it loaded). Read it first; this skill adds the Oteny **product deltas**
below. Two native facts it leans on:

- **Lean bodies via native progressive disclosure.** Only a one-line `name:
  description` index sits in the cached prompt; the agent pulls a body on demand with
  `skill_view(name)` and a reference with `skill_view(name, file_path='references/…')`.
  So size matters: a `SKILL.md` body sits at **8–14k chars** and you **split into
  `references/` past ~20k** (hard cap 100k). Do **not** build a "load skill" tool —
  Hermes already is that tool.
- **The `description` is the router, truncated to 60 chars.** The index shows only the
  first ~60 chars of each description (`skill_utils.extract_skill_description`), so a
  composing skill's description must be a **sharp ≤60-char trigger** (the words a
  matching message contains), not a paragraph.

## Two invariants that make this cheap

This rubric, and everything it validates, holds to two hard invariants — confirm
both for any bundle:

1. **No Claude Code at runtime.** Claude Code (and its Workflows feature) is a
   build-time tool *we* may use to author and grade bundles. The bot itself never
   uses it; it runs on the tenant's Hermes. A bundle that assumes a Claude-Code
   host fails.
2. **No new Hermes code.** A bundle is plain files — `SKILL.md`, small YAML
   manifests, optional helper scripts — run by the tools the tenant's Hermes
   already has (`terminal`/`execute_code`/`cronjob`, plus the set Oteny provisions:
   web search, travel/maps, MCP servers — the menu is
   [`tool-use`](../../../skills/tool-use/SKILL.md)). Building **on** present tools is
   expected; what's banned is a Talent that can't run until *we* fork/patch Hermes or
   author a **new** tool/plugin. Declare what it needs (check 9), stub charged/absent
   tools so the persona degrades gracefully, and keep the deterministic backbone in
   the bundle's own scripts.

## The checklist-first bar (the airline-pilot rule)

The bot runs on the tenant's **global model tier** — usually a small, fast model
(Gemini-Flash), reliable **only when it follows a checklist**, not when it
improvises from prose. So author every task as a **numbered, verifiable checklist** — an
airline pilot's pre-flight list, **decision = the checklist, not the model's judgement**.
This is the durable **cost lever**: a checklist-structured skill runs correctly on the
cheap tier; prose forces a bigger model or a costly loop.

**Not Talent-only.** It governs **every Oteny skill a tenant's agent runs on that weak
model** — a sold **Talent** *and* the non-Talent **infra-default skills** we ship but never
sell (`oteny-cron-authoring`, `oteny-set-timezone`, …). A non-Talent skill is **N/A** for
the Talent-only rubric below (no `required_artifacts.yaml` / `agent-profile.yaml`) but holds
**this** bar the same: one ordered, literal protocol per task, no improvisation.

The shape (master triage → per-task *input → check → reply/act* → completeness loops), the
**five disciplines** that keep it runnable by the weak tier, the worked examples, and check
11's Talent expansion are in [`references/checklist-first.md`](references/checklist-first.md).
**Keep checklists lean — tune against real test-VM logs**, don't over-specify up front.

## When to use

- Writing or revising a `skills/<bot>/` bundle.
- Grading a bundle before it ships, or a tenant's Hermes self-checking a delivered one.

## The setup goal is the bundle's `required_artifacts.yaml`

The single most important idea: a bot's "setup goal" is **declared, not implied.**
`required_artifacts.yaml` lists every artifact that must exist before the bot can
work, each with a **machine-checkable** existence condition. That manifest *is* the
goal; the first-run section is the loop that drives toward it; `selfcheck` is the
deterministic judge. A bundle whose "done" state is vague cannot be validated and
cannot self-heal — so a well-formed manifest is the first thing to check.

Artifact classes a manifest may declare (omit those a bot doesn't need):

| Class | Checkable condition |
|---|---|
| `data` | db file exists + named tables present |
| `profile` | profile file exists + required fields non-empty |
| `memory` | `~/.hermes/memories/USER.md` rendered from the profile |
| `routing` | this bot's `channel_prompt` (+ optional DM hint) registered |
| `cron` | named jobs registered (with `enabled_when: tool:<x>` if gated) |
| `tools` | required tools present; absent charged tools shipped as stubs |
| `secret` | named env vars present (delivered by the deployer, never baked) |

## The rubric — 14 checks (each PASS / FAIL / N/A)

Grade a bundle by running each check against the folder. Concrete inspection
commands are given where they help; an LLM can run them via `terminal`. Checks 4 and 9
add **context-aware reads** (not keyword matches) — see
[references/copy-and-tools.md](references/copy-and-tools.md).

### 1. Package structure
- `SKILL.md` with valid agentskills.io frontmatter (`name`, `description`,
  `version`). `description` is a **sharp ≤60-char trigger** — the index truncates it
  to 60, and the model self-selects on it (the words a matching message contains).
- `agent-profile.yaml` (voice/persona, `channel_prompt` text, toolset
  *contribution*, baked|purchased, price). Model tier is **global, not per-bot**. A
  Talent (a bundle with `required_artifacts.yaml`) **must** ship one.
- `required_artifacts.yaml` present and complete (see above).
- `references/` for on-demand detail; `scripts/` for deterministic helpers (both
  optional). A multi-skill Talent: each composing skill independently valid.
- **Composition discipline (multi-skill Talents):** each composing skill owns **one**
  concern (engine / method / voice / visual / onboarding); they **cross-reference,
  never duplicate** — one canonical home per fact (SQL mechanics in one `references/`;
  the method math in the method skill; the welcome in onboarding). A master engine skill
  **triages and dispatches** to the others (see check 11).
- **Lean body, native sizing.** A `SKILL.md` body sits at **8–14k chars** and splits
  into `references/` past ~20k (native rule, hard cap 100k); the first-run drill lives
  in `references/first-run.md`, not the body. Detail is one level deep in `references/`.

### 2. Setup goal well-defined
- Every artifact the bot needs is in `required_artifacts.yaml` with a **concrete,
  checkable** condition (a path, table names, field names) — no vague "set up
  correctly." If you can't write a one-line check for it, it's underspecified.

### 3. First-run is mechanical, idempotent, in `references/`, and approval-clean
- The first-run drill lives in **`references/first-run.md`** (pulled only when the
  guard says NOT-READY), **not** in the `SKILL.md` body (D57 — it would otherwise sit
  in context on every load). The body's triage just routes to it.
- It is **copy-paste-exact**: literal commands, **no judgement calls left to the model**.
- It opens with a **one-line guard** ("is setup complete?") — READY ⇒ skip & act.
- **Declared scripts only — never improvised exec.** Create the schema by running the
  shipped `scripts/init.sql` (`sqlite3 db < scripts/init.sql`) or a `scripts/*.py`;
  **never** paste an inline `CREATE TABLE`, a `python3 -c "…"`, or a heredoc — Hermes'
  approval gate flags improvised exec and the bot stalls on "Command Approval
  Required" (the live food-tracker loop, D57). The schema lives **once**, in
  `scripts/*.sql`; `.md` documents columns in prose.
- Remediation is **idempotent**: `init.sql` is `CREATE TABLE IF NOT EXISTS`, cron
  registered list-first ("create if absent"), `ON CONFLICT … DO UPDATE` for daily rows.
- It covers **every** manifest class it declares (create db → intake →
  register routing/cron) and **loops to a re-check** → READY.
- **Cron jobs MUST pin `model` + `provider`** (live-proven footgun, D40). An un-pinned job
  resolves its model from `config.yaml`'s `model.default`; with none it fires **empty** and
  the router 400s — reminders silently fail. So the planner reads model+provider from
  `config.yaml` and passes them on **every** job (see
  `oteny-flatbelly-talent/scripts/provision_cron.py`). The pin is a **persona alias**
  (`assistant`/`builder`/`researcher`, D55) — fallback `assistant`, **never** the raw
  OpenRouter slug.
- Honors the runtime hard rules (proven on the live `food-tracker`): **one
  `sqlite3` invocation per terminal call; never chain INSERT+SELECT in one call;
  keep non-ASCII out of SQL output.**
- **Collapse the per-turn preamble** (D38): the triage's first action should be a
  **single** `preflight`-style script call returning readiness + clock + today's
  state + memory + targets, and the hot intents inlined into `SKILL.md` — not 4–5
  separate probe calls + a reference load. On a weak runtime model that fan-out is
  most of a slow turn (live: 67 calls → 5).

### 4. PII / secrets clean (method, not person) — and generic, not baked for one body
- No personal data, no real tokens/keys, no hardcoded chat/user ids. Tenant
  specifics come from the profile/intake, never baked.
- Method facts stay (rules, ratios, formats); body/account specifics go.
- **Owner settings live in the profile/override (D34/D53), not the bundle.** Delivered
  files carry only generic **defaults**; an owner-specific setting with **no safe
  default** (which project/account/location) gets **no baked value** — the bot asks the
  owner and `selfcheck` flags it unset. Never bake one tenant's value (project, timezone,
  name) as a default. (Worked fix: `backup-odoo-sh-database`.)
- **Generic & derived, not tuned to the source user.** Numbers that remain must fit any
  tenant: rates as **%/relative** (not one user's absolute kg), targets **per-unit or
  derived from the profile**, the path **derived from the tenant's own data** (obese →
  lean athlete) — never a curve calibrated to one body. Scan for tell-tale source-user
  magnitudes (a specific start weight, a personal lab value).
- Gate: ``grep -riE 'name-of-source-user|real_token|DEFAULT_TOKEN|[0-9]{8,}|api[_-]?key' <bundle>`` returns nothing meaningful.

### 5. Routing declared (not hand-edited into SOUL)
- A `routing` declaration: a per-group `channel_prompt` (persona **and** a "load
  `<skill>` first" directive) + an optional one-line DM hint. The reconciler
  applies it; the bundle never string-edits SOUL or `config.yaml` itself.
- Per-bot **voice lives in the skill**, not a global SOUL.
- Group/chat ids are **looked up at runtime** (from `channel_directory.json`),
  never hardcoded.
- **Scoped business bots route to Odoo Discuss, not Telegram** — and shift the toolset
  (checks 1 + 9), data plane (checks 2 + 6), and tests (check 14) accordingly; the full
  authoring delta is [`references/business-bot-pattern.md`](references/business-bot-pattern.md).

### 6. Namespacing (so bots never collide)
- Data under `~/.hermes/data/<bot>/` (D34); skills under
  `~/.hermes/skills/talents/<bot>/`; crons tagged by bot; config entries keyed by the
  bot's group id. No writes outside the bot's namespace; never into
  `~/.hermes/skills/tenant/`.

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
  [`references/tools-catalog.md`](references/tools-catalog.md) (generated by Oteny).
  `scripts/lint_tools.py` checks your profile against it and **fails a stale claim**
  (a `stubbed` tool that is actually live). See
  [references/copy-and-tools.md](references/copy-and-tools.md).

### 10. Discovery & progressive disclosure
- `SKILL.md` opens with intent (plain language), then a **quick-reference index**
  that loads `references/` on demand. The bundle exploits Hermes's native
  index → `skill_view(name)` → `skill_view(name, file)` disclosure rather than
  dumping everything up front.

### 11. Runtime-operable by a weak model
The Talent expansion of **the checklist-first bar** (above): the bundle must be
**executable day-to-day without losing track**, not merely installable (check 3 is the
one-time *setup*; this is the steady state).
Grade for the full shape — a **master triage** on every message (setup-check →
is-this-for-me YES/NO/unsure, **writes nothing on NO** → classify → dispatch),
**per-intent** *data entry → analysis → reply* sub-checklists, **completeness loops**
that never restart from a partial state, and **grounded** reads (quote the store **this
turn**; never a number from memory) — plus the two Talent nuances (jargon fade-ladder +
glossary; hot-path-in-body) — all detailed in
[`references/checklist-first.md`](references/checklist-first.md).

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
  ([D53](../../../skills/design/decisions.md) base/override rule, ported from Wilma).

**Mechanical gate.** [`scripts/lint_upgrade_safe.py`](scripts/lint_upgrade_safe.py)
(`python3 lint_upgrade_safe.py <bundle_dir>`) FAILS on a concrete **upgrade-safety**
violation (a shipped data-plane state file, an embedded secret, a hardcoded Telegram id)
**or lean-authoring (D57)** — over-60-char `description`, over-20k `SKILL.md`, an
approval-gate-tripping command in a fenced block (`python -c`/heredoc/`bash -c`/`curl|sh`/
unguarded `DELETE`), an inline `CREATE TABLE` in `.md`, a `## First-run setup` body section,
or a Talent missing `agent-profile.yaml` (the script's docstring is the full list). Enforced
**twice** — CI/offline suite **and** the deployer before shipping to a tenant; lint clean
before ship.

**Reference implementations (copy the shape).** Flatbelly's master triage / per-intent
checklists / fade-ladder glossary / completeness checklist, plus the non-Talent
`oteny-cron-authoring` protocol — all collected in
[`references/checklist-first.md`](references/checklist-first.md).

### 13. In-box migrations (forward-only state reconciliation, D99)
A Talent with **mutable live state** (a db, or agent-registered crons) reconciles a prior
version's state **in-box, agent-driven** — never an operator editing the VM. It ships a
bundle-root `migrations.yaml` + the shared `scripts/migrate.py` + `references/migrations.md`,
and surfaces `MIGRATIONS: pending` from `preflight`. Mechanism + the D52 sidecar boundary:
[`references/in-box-migrations.md`](references/in-box-migrations.md).

### 14. Behavioral tests (the dev loop)
Ships **behavioral tests in the bundle** (`tests/{scenarios,fixtures,unit}`, never delivered)
run by [`run_scenario.py`](../_shared/scripts/run_scenario.py): `--backend mock` (offline, free
in CI) + `--backend live`. Schema + examples: [`references/behavioral-scenarios.md`](references/behavioral-scenarios.md).

## Store presentation + per-Talent tools

A Talent's storefront face — the optional bundle-root `icon.png` + `teaser.yaml` (sample
chat) the Bot Market seeder reads — and the `agent-profile.yaml` tools declaration that
doubles as the "what it can do" copy (the check-9 extension) live in
[`references/store-presentation.md`](references/store-presentation.md).

## Validation output (what the grader returns)

When grading, emit a compact PASS/FAIL/N/A line per check and a verdict footer,
nothing else; a bundle ships only at **VERDICT: SHIP** (no FAILs; N/As justified).
The exact output format is in
[`references/validation-output.md`](references/validation-output.md).

## Authoring workflow (writing to the standard)

1. Start from `required_artifacts.yaml` — declare the goal first.
2. Write the mechanical first-run section that drives to it (check 3).
3. Write the behavior + voice + references; add the safety boundary + routing
   declaration; namespace everything. **Write to the checklist-first bar (check 11):** a
   master triage + per-intent entry→analysis→reply sub-checklists + completeness loops.
4. De-personalize against check 4 (and keep what remains **generic/derived**, not tuned
   to one body); quarantine for check 8; keep it **upgrade-safe** (check 12) — no
   per-tenant state in delivered files, stable slug, customization → delta-only override.
5. Self-grade with the rubric; reach **SHIP** before baking.

## Related

- [`skill-library`](../../../skills/skill-library/SKILL.md) — the package contract,
  first-run, routing/reconciler, delivery, and how Talents are authored,
  priced, and delivered.
- [`../oteny-flatbelly-talent/`](../oteny-flatbelly-talent/),
  [`../oteny-stock-talent/`](../oteny-stock-talent/) — the shipped worked examples to validate against.
- [`skill-writing`](../../../skills/skill-writing/SKILL.md) — the *design*-library
  authoring standard (this skill's counterpart for `skills/`).
