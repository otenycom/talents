# First run — create the run ledger

The demo keeps one piece of state: a ledger of every helper run, in a local
sqlite database. On first use (the `sqlite_db` artifact in
`required_artifacts.yaml` is missing), create it from the shipped schema:

```
mkdir -p ~/.hermes/data/oteny-helper-runner-demo
sqlite3 ~/.hermes/data/oteny-helper-runner-demo/runs.db < skills/talents/oteny-helper-runner-demo/scripts/init.sql
```

The schema is idempotent (`CREATE TABLE IF NOT EXISTS`), and every helper
re-applies it before it writes, so a first `talent_run` call also creates the
ledger. Then `selfcheck` reports READY.
