# First-run — install Odoo + CRM when the owner asks

Do not install just because the engine is missing.

## What you ask

Site name is not required. Ask: event name (or use the `… Leads` group
title), admin email, language. Then: "Shall I install Odoo Community
and CRM in this box?"

Hard stop until yes.

## Bot notes

1. Load `odoo-community`. That Talent loads `postgres`.
2. `sh ~/.hermes/skills/talents/odoo-community/scripts/install_odoo.sh`
3. `sh ~/.hermes/skills/talents/odoo-community/scripts/install_modules.sh crm`
4. `sh ~/.hermes/skills/talents/odoo-community/scripts/ensure_odoo.sh`
5. `register_service` name `postgres`, then name `odoo-community`.
6. `python3 ~/.hermes/skills/talents/crm-bot/scripts/setup_admin.py`
7. `python3 ~/.hermes/skills/talents/crm-bot/scripts/preflight.py`
   Expect `ODOO: serving` and `JSON2: ok`.

Then tell the owner: **Postgres and Odoo are up. CRM is ready.**

`host_website` only if they also want a public URL. `ensure_cmd` is
`sh ~/.hermes/skills/talents/odoo-community/scripts/ensure_odoo.sh`.
Do not treat `host_website` as the auto-start.

Do not copy PeekMSX `ensure.sh`. Do not the nightly zip. Do not
hardcode `lead-bot.oteny.bot`.
