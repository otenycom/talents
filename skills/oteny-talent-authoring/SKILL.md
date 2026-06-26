---
name: oteny-talent-authoring
description: "Create, edit, review, export, import, or publish a Talent."
version: 1.0.0
author: Oteny
license: MIT
metadata:
  hermes:
    tags: [authoring, skills, talents, publishing, oteny, how-to]
    related_skills: [hermes-agent-skill-authoring, oteny-web-operator, oteny-remember-login]
---

# Building your own skills & Talents on Oteny

## Overview

You (the owner) can ask me to build new skills — "make me a skill that tracks my
plants", "add a habit tracker", "teach yourself to draft my newsletter." I create them
the same way I'd create any Hermes skill, **plus** a few house rules that make them
robust on this hosted setup and ready to **publish as a Talent** (a packaged
persona + skills others can install). This skill is those house rules; it does **not**
re-explain the generic mechanics — those live in the native **`hermes-agent-skill-authoring`**
skill, which I read first.

> **Oteny preserves the Talents you build (your work is safe across updates).** When I
> author a publishable Talent into the Talent overlay (`~/.hermes/skills/talents/<slug>/`),
> Oteny's fleet updates **never prune a bundle they didn't deliver** — a routine update
> refreshes the Oteny-shipped Talents but carries your own Talent across untouched, and it
> rides backups so a rebuild restores it. So building your own Talent here is durable, not
> throwaway. (If I author it share-ready by the rules below, you can also later
> **promote** it into the Oteny catalog with one command.)

> **Build on the vetted building blocks — don't reverse-engineer them.** A Talent that
> operates a website, remembers a login, retrieves a download, searches the web, or
> takes a credential should route through the existing capability skills, never grep my
> own plugin/framework source to rediscover how a tool works: web tasks + retrieving a
> downloaded file → **`oteny-web-operator`** (`browser_download`); a remembered login →
> **`oteny-remember-login`** (`connect_login`); a secret/API key → **`oteny-connect-credential`**;
> sharing a local file → **`oteny-drop`**. Compose these as steps; they're the tested path.

## When to Use

- The owner asks me to **create / edit** a skill or workflow ("make me a skill that …").
- The owner asks to **package or publish** one as a Talent (to reuse, share, or submit
  to the Oteny Talent Store).
- The owner asks to **review / read back / export** a Talent in full, or to **import**
  one someone shared — Telegram can't show a multi-file bundle, so I publish an **Oteny
  Talent Drop** (a rendered viewer + a downloadable zip). Protocol:
  [`references/export-import.md`](references/export-import.md).
- I'm reviewing a skill I (or the owner) wrote and want it to meet the Oteny bar.

Don't use for: one-off tasks (just do them); editing an Oteny Talent already
installed (those are control-plane managed and replaced on upgrade — customize via the
override file, see rule 7).

## Step 0 — defer to the native authoring skill

Load `skill_view(name='hermes-agent-skill-authoring')` first. It owns the generic rules
and I follow them verbatim: frontmatter (`---` at byte 0, `name`, `description`,
non-empty body), the `# Title → ## Overview → ## When to Use → body → ## Common
Pitfalls → ## Verification Checklist` structure, `references/`/`scripts/`/`templates/`
placement, sizing (8–14k chars; split past ~20k), and `skill_manage(action='create')`
for a personal user-local skill vs `write_file` for an in-repo one.

**Where it lives decides whether it's a quick skill or a publishable Talent:**
- A **quick personal skill** (just for this bot) → `skill_manage(action='create')`, which
  lands it in the Hermes bundled tree (e.g. `~/.hermes/skills/<category>/<name>/`). Fine
  for one-off helpers; not share-ready.
- A **publishable Talent** → a **top-level dir in the Talent overlay**,
  `~/.hermes/skills/talents/<slug>/`, with the full share-ready structure (rule 4:
  `agent-profile.yaml`, `required_artifacts.yaml`, `SKILL.md`, `scripts/selfcheck.py`,
  `references/first-run.md`). This is the overlay Oteny **preserves** across updates and
  the only home `promote-talent` can lift from — so build anything meant to be reused or
  shared *here*, not in the bundled tree.

## The Oteny house rules (what this adds)

These are the deltas that matter on a hosted, always-on, possibly-multilingual bot:

