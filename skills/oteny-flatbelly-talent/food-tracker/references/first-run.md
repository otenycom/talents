# food-tracker — First-run setup & self-check

**You are here only because triage step 1 (`preflight.py`) or the guard printed
`NOT-READY`.** Normal turns never load this file. It is mechanical and idempotent:
run the guard for the exact missing list, run the remediation for each missing
artifact in order (declared scripts only — never improvise `python3 -c`, a heredoc,
or inline DDL; those stall on the approval gate), then re-check. The setup GOAL is
declared in `../required_artifacts.yaml`; `selfcheck.py` is the judge.

## Guard (the authoritative readiness judge)

```bash
python3 ~/.hermes/skills/talents/oteny-flatbelly-talent/scripts/selfcheck.py
```

- `READY` → setup is done. Stop here and coach.
- `NOT-READY: missing=[…]` → run the remediation for **each** listed artifact, in this
  order, then run the guard again.
- `UNKNOWN: env=[…]` → an **environment fault** (a present-but-unreadable file / a corrupt
  db), **NOT** first-run. **Do NOT run any remediation** — re-creating the db or re-running
  the intake would overwrite the owner's real (currently unreadable) data. Report the
  one-line problem to the owner and stop.

## Runtime hard rules for setup (proven on the source instance)

- **One `sqlite3` invocation per terminal call.** Never chain `INSERT`+`SELECT` in one
  call — a mid-call error lands the INSERT but errors the call, and a blind retry
  double-inserts. Verify with a separate `SELECT`.
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
mkdir -p ~/.hermes/data/oteny-flatbelly-talent
```
```bash
sqlite3 ~/.hermes/data/oteny-flatbelly-talent/food.db < ~/.hermes/skills/talents/oteny-flatbelly-talent/scripts/init.sql
```

## Remediation: `profile` (intake)

The **conversational** welcome + question set (capabilities, the why-VAT, the routine,
and the core questions incl. **waist**) lives in the [`flatbelly-onboarding`](../../flatbelly-onboarding/SKILL.md)
skill — load it (`skill_view name='flatbelly-onboarding'`) and run its welcome + intake **in the
tenant's language**. This block is the **mechanical persist** of the answers. Do not
invent answers; ask again for anything missing.

Write the answers to `~/.hermes/data/oteny-flatbelly-talent/profile.yaml` (template:
`../../profile/profile.yaml.template`). Derive, don't bake:

- `protein_target_g` = `round(1.8 × ref_weight_kg)`, kept in the 1.6–2.2 g/kg band —
  `ref_weight_kg` is current weight for lean/normal bodies, or goal weight when WHtR ≥
  0.5 with a large gap; unless the tenant gave a target.
- `leucine_threshold_g` = 2.5 (bump to 3.0 if `age >= 55` — anabolic resistance).
- target rate = the per-body-type **% of body weight/week** from
  [`fat-loss-protocol`](../../fat-loss-protocol/SKILL.md) "Deriving the natural path"
  (≤ ~1%/wk), never a fixed kg figure baked for one body.
- `timezone` defaults to the tenant's; reminders default 08:00 / 20:00 local.

Record the baseline **waist** (if given) so WHtR tracks from day one — `food.db` exists
from the `data` step (one statement per call):

```bash
sqlite3 ~/.hermes/data/oteny-flatbelly-talent/food.db "INSERT INTO waist (date, waist_cm, height_cm) VALUES (date('now'), <waist_cm>, <height_cm>) ON CONFLICT(date) DO UPDATE SET waist_cm=excluded.waist_cm, height_cm=excluded.height_cm;"
```

Then render the **two** memory files (split so a second bot never clobbers the
shared file). Fill each template's `{{placeholders}}` from `profile.yaml`, dropping any
line whose source field is unset, and write them with the file tool:

```bash
mkdir -p ~/.hermes/memories ~/.hermes/data/oteny-flatbelly-talent
```
- render `../../profile/USER.md.template`   → `~/.hermes/memories/USER.md` (shared identity; Hermes auto-loads it into EVERY session — keep it identity-only)
- render `../../profile/memory.md.template` → `~/.hermes/data/oteny-flatbelly-talent/memory.md` (this bot's domain memory; the triage reads it each turn)

## Remediation: `routing` (register this bot's routing)

Let the platform **index-reconciler** (delivered on the bot, not in this catalog)
apply this bot's routing declaration (from `../../agent-profile.yaml`) — never
hand-edit SOUL/config:

```bash
python3 ~/.hermes/skills/talents/index-reconciler/scripts/index_reconciler.py --apply
```

## Remediation: `cron` (daily reminders + weekly dashboard)

Plan the schedule list-first (create only if absent), timezone-correct from the
profile. The planner prints, for each absent job, its `schedule`, `skills`, `prompt`,
**and a `model` + `provider`** read from `config.yaml`:

```bash
python3 ~/.hermes/skills/talents/oteny-flatbelly-talent/scripts/provision_cron.py --json
```

Then register **each** `to_create` job with the `cronjob` tool, passing **every** field
the planner gave — **including `model` and `provider`**. This is mandatory: Hermes' cron
scheduler does **not** read the interactive `model.model` from `config.yaml`; an
un-pinned cron job fires with an **empty model** and the router rejects it (`HTTP 400 …
Invalid model name passed in model=`). Verify after: `cronjob` list shows a non-empty
`model` on each job.

## Re-check

Run the guard again. When it prints `READY`, proceed to coach — in the tenant's
language, grounded in the DB.
