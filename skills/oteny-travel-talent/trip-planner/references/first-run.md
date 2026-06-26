# trip-planner — First-run setup & self-check

**You are here only because triage step 1 (`preflight.py`) or the guard printed
`NOT-READY`.** Normal turns never load this file. It is mechanical and idempotent: run
the guard for the exact missing list, run the remediation for each missing artifact in
order (declared scripts only — never improvise `python3 -c`, a heredoc, or inline DDL;
those stall on the approval gate), then re-check. The setup GOAL is declared in
`../../required_artifacts.yaml`; `selfcheck.py` is the judge.

There are **no crons to register at first-run** — they are trip-scoped (created when a
trip/flight is added; see `disruption.md`), so a freshly set-up bot with no trip has zero
scheduled jobs and zero idle cost.

## Guard (the authoritative readiness judge)

```bash
python3 ~/.hermes/skills/talents/oteny-travel-talent/scripts/selfcheck.py
```

- `READY` → setup is done. Stop here and plan.
- `NOT-READY: missing=[…]` → run the remediation for **each** listed artifact, in this
  order, then run the guard again.

## Runtime hard rules for setup (proven on the source instance)

- **One `sqlite3` invocation per terminal call.** Never chain `INSERT`+`SELECT` in one
  call — a mid-call error lands the write but errors the call, and a blind retry
  double-writes. Verify with a separate `SELECT`.
- **Declared scripts only.** Create the schema by running the shipped `init.sql`; never
  paste a `CREATE TABLE` block and never use `python3 -c`/heredocs — the gateway's
  approval gate flags improvised exec and the bot stalls waiting for `/approve`.
- **Keep non-ASCII out of SQL output** (no ✅/⚠️/→ inside SQL `SELECT`); render emoji
  only in the final reply.

## Remediation: `data` (db + tables missing)

Create the namespaced data dir and apply the canonical schema by running the shipped,
idempotent `init.sql` (the **single** executable copy of the schema; columns are
documented in `datamodel.md`). Both commands are declared and approval-clean:

```bash
mkdir -p ~/.hermes/data/oteny-travel-talent
```
```bash
sqlite3 ~/.hermes/data/oteny-travel-talent/trips.db < ~/.hermes/skills/talents/oteny-travel-talent/scripts/init.sql
```

## Remediation: `profile` (intake)

The **conversational** welcome + question set (what the bot does, and the core questions:
home city, home timezone, language, default currency, traveller preferences) lives in the
[`onboarding`](../../onboarding/SKILL.md) skill — load it (`skill_view name='onboarding'`)
and run its welcome + intake **in the tenant's language**. This block is the **mechanical
persist** of the answers. Do not invent answers; ask again for anything missing.

Write the answers to `~/.hermes/data/oteny-travel-talent/profile.yaml` (template:
`../../profile/profile.yaml.template`). Derive, don't bake:

- `home_city` / `home_timezone` from the tenant (the origin for door-to-door routing and
  the clock for leave-by math).
- `default_currency` from the tenant (defaults the expense ledger + settle-up).
- `language` defaults to the tenant's; `traveller_prefs` is free-form (seat, diet, pace).

Then render the **two** memory files (D34 — split so a second bot never clobbers the
shared file). Fill each template's `{{placeholders}}` from `profile.yaml`, dropping any
line whose source field is unset, and write them with the file tool:

```bash
mkdir -p ~/.hermes/memories ~/.hermes/data/oteny-travel-talent
```
- render `../../profile/USER.md.template`   → `~/.hermes/memories/USER.md` (shared identity; Hermes auto-loads it into EVERY session — keep it identity-only)
- render `../../profile/memory.md.template` → `~/.hermes/data/oteny-travel-talent/memory.md` (this bot's domain memory; the triage reads it each turn)

## Remediation: `localized_bundle` (translate if needed)

If `profile.language` ≠ the active bundle language, localize the bundle with the
[`skill-translator`](../../../skill-translator/SKILL.md) default skill, then mark it:

```bash
echo "<profile.language>" > ~/.hermes/data/oteny-travel-talent/.bundle_lang
```

## Remediation: `routing` (register this bot's routing)

DM routing is native (auto-satisfies). Only when the human has **bound the bot to a trip
group** do you register the group `channel_prompt` — let the
[`index-reconciler`](../../../index-reconciler/SKILL.md) apply this bot's routing
declaration (from `../../agent-profile.yaml`); never hand-edit SOUL/config:

```bash
python3 ~/.hermes/skills/talents/index-reconciler/scripts/index_reconciler.py --apply
```

## Baseline migrations (fresh box only)

Once `selfcheck.py` prints `READY`, stamp this box's migration baseline so the
version-to-version migrations (`references/migrations.md`) never run on a box that was
**born current** — a fresh box has no prior-version state to reconcile:

```bash
python3 ~/.hermes/skills/talents/oteny-travel-talent/scripts/migrate.py --baseline
```

This marks every current migration applied **without** running it. (A pre-existing box
skips first-run, so it has no baseline and instead heals forward via the `MIGRATIONS:`
guard in triage — each migration is idempotent.)

## Re-check

Run the guard again. When it prints `READY`, proceed to plan — in the tenant's language,
grounded in the DB / the `travel` tool. (No crons are required to be READY; they are
created per-trip later.)
