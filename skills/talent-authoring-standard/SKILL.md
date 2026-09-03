---
name: talent-authoring-standard
description: "Author or grade an Oteny Talent bundle."
version: 0.5.4
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

Authors in this repo use **this** skill plus
[`oteny-talent-authoring`](../oteny-talent-authoring/SKILL.md) and
[`oteny-talent-dev-loop`](../oteny-talent-dev-loop/SKILL.md);
[`oteny-flatbelly-talent`](../oteny-flatbelly-talent/) +
[`oteny-stock-talent`](../oteny-stock-talent/) are the worked examples.
(Package/delivery mechanics on the Oteny control plane are out of scope here — this
repo is the whole public surface for Talent authors.)

## Defer to the native authoring skill (don't fork it)

An Oteny Talent **is** a Hermes skill bundle, so the GENERIC rules — frontmatter, the
canonical section structure, `references/`/`scripts/`/`templates/` placement, and
**sizing** — are owned by the native upstream skill
**[`hermes-agent-skill-authoring`](https://github.com/NousResearch/hermes-agent/blob/main/skills/software-development/hermes-agent-skill-authoring/SKILL.md)**
(the tenant has it loaded). Read it first; this skill adds the Oteny **product deltas**
below. Two native facts it leans on:

- **Lean bodies, native progressive disclosure.** Only the one-line `name: description`
  index is cached; bodies + references load on demand via `skill_view(name[, file_path])`.
  So a `SKILL.md` body sits at **8–14k chars** and **splits into `references/` past ~20k**
  (the offline lint **and** on-bot delivery gate both fail past 20 000 — `last_status=gate_failed`)
  (hard cap 100k) — don't build a "load skill" tool, Hermes is one.
- **The `description` is the router, truncated to ~60 chars**
  (`skill_utils.extract_skill_description`) — make it a **sharp ≤60-char trigger**, not a paragraph.

## Two invariants that make this cheap

This rubric, and everything it validates, holds to two hard invariants — confirm
both for any bundle:

1. **No Claude Code at runtime.** Claude Code (and its Workflows feature) is a
   build-time tool *we* may use to author and grade bundles. The bot itself never
   uses it; it runs on the tenant's Hermes. A bundle that assumes a Claude-Code
   host fails.
2. **No new Hermes code.** A bundle is plain files — `SKILL.md`, small YAML manifests,
   optional helper scripts — run by the tools the tenant's Hermes already has
   (`terminal`/`execute_code`/`cronjob` + the set Oteny provisions: web search, travel/maps,
   MCP — the menu is the generated [`TOOLS.md`](../../TOOLS.md)). Building **on** present
   tools is expected; **banned** is a Talent that can't run until *we* fork/patch Hermes or
   author a **new** tool. Declare what it needs (check 9), stub charged/absent tools so the
   persona degrades, and keep the deterministic backbone in the bundle's own scripts.

## Audience first — owner chat vs bot checklist vs author docs

A Talent bundle is read by **different people for different jobs**. Fence them or the
copy fails (tool APIs aimed at owners, platform jargon in chat, eng runbooks in the
hot path):

| Reader | Write for them with |
| --- | --- |
| **End-user (owner)** | Plain chat — *what to type*, never tool/shell names |
| **Bot (weak model)** | Checklist-first **Bot notes** — tools, scripts, verify steps |
| **Talent author / platform eng** | Authoring skills + HermesHost design library — **not** shipped runtime copy |

**Owner-facing shape:** lead with copy-paste chat lines (`Attach my domain example.com…`);
put `attach_site_domains(...)` only under a labelled **Bot notes** footer. Worked example:
[`odoo-website`](../odoo-website/). Full rule:
[`references/audience-and-voice.md`](references/audience-and-voice.md).

## The checklist-first bar (the airline-pilot rule)

The bot runs on the tier the Talent declares (`model_tier` in `agent-profile.yaml`;
default the tenant's global tier — usually a small, fast model like Gemini-Flash),
reliable **only when it follows a checklist**, not when it improvises from prose. So author every task as a **numbered, verifiable checklist** — an
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
Audience fencing ([`audience-and-voice.md`](references/audience-and-voice.md)) sits **on
top** of this bar — it does not replace it.

## When to use

- Writing or revising a `skills/<bot>/` bundle.
- Grading a bundle before it ships, or a tenant's Hermes self-checking a delivered one.

## The setup goal is the bundle's `required_artifacts.yaml`

The single most important idea: a bot's "setup goal" is **declared, not implied.**
`required_artifacts.yaml` lists every artifact that must exist before the bot can
work, each with a **machine-checkable** existence condition. That manifest *is* the
goal; the first-run section is the loop that drives toward it; `selfcheck` is the
deterministic judge. A bundle whose "done" state is vague cannot be validated and
cannot self-heal — so a well-formed manifest is the first thing to check. The artifact
classes it may declare (`data`/`profile`/`memory`/`routing`/`cron`/`tools`/`secret`/
`connection`) and their checkable conditions are in
[`references/required-artifacts.md`](references/required-artifacts.md).

## The rubric — 14 checks (each PASS / FAIL / N/A)

Grade a bundle by running each check against the folder. The full text of every
check — the inspection commands, the examples, the context-aware reads for 4 and 9 —
is in [references/rubric.md](references/rubric.md). Open it before grading. The digest:

1. **1. Package structure** — `SKILL.md` with valid agentskills.io frontmatter (`name`, `description`, `version`).
2. **2. Setup goal well-defined** — Every artifact the bot needs is in `required_artifacts.yaml` with a **concrete, checkable** condition (a path, table names, field names) — no vague "set up correctly." If you can't write a one-line check for it, it's underspecified.
3. **3. First-run is mechanical, idempotent, in `references/`, and approval-clean** — Six graded rules — drill in **`references/first-run.md`** (not the body, D57); declared scripts only (no improvised exec); cron pins `model`+`provider` as a persona alias; one `sqlite3` per terminal call; readiness scripts are pure-stdlib and never hard-fail (D237); third-party feature scripts ship a uv lock + `talent-run`; collapse the per-turn preamble to one preflight (D38).
4. **4. PII / secrets clean (method, not person) — and generic, not baked for one body** — No personal data, tokens, or hardcoded chat/user ids.
5. **5. Routing declared (not hand-edited into SOUL)** — A `routing` declaration: a per-group `channel_prompt` (persona **and** a "load `<skill>` first" directive) + an optional one-line DM hint.
6. **6. Namespacing (so bots never collide)** — Data under `~/.hermes/data/<bot>/` (D34); skills under `~/.hermes/skills/talents/<bot>/`; crons tagged by bot; config entries keyed by the bot's group id.
7. **7. Safety boundary (domain-appropriate)** — A boundary loaded with the voice: a "not professional advice" disclaimer, red-flag escalation for the domain (medical for food, financial for stocks), no invented facts about the user, and any sane hard limits.
8. **8. Author in ENGLISH — the model localizes the reply on the fly (D148)** — **No per-tenant translation step.** Author every bundle in English; the model reads it and replies in the owner's own language, enforced every gateway AND cron turn (`_SYSTEM_DISCIPLINE` + hh-tools `pre_llm_call`).
9. **9. Tool dependencies declared; charged tools stubbed** — External/charged tools are declared in the manifest.
10. **10. Discovery & progressive disclosure** — `SKILL.md` opens with intent (plain language), then a **quick-reference index** that loads `references/` on demand.
11. **11. Runtime-operable by a weak model** — The Talent expansion of **the checklist-first bar**: the bundle must run day-to-day, not just install (check 3 is one-time setup; this is steady state).
12. **12. Upgrade-safe (base/override split, D53)** — The bundle is **fully replaced on every `update-talents`/converge** — so it must carry **zero per-tenant state in its delivered files**.
13. **13. In-box migrations (forward-only state reconciliation, D99)** — A Talent with **mutable live state** (a db, or agent-registered crons) reconciles a prior version's state **in-box, agent-driven** — never an operator editing the VM.
14. **14. Behavioral tests (the dev loop)** — Ships **behavioral tests in the bundle** (`tests/{scenarios,fixtures,unit}`, never delivered) run by [`run_scenario.py`](../_shared/scripts/run_scenario.py): `--backend mock` (offline, free in CI) + `--backend live`.

## Store presentation + per-Talent tools

A Talent's storefront face — the optional bundle-root `icon.png` + `teaser.yaml` (sample
chat) the Talent Market seeder reads — and the `agent-profile.yaml` tools declaration that
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
   declaration; namespace everything. **Fence audiences**
   ([`audience-and-voice.md`](references/audience-and-voice.md)): owner chat phrases
   first, **Bot notes** for tools/scripts. **Write to the checklist-first bar
   (check 11):** master triage + per-intent sub-checklists + completeness loops.
4. De-personalize against check 4 (and keep what remains **generic/derived**, not tuned
   to one body); quarantine for check 8; keep it **upgrade-safe** (check 12) — no
   per-tenant state in delivered files, stable slug, customization → delta-only override.
5. Self-grade with the rubric; reach **SHIP** before baking.

## Related

- [`references/audience-and-voice.md`](references/audience-and-voice.md) — owner vs bot
  vs author; type-this writing style.
- [`references/connections.md`](references/connections.md) — the four `connections:`
  kinds, the binding rules, and the readiness gate a `kind: saas` entry arms.
- [`oteny-talent-authoring`](../oteny-talent-authoring/SKILL.md) — create → edit →
  package → publish.
- [`oteny-talent-dev-loop`](../oteny-talent-dev-loop/SKILL.md) — clone → reload →
  test → traces → green → tag.
- [`../odoo-website/`](../odoo-website/) — worked example of type-this + Bot notes.
- [`../oteny-flatbelly-talent/`](../oteny-flatbelly-talent/),
  [`../oteny-stock-talent/`](../oteny-stock-talent/) — shipped worked examples to
  validate against.
