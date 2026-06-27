# Migration test template (offline, deterministic)

Copy this scenario into your bundle at `tests/scenarios/<id>_migration.yaml`, adapt the
db/schema/rows/asserts to your migration, and run it offline & free:

```
python3 skills/_shared/scripts/run_scenario.py skills/<bundle>/tests/scenarios/<id>_migration.yaml
```

It proves the four things a migration must get right: it **applies** on a box upgraded from
the prior version, it produces the **new shape**, it **preserves prior rows** (additive, no
data loss), and it is **idempotent** (a re-apply is a safe no-op).

```yaml
bot: <your-bot-slug>

seed:
  # No `migrations:` key  -> a LEGACY box: no marker, so every declared migration is pending
  # (a box upgraded from before this migration). seed.sql is the PRIOR-SHAPE fixture — the
  # old schema's rows, exactly as they existed before the migration.
  sql: |
    INSERT INTO <prior_table> (<cols>) VALUES (<prior rows>);

requires_migration: <id>            # asserts <id> is DECLARED and PENDING after seed

turns:
  - user: "<a message that makes the agent reconcile the db>"
    expect:
      tool_calls:
        - migrate: <id>             # apply the pending deterministic (sql) migration
      state:
        # 1. the NEW shape exists ...
        - table_exists: <new_table>
        # 2. ... and is correctly populated (assert a backfilled value, float-tolerant) ...
        - query: "SELECT <col> FROM <new_table> WHERE <key> = '<k>'"
          equals: <expected>
        # 3. ... and PRIOR rows are preserved (additive migration, no data loss).
        - query: "SELECT COUNT(*) FROM <prior_table>"
          equals: <prior_row_count>
      reply: "<live-only: how the agent phrases the answer>"
```

**Idempotency** is covered for free: the runner builds a fresh sandbox each run, and `migrate.py
--apply` is detect-then-act, so a re-apply recomputes the same totals without dropping a row.
To assert it explicitly in one box, list the `migrate:` tool-call **twice** in the same turn
and assert the row count / totals are unchanged (see the test
`test_migration_idempotent_within_one_box`).

If your migration is a `checklist` kind (it needs the agent / the `cronjob` tool), it is not
applied by `migrate: <id>` — drive it as a live scenario and `migrate.py --mark <id>` it; mark
the natural-language steps `live_only`.

The worked, shipped example is flatbelly's
[`tests/scenarios/macros_migration.yaml`](../../oteny-flatbelly-talent/tests/scenarios/macros_migration.yaml)
(migration [`0002_food_macros`](../../oteny-flatbelly-talent/migrations.yaml)).
