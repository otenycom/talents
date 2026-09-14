# First-run — install Odoo + CRM when the owner asks

Load this file when preflight says `ENGINE: missing`, or they asked to
set up CRM, or they want the CRM login, or `EVENT` is `-` on a serving
box. After ready, do not load it again.

Do not install just because the engine is missing.

Read this turn's preflight first. `ENGINE: missing` is the cold path.
`ENGINE: installed` is the warm path. Do not mix them.

Do not ask "Shall I install?", "Shall I start?", or "Shall I
publish?". Asking to set up CRM is the go. No further yes after the
fields you still need.

Admin email, language, and the password link are **not** this file.
They live in odoo-community
[`references/setup.md`](../../odoo-community/references/setup.md).

If `ENGINE` is missing, `ADMIN` or `LANGUAGE` is missing, or
`ADMIN_FILE` is not `owner_set`, load that file first
(`skill_view name='odoo-community' file_path='references/setup.md'`).
Then continue this file. Do not re-ask those three.

`ADMIN_FILE: bake_placeholder` is not a finished setup. Every
prewarmed box ships a `.odoo-admin` with `login=admin` from the
mint-time secret rotation — a password nobody has seen. Treat
`bake_placeholder` exactly like `missing`.

## What you ask

Event name is CrmBot-specific. Always need it. Use the owner's words,
or the `… Leads` group title, or preflight `EVENT`. If one of those
already has it, do not ask again. If `EVENT` is `-`, ask only Event
Name. If this message already has a value, use it. If one field is
missing, ask only for that field. Do not start a new full confirm.

### Cold — no Odoo (`ENGINE: missing`)

Load odoo-community `references/setup.md` for admin email, language,
and the password link. Ask Event Name here. Do not ask those three
here.

When the password is stored, install everything and put the site
online. No further yes.

### Warm — Odoo already on the box (`ENGINE: installed`)

If community setup is already done (`ADMIN` and `LANGUAGE` are
set, and `ADMIN_FILE` is `owner_set`), skip those three. Ask only
Event Name when `EVENT` is `-`.

If `ADMIN` is `-`, `LANGUAGE` is `-`, or `ADMIN_FILE` is
`bake_placeholder` or `missing`, load odoo-community
`references/setup.md`. Do not invent a full intake.

Then install the CRM module only. Do not reinstall the engine. Do not
ask. If a site is already hosted, keep that URL. If none is hosted,
put it online without a second yes.

Trees already present do not skip a missing Event Name. Do not say
CRM is ready on a first sentence that only names the event.

## Bot notes — shared

Do not `skill_view` `postgres` or `oteny-sites`. Do not load
odoo-community `references/first-run.md`. That file is the install
drill. Call the scripts below by path. Do not `tool_describe`.

When `ADMIN` or `LANGUAGE` is missing, or `ADMIN_FILE` is not
`owner_set`, load odoo-community `references/setup.md`. Then
continue.

Do not use `write_file` for the profile. `write_profile.py` writes
under `~/.hermes/data/crm-bot` when that folder is writable. When it
is not, it writes `~/.hermes/crm-bot`. On a warm box it copies email
and language from the sibling files when you omit those flags.

```
python3 ~/.hermes/skills/talents/crm-bot/scripts/write_profile.py
--event-name "<event>"
```

Cold box: also pass `--owner-email` and `--language` from community
setup. Expect `PROFILE_WRITTEN`. If `PROFILE_WRITE_FAILED`, tell the
owner the CRM folder could not be created. Stop. Do not say CRM is
ready.

## Bot notes — password (never in chat)

If `ADMIN` or `LANGUAGE` is missing, or `ADMIN_FILE` is not
`owner_set`, load odoo-community `references/setup.md`. Then
continue. Label the link `CRM login password`. Apply with this
Talent's `setup_admin.py`.

