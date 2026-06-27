# Check 13 — In-box migrations (forward-only state reconciliation, D99)

A converge replaces a Talent's **files**, but never its **live state** — the per-bot db,
profile/memory/overrides, and (the hard one) its **registered cron jobs** (only the agent
can re-plan those; the `cronjob` tool needs the live chat origin). So when a new version
changes the *shape* of that state, the Talent reconciles it **in-box, agent-driven**, from
a declared checklist — never an operator hand-editing the VM (VM access is exceptional:
bug-hunting, support). Required for any Talent with mutable live state (a db, or
agent-registered crons).

## What the bundle carries

- **`migrations.yaml`** at the bundle root — an ordered, **append-only, forward-only** list;
  each entry `{id, kind: sql|checklist, ref|sql, summary}`. `sql` is deterministic (the
  runner applies it against the bot db named by top-level `db:`); `checklist` needs the
  agent/tools (a `references/migrations.md` section the agent follows). Never renumber a
  shipped id.
- **The shared `scripts/migrate.py`** — a byte-identical canonical copy (drift-tested like
  `selfcheck.py`):
  - `--status [--json]` → lists pending (declared minus the applied marker); prints the
    `MIGRATIONS:` line.
  - `--apply <id>` → runs a `sql` migration (idempotent: a re-run that hits
    "duplicate column"/"already exists" is treated as done) and marks it. Refuses a
    `checklist` id (that's the agent's job).
  - `--mark <id>` → records an agent-run `checklist` migration done.
  - `--baseline` → marks **all** current migrations applied **without** running them.
- **`references/migrations.md`** — one airline-pilot checklist section per `checklist`
  migration (`## <id>`), each **detect-then-act** so an already-satisfied box no-ops.
- **Marker** `~/.hermes/data/<bot>/migrations.json` — **data plane**, so it survives every
  converge/backup/restore (D34/D62). Only `migrate.py` writes it; never ship it in a bundle
  (the upgrade-safe lint, check 12, would flag it).

## How it triggers (the load-bearing bit)

The readiness guard surfaces it, **not** first-run. `preflight` prints a
`MIGRATIONS: pending — …` line (it already opens the db, so the check is ~free), and the
engine skill's triage runs the pending checklists **before** planning — **even on a READY
box** (first-run only fires when NOT-READY, so a migration gated on first-run would never
run on an existing tenant). Lifecycle:

- **Fresh box** → first-run builds current-shape state, then `migrate.py --baseline` stamps
  every current migration applied → migrations never run on a box born current.
- **Legacy box** → no marker → all declared migrations pending → run forward; idempotent
  detect-then-act keeps an already-satisfied one a safe no-op.

Migrations are **orthogonal to readiness** — a box can be READY with pending migrations, so
they are **not** `required_artifacts.yaml` entries.

## Boundary with sidecar migrations (D52)

Sidecar migrations (`src/hermeshost/migrations/`) run by the **deployer over SSH** on the
**file layout** (dir moves, cron-name *text* retags), stamped in the on-VM manifest's
`applied_migrations`. In-box Talent migrations run by the **agent** on **live state**,
stamped in `migrations.json`. The rule: a file/dir/text op the deployer can do → sidecar
migration; anything needing the LLM or the `cronjob` tool → in-box Talent migration.

## Reference implementation

The shipped, tested **sql** example is flatbelly's `0002_food_macros` — it adds a
per-day `food_macros` rollup table and backfills it from the existing `meals` rows
(additive, idempotent, prior data preserved). See
[`../../oteny-flatbelly-talent/migrations.yaml`](../../oteny-flatbelly-talent/migrations.yaml) +
[`../../oteny-flatbelly-talent/food-tracker/references/migrations.md`](../../oteny-flatbelly-talent/food-tracker/references/migrations.md).
A **checklist** migration (anything needing the agent / the `cronjob` tool — e.g. swapping a
prior version's open-interval crons for day-bounded windowed ones) follows the same pattern
but is run by the agent from its `references/migrations.md` section and recorded with
`migrate.py --mark <id>`.

## Testing a migration offline (the dev loop)

A migration is tested **offline and deterministically** as a behavioral scenario with
`requires_migration:` — no LLM, free in CI. The scenario seeds the **prior-shape** state (a
legacy box: no migration marker, the old schema + rows), the turn applies the pending
migration, and `state:` assertions verify the new shape **and** that prior rows are
preserved; running it twice proves idempotency. The copy-paste template is
[`migration-test-template.md`](migration-test-template.md); the worked example is
flatbelly's [`tests/scenarios/macros_migration.yaml`](../../oteny-flatbelly-talent/tests/scenarios/macros_migration.yaml).
The scenario schema + runner are in [`behavioral-scenarios.md`](behavioral-scenarios.md).
