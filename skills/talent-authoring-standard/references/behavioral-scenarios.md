# Behavioral scenarios — the author's verification loop

A Talent is a folder of files that teaches a weak model to behave. The way you keep it
working across edits and version bumps is to ship **behavioral tests inside the bundle**
and run them two ways from one runner (`_shared/scripts/run_scenario.py`):

- **`--backend mock` (offline, deterministic, free)** — stands up a hermetic sandbox home,
  seeds the Talent's data plane (profile + db + prior-shape rows + migration marker), then
  for each turn EXECUTES the scenario's canned tool-calls (a `sql` statement, a declared
  `script`, or a `migrate` apply) and asserts the resulting **db state**. No LLM, no
  network — so CI runs it on every push. It proves the Talent's deterministic data layer
  (its SQL, scripts, and in-box migrations produce the right state) — exactly the layer
  that breaks silently across a version bump.
- **`--backend live`** — drives the real bot and reads the trace from the gateway-log
  markers. It proves the natural-language layer (routing, reply quality). Anything the mock
  can't judge — `reply`, `trace` — is **live-only**: recorded as `SKIP` offline and proven
  here.

## Where the tests live (never delivered)

Each bundle carries an author-side test tree that the deployer **never ships** to a tenant
(the delivery excludes any `tests/` directory):

```
<bundle>/tests/
  scenarios/   # *.yaml behavioral scenarios (this doc)
  fixtures/    # prior-shape SQL / data used by migration tests
  unit/        # pytest unit tests for the bundle's own scripts
```

A scenario lives at `<bundle>/tests/scenarios/<name>.yaml`; the runner resolves the bundle
as two parents up (override with `--bundle <dir>`).

## Run it

```
python3 skills/_shared/scripts/run_scenario.py skills/<bundle>/tests/scenarios/*.yaml
python3 skills/_shared/scripts/run_scenario.py --backend mock <one>.yaml --json
```

Exit code is non-zero iff any assertion failed (CI gates on it). The full result DTO is
printed to stdout; human progress goes to stderr.

## Scenario schema

```yaml
bot: oteny-flatbelly-talent          # cross-checked against the bundle's agent-profile.yaml

live_only: false                      # true (or a list containing "scenario") -> whole
                                      # scenario is SKIPped offline (live-only behaviour)

requires_migration: 0002_food_macros  # optional: asserts this migration is DECLARED and
                                      # PENDING after seed (a genuine upgrade-from-prior-state)

assert_selfcheck_ready: true          # optional: after seed, assert selfcheck READY (true)
                                      # or NOT-READY (false) — the deterministic protocol gate

seed:                                 # how the sandbox data plane is built before turns run
  db: food.db                         # the Talent's sqlite db (default: from required_artifacts.yaml)
  init_sql: scripts/init.sql          # schema to apply (default: auto-detect scripts/init.sql)
  profile: {goal_weight_kg: 85, ...}  # -> ~/.hermes/data/<bot>/profile.yaml
  user_md: "..."                      # -> ~/.hermes/memories/USER.md (shared identity)
  memory: "..."                       # -> ~/.hermes/data/<bot>/memory.md (domain memory)
  cron_jobs: ["<job name>", ...]      # -> ~/.hermes/cron/jobs.json (for the cron selfcheck)
  sql: |                              # prior-shape rows (the legacy state a migration reconciles)
    INSERT INTO meals (...) VALUES (...);
  migrations: baseline                # 'baseline' = born-current box (all current applied);
                                      # a list of ids = pre-mark those applied;
                                      # absent = LEGACY box (no marker -> all declared pending)

turns:
  - user: "log 76 kg this morning"    # the message (informational in mock)
    expect:
      tool_calls:                     # canned, deterministic — EXECUTED in mock, asserted in live
        - sql: "INSERT INTO weight(date, weight_kg, period) VALUES (date('now'), 76, 'morning')"
        - script: scripts/x.py        # a DECLARED bundle script (args, stdin optional; allow_fail)
        - migrate: 0002_food_macros   # apply a deterministic (sql) in-box migration
      state:                          # db-grounded ground truth (the mock's real assertions)
        - query: "SELECT weight_kg FROM weight WHERE period='morning' ORDER BY id DESC LIMIT 1"
          equals: 76                  # scalar equality (float-tolerant)
        - query: "SELECT COUNT(*) FROM weight"
          count: 1                    # row count   (also: nonempty: true)
        - table_exists: food_macros   # a table is present
      reply: "confirms the weigh-in"  # LIVE-ONLY -> SKIP in mock
      trace: [...]                    # LIVE-ONLY -> SKIP in mock
    assert: scripts/checks.py::fn     # optional escape hatch: import + call fn(ctx); ctx gives
                                      # {home, hermes_home, data_dir, bot, bundle, db}. Use for a
                                      # ground-truth assertion the declarative form can't express
                                      # (e.g. a /json/2/ check on a seam-backed Talent — live-only).
```

### State assertion verbs

| verb | passes when |
|---|---|
| `equals: <v>` | the query's first row/column equals `<v>` (numbers compared float-tolerant) |
| `count: <n>` | the query returns exactly `<n>` rows |
| `nonempty: true` | the query returns ≥1 row (`false` = returns none) |
| `table_exists: <name>` | a table `<name>` exists in the db |

## Worked examples (flatbelly, the reference Talent)

- [`oteny-flatbelly-talent/tests/scenarios/weight_log.yaml`](../../oteny-flatbelly-talent/tests/scenarios/weight_log.yaml)
  — a set-up box logs a morning weigh-in; asserts the `food.db` row and a READY selfcheck.
- [`oteny-flatbelly-talent/tests/scenarios/macros_migration.yaml`](../../oteny-flatbelly-talent/tests/scenarios/macros_migration.yaml)
  — a box upgraded from before `0002_food_macros` reconciles its db in-box: the pending
  migration adds the rollup table and backfills it, preserving every prior meal and weigh-in.

See also the migration test offline template (`tests/migration_e2e.py` + `tests/fixtures/`)
in [`in-box-migrations.md`](in-box-migrations.md) for the pytest-shaped equivalent of the
migration scenario.
