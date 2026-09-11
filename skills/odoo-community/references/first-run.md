# First-run — install Odoo Community 19.0 when the owner asks

Do not install just because `~/odoo-site` is missing.

## What you ask

"I can install Odoo Community 19.0 in this box. It needs a local
PostgreSQL. Shall I?"

Hard stop until yes.

## Bot notes

1. If both `~/postgres` and `~/odoo-site/pgdata` are missing, run
   postgres INSTALL (`install_postgres.sh` + `register_service`
   name `postgres`).
2. `sh ~/.hermes/skills/talents/odoo-community/scripts/install_odoo.sh`
3. `sh ~/.hermes/skills/talents/odoo-community/scripts/ensure_odoo.sh`
4. `register_service` name `postgres` and name `odoo-community`.

Expect `ODOO_INSTALLED` then `ODOO_UP`. The tree is a **shallow**
git clone of branch `19.0`. Check `rev-parse --is-shallow-repository`
is `true`. Check `odoo/release.py` is major 19.

WebsiteBot and CrmBot load you. You still do not `-i website` or
`-i crm`. You still do not install because the tree is missing.

Then tell the owner: **Postgres and Odoo are up.**

Do not `-i website`. Do not the nightly zip.