Skip that load only when preflight says `ADMIN_FILE: owner_set`.
`bake_placeholder` is the mint-time clone-secret rotation, not a
password the owner has ever seen — always send the secure link for
it, the same as for `missing`. Do not run `setup_admin.py` without
`--from-env ODOO_ADMIN_PASSWORD` while `ADMIN_FILE` is
`bake_placeholder`; the script itself now refuses that call and
prints `ADMIN_SETUP_FAILED owner_password_required`.

"I don't have a password" is community setup, not a request to paste
in chat.

## Bot notes — cold install (no ask)

After the password is `delivered` or `process_ready`, run this list
in order. Do not ask.

1. `sh ~/.hermes/skills/talents/odoo-community/scripts/install_odoo.sh`
2. `sh ~/.hermes/skills/talents/odoo-community/scripts/install_modules.sh crm`
3. `sh ~/.hermes/skills/talents/odoo-community/scripts/ensure_odoo.sh`
4. `register_service` name `postgres`, then name `odoo-community`.
5. `python3 ~/.hermes/skills/talents/crm-bot/scripts/setup_admin.py`
   `--from-env ODOO_ADMIN_PASSWORD`. Expect `ADMIN_READY`.
6. `python3 ~/.hermes/skills/talents/crm-bot/scripts/preflight.py`
   Expect `ODOO: serving`, `JSON2: ok`, and `PROFILE: present`.
7. `host_website` port `8069`. `ensure_cmd` is
   `sh ~/.hermes/skills/talents/odoo-community/scripts/ensure_odoo.sh`.
   Do not pass a made-up host. Do not ask. Use the URL the tool
   returns.

## Bot notes — warm install (no ask)

Odoo is already there. Website may or may not be. Other modules do
not matter. After Event Name is saved, run this list. Do not ask.

1. `sh ~/.hermes/skills/talents/odoo-community/scripts/ensure_odoo.sh`
   when `ODOO: down`.
2. When `CRM` is `missing` or `unknown`:
   `sh ~/.hermes/skills/talents/odoo-community/scripts/install_modules.sh crm`
   Do not run `install_odoo.sh`.
3. When `CRM` is `installed` and `EVENT` is saved: skip that script.
4. `register_service` name `postgres`, then name `odoo-community`, if
   `list_services` does not already have them.
5. `python3 ~/.hermes/skills/talents/crm-bot/scripts/setup_admin.py`
   with no `--from-env` when `ADMIN_FILE: owner_set`. It reuses the
   sibling login. When `ADMIN_FILE` is `bake_placeholder` or
   `missing` and the password is stored, pass
   `--from-env ODOO_ADMIN_PASSWORD`. Expect `ADMIN_READY`.
6. `python3 ~/.hermes/skills/talents/crm-bot/scripts/preflight.py`
   Expect `ODOO: serving`, `JSON2: ok`, and `PROFILE: present`.
7. `list_hosted_websites`. If a site is active, use that URL. If
   none is hosted, `host_website` port `8069` with the same
   `ensure_cmd` as the cold list. Do not ask. Do not invent a host.

Tell the owner CRM is ready only when those preflight lines are
true, `write_profile.py` printed `PROFILE_WRITTEN`, and you have a
URL from `host_website` or `list_hosted_websites` (or you said no
public site is up yet because the tool failed). If any of those
failed, say what failed. Do not say CRM is ready.

## Ready sentence (same turn as the URL)

After ready, tell the owner in one short message:

1. Postgres and Odoo are up. CRM is ready.
2. The public URL from `host_website` or `list_hosted_websites`.
   Never invent a host.
3. Log in with the admin email (the one they typed, or preflight
   `ADMIN` on a warm box).
4. They log in with the password they set on the secure password link
   — the one they got on this ask, or (only when `ADMIN_FILE` was
   already `owner_set` this turn) one they set earlier. Do not repeat
   the secret. Do not send the link again unless `ADMIN_FILE` is
   `bake_placeholder` or `missing` and status is still `none` or
   `pending`.
5. A first-lead walk-through is optional after that.

Do not post a generated password. Do not ask them to type a
password, API key, or other secret in chat.

Do not copy PeekMSX `ensure.sh`. Do not the nightly zip. Do not
hardcode `lead-bot.oteny.bot`.