**Above all — I structure every skill as checklists, not prose (the airline-pilot
rule).** This bot runs on a small, fast model that is reliable **only when it follows a
numbered checklist** instead of improvising — and checklists keep it cheap to run. So I
write each skill as a **triage** at the top (is this for me? → which task?), then a
**numbered, literal checklist per task** shaped *input → check → reply/act*, plus a
**completeness loop** for anything that gathers several inputs (track what's still
missing, ask only for that, never restart from scratch). The decision is the checklist,
not a guess; if a run finds nothing, I say so — I never fabricate a result. The delivered
**`oteny-cron-authoring`** skill is the shape to copy (*"do these in order, every
time"*). This holds for **every** skill I build — quick personal helper or published
Talent alike.

1. **Data lives in `~/.hermes/data/<skill>/`, never the home root.** Put every db /
   file the skill writes under its own namespaced data dir (e.g.
   `~/.hermes/data/plant-tracker/plants.db`). Don't scatter state at `~/` (a common
   slip — see the worked example). The data dir is the durable plane: it survives skill
   upgrades and is what gets backed up.

2. **Declared, approval-clean commands only.** My gateway flags improvised code
   execution for approval, which stalls a smooth flow. So:
   - Create a schema by shipping a `scripts/init.sql` and running
     `sqlite3 ~/.hermes/data/<skill>/x.db < .../scripts/init.sql` — **not** by pasting a
     `CREATE TABLE` block and **not** with `python3 -c "…"` or a `<<EOF` heredoc.
   - Put any real logic in a declared `scripts/*.py` and run it as
     `python3 .../scripts/foo.py` (declared script paths are fine; `python3 -c`/`-e`,
     `bash -c`, heredocs, and unguarded `DELETE`/`DROP` are not). Verify with a separate
     `SELECT`; never chain `INSERT`+`SELECT` in one call.

3. **Lean body, sharp description.** Keep `SKILL.md` to the triage + hot path + a few
   hard rules; push detail into `references/` (I load them on demand). The
   **`description` is the router** — I pick the skill from its first ~60 chars, so make
   it a sharp trigger naming the words a matching message contains (e.g.
   `"Log plants, watering, sunlight, and growth notes."`).

4. **To make it a publishable *Talent*, add a profile + a setup goal.** A skill becomes
   a Talent (installable, with a persona) when it ships:
   - `agent-profile.yaml` — `bot:` (the slug), `display_name`, `tagline` (shown in the
     welcome), the `skills:` it bundles, `voice_skill:`, `base_language`, and a
     `routing:` block with a `channel_prompt` + `signature`.
   - `required_artifacts.yaml` — the **setup goal**, one machine-checkable artifact per
     thing that must exist (db + tables, profile fields, etc.).
   - a `scripts/selfcheck.py` (copy the standard one) + a `references/first-run.md` drill
     that drives a fresh install to READY using declared scripts.

5. **Routing is by topic, zero-config.** In a DM I auto-pick the right skill from the
   index. In a **group**, the group's title is injected for me, so a group named for the
   topic ("Plants", "Stocks") routes to the matching Talent — no per-group setup. The
   owner can pin an ambiguous group to a Talent explicitly if needed.

6. **Author in English; localize per owner.** Write the bundle's files in **English**
   (`base_language: en`) even for a non-English owner — the bundle is translated on
   demand and I reply in the **owner's** language (from their profile). Keep SQL, column
   names, code, and URLs in fenced/quarantined blocks so localization can't break the
   mechanics; keep technical jargon in English. Never hardcode the owner's language.

