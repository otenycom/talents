# WebsiteBot in-box migrations

## 0001_register_local_stack

Detect-then-act. A box born current already ran `--baseline` after first
install. A legacy box has no `migrations.json`, or a marker that lacks
this id.

1. Run `list_services`.
2. If `~/odoo-site` is missing, or preflight says Odoo Online / remote,
   there is no local Odoo. If `~/postgres` and `~/odoo-site/pgdata` are
   also missing, skip to step 6. If only Postgres is present, register
   `postgres` if needed, then skip to step 6.
3. If `postgres` is missing from `list_services` and a local cluster
   exists (`~/postgres/data` or `~/odoo-site/pgdata`), call
   `register_service` name `postgres`, command
   `sh ~/.hermes/skills/talents/postgres/scripts/ensure_postgres.sh`.
4. If `odoo-community` is missing and `~/odoo-site` exists, call
   `register_service` name `odoo-community`, command
   `sh ~/.hermes/skills/talents/odoo-community/scripts/ensure_odoo.sh`.
5. `list_services` must then show every service that step 3 or 4
   registered.
6. Mark it:

   ```
   python3 ~/.hermes/skills/talents/odoo-website/scripts/migrate.py --mark 0001_register_local_stack
   ```

A take-down of the public URL does not unregister this service.
`unregister_service` runs only when the owner asked to stop the local
stack. Do not invent a third recipe.
