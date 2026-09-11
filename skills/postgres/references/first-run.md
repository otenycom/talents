# First-run — install PostgreSQL 18 when the owner asks

Pulled when the owner wants a local database. The Talent files being
on disk is enough. Do **not** install just because `~/postgres` is
missing.

## What you ask

One line: "I can install PostgreSQL 18 in this box. It stays on this
box. Shall I?"

Hard stop until they say yes. No install before that.

## Bot notes — INSTALL

```
sh ~/.hermes/skills/talents/postgres/scripts/install_postgres.sh
sh ~/.hermes/skills/talents/postgres/scripts/ensure_postgres.sh
```

Then call `register_service` name `postgres`, command
`sh ~/.hermes/skills/talents/postgres/scripts/ensure_postgres.sh`.

Expect `POSTGRES_INSTALLED` then `POSTGRES_UP`. Idempotent.

A box that already has `~/odoo-site/pgdata` keeps that cluster. Do
not `initdb` again. Do not `pg_upgrade`.

## After

Tell them: **PostgreSQL is up at `127.0.0.1:5432`.** No public URL.
A later Talent may load you. You still do not start `:5432` from a
mere `skill_view`.