7. **Upgrade-safe: no per-tenant state in the skill files.** The skill body holds the
   *method*; the *person* (the owner's data, preferences, settings) lives in the data
   plane (`~/.hermes/data/<skill>/profile.yaml`) and a durable override file — so I can
   improve the skill without losing the owner's customizations. Never bake a name, an id,
   a token, a timezone, or a project/account into the skill. A setting with **no safe
   default** (e.g. *which* account/project to act on) gets **no baked value** — I **ask
   the owner** and `selfcheck` flags it unset until filled; only settings with a sane
   generic default (and the default only) ship in the files.

8. **A Talent that signs in to a website scripts the login as a checklist, not free
   clicks.** Compose the building blocks (`oteny-web-operator`, `oteny-remember-login`) —
   don't hand-roll login steps the weak model can brute-force. The login step is a
   **decision table** (signed-in / login page / 2FA prompt / "too many attempts") with one
   rule each, and **any** wall → `browser_request_human` **once**, then stop and wait. End
   it with a hard "never" list (read most recently): never click sign-in more than once,
   never type the username/password/2FA, never retry a blocked login, never `connect_login`
   when `list_logins` already has the site. Many sites (odoo.sh → GitHub, anything on
   Google) force **2FA** a saved password can't pass — for unattended runs the owner saves
   the site's 2FA seed via `connect_login`; otherwise expect a one-time human handoff each
   run.

## Worked example — turning a good skill into a Talent

A real grocery-tracker built on a tenant box was **good**: a tidy ~100-line `SKILL.md`,
proper `references/` + `scripts/`, a declared CLI. But it fell short of a publishable
Talent on two counts, both fixed by the rules above:

- It stored its db at `~/grocery_list/grocery.db` (home root) → **move it** to
  `~/.hermes/data/grocery-tracker/grocery.db` (rule 1) so it's namespaced and backed up.
- It had **no `agent-profile.yaml`** and no `required_artifacts.yaml` → **add them**
  (rule 4): a profile with `display_name: "Grocery list"`, a sharp `description`, a
  `routing.channel_prompt`, and a manifest declaring the db + tables. Now it self-checks,
  routes, and can be installed by anyone.

That's the whole gap between "a handy skill I made" and "a Talent worth publishing."

## Publishing to the Oteny Talent Store

When a Talent is solid, I can submit it. **Author it share-ready from the start so it
promotes clean the first try** — the promote step sanitizes per-tenant state and then
lint-gates against the Talent authoring standard, so a Talent that already follows the
rules sails through:

- **No per-tenant state in the files.** Data under `~/.hermes/data/<slug>/` (rule 1), and
  **never a baked `channel_chat_id`/owner id/token** — routing is by topic (rule 5), so
  the shared version routes via the native index + group title, not a hardcoded chat id.
- Lean body, **≤60-char description**, declared/approval-clean commands, `agent-profile.yaml`
  present (rules 2–4).

The owner runs **`promote-talent --ref <tenant> --slug <slug>`** (Oteny side): it pulls
the Talent from `~/.hermes/skills/talents/<slug>/`, strips any per-tenant state, lints it,
and on a clean pass writes it into the Oteny catalog for review — after which it becomes
installable by other Oteny users. If the lint flags something, it reports exactly what to
fix and writes nothing; I fix it and retry. (The self-serve submission button is rolling
out — until then I keep the Talent share-ready and tell the owner it's queued.)

## Common Pitfalls

1. **Writing data to `~/` instead of `~/.hermes/data/<skill>/`.** It works today but
   isn't namespaced or reliably backed up, and two skills can collide.
2. **Improvising `python3 -c "…"` / a heredoc / inline `CREATE TABLE`.** It trips the
   approval gate mid-flow. Ship a `scripts/init.sql` / `scripts/*.py` and run it.
3. **A paragraph for a `description`.** Only the first ~60 chars route; make it a sharp
   trigger.
4. **Forgetting `agent-profile.yaml` / `required_artifacts.yaml`** — then it's a skill,
   not a Talent: it can't self-check, route, or be published.
5. **Baking the owner's data into the skill** — it's lost on the next improvement, and
   it's not shareable. Keep person-data in the data plane.
6. **Writing the skill as prose to interpret instead of a numbered checklist** — a small
   model loses track or improvises. Give it a triage + a literal per-task checklist.
7. **A login Talent that lets the model click sign-in repeatedly.** On a 2FA / "too many
   attempts" wall it must hand off **once** via `browser_request_human` and stop — repeated
   clicks trip the site's rate-limit and email the owner a security alert (rule 8).

## Verification Checklist

- [ ] Read `hermes-agent-skill-authoring`; frontmatter + structure follow it.
- [ ] `description` ≤ 60 chars and a sharp trigger.
- [ ] Data under `~/.hermes/data/<skill>/`; nothing written to `~/`.
- [ ] Schema in `scripts/init.sql` (or a `scripts/*.py`); no inline DDL / `python3 -c` /
      heredoc; guarded deletes only.
- [ ] Body lean; detail in `references/`.
- [ ] Structured as checklists: a triage + a numbered per-task checklist (input → check →
      reply/act) + a completeness loop for multi-input flows — no step left to a guess.
- [ ] (Talent) `agent-profile.yaml` + `required_artifacts.yaml` + `selfcheck.py` +
      `references/first-run.md` present and self-checks to READY.
- [ ] No per-tenant data / ids / tokens baked into the skill files.
- [ ] (Browser-login Talent) login is a decision-table checklist composing
      `oteny-web-operator`/`oteny-remember-login`; any 2FA/blocked wall → one
      `browser_request_human` handoff then stop; no repeated sign-in clicks (rule 8).
