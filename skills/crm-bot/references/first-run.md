# First-run — install Odoo + CRM when the owner asks

Do not install just because the engine is missing.

## What you ask

Site name is not required. Ask: event name (or use the `… Leads` group
title), admin email, language. Then: "Shall I install Odoo Community
and CRM in this box?"

Hard stop until this turn has an admin email (it contains `@`), a
language, and an explicit yes. Do not take the box login, `USER.md`,
or a found `.odoo-admin` as the admin email. The owner must type it.

Trees already present, or preflight already serving, does not skip
this ask. Do not say CRM is ready on a first sentence that only
names the event.

## Bot notes

After yes, write the answers first. Do not use `write_file` for
the profile. `write_profile.py` writes under `~/.hermes/data/crm-bot`
when that folder is writable. When it is not, it writes
`~/.hermes/crm-bot`.

1. `python3 ~/.hermes/skills/talents/crm-bot/scripts/write_profile.py`
   `--event-name "<event>" --owner-email "<email>" --language "<lang>"`
   Expect `PROFILE_WRITTEN`. If `PROFILE_WRITE_FAILED`, tell the
   owner the CRM folder could not be created. Stop. Do not say
   CRM is ready.
2. Load `odoo-community`. That Talent loads `postgres`.
3. `sh ~/.hermes/skills/talents/odoo-community/scripts/install_odoo.sh`
4. `sh ~/.hermes/skills/talents/odoo-community/scripts/install_modules.sh crm`
5. `sh ~/.hermes/skills/talents/odoo-community/scripts/ensure_odoo.sh`
6. `register_service` name `postgres`, then name `odoo-community`.
7. `python3 ~/.hermes/skills/talents/crm-bot/scripts/setup_admin.py`
   Expect `ADMIN_READY`.
8. `python3 ~/.hermes/skills/talents/crm-bot/scripts/preflight.py`
   Expect `ODOO: serving`, `JSON2: ok`, and `PROFILE: present`.

Tell the owner CRM is ready only when all three of those preflight
lines are true and `write_profile.py` printed `PROFILE_WRITTEN`. If
any of those failed, say what failed. Do not say CRM is ready.

## Ready sentence (same turn as the login door)

After ready, and after `list_hosted_websites` if they already asked
to put CRM online, tell the owner in one short message:

1. Postgres and Odoo are up. CRM is ready.
2. The public URL when a site is active, else that the link appears
   after they ask to put CRM online.
3. Log in with the admin email they typed.
4. **The secure password link in this same message.** They have no
   password until they set one there. A first-lead walk-through is
   optional after that.

Do not post the generated password. Do not ask them to type a
password, API key, or other secret in chat.

## Bot notes — password (never in chat)

The box already has a generated login. The owner does not. Hand
them a password through the private intake, then apply it.

1. `credential_status` env_var `ODOO_ADMIN_PASSWORD`.
2. `none` → `connect_account` label `CRM login password`, env_var
   `ODOO_ADMIN_PASSWORD`. Send the returned URL in the ready
   sentence.
3. `pending` → send that same URL again. Wait.
4. `leased` or `submitted` → one sentence: the password is stored;
   you apply it in about two minutes. End the turn.
5. `delivered` or `process_ready` →
   `python3 ~/.hermes/skills/talents/crm-bot/scripts/setup_admin.py`
   `--from-env ODOO_ADMIN_PASSWORD`. Expect `ADMIN_READY`. Then
   say they can log in with the email. Do not repeat the secret.

## Owner has no password

Same checklist. "I don't have a password" is this path, not a
request to paste in chat.

`host_website` only if they also want a public URL. `ensure_cmd` is
`sh ~/.hermes/skills/talents/odoo-community/scripts/ensure_odoo.sh`.
Do not treat `host_website` as the auto-start.

Do not copy PeekMSX `ensure.sh`. Do not the nightly zip. Do not
hardcode `lead-bot.oteny.bot`.
