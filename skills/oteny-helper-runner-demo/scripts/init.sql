-- The demo's run ledger. Idempotent: re-running it is safe.
CREATE TABLE IF NOT EXISTS helper_runs (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ran_at    TEXT NOT NULL,
    helper    TEXT NOT NULL,
    argv      TEXT NOT NULL,
    exit_code INTEGER NOT NULL
);
