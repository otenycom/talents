# Owner setup — admin email, language, password

This file owns the three owner facts every Odoo module Talent
shares. Install is a different file:
[`first-run.md`](first-run.md). That file starts Odoo when the
owner asks. This file does not install.

WebsiteBot and CrmBot load this file. They do not ask these
facts again once the facts are on disk.

## What you ask (only if missing)

Ask in one or two short messages. If this message already has a
value, use it. If one field is missing, ask only for that field.
Do not start a new full confirm.

1. **Admin email** — they must type it. It contains `@`. Do not
   take the box login, `USER.md`, or a default `admin` login.
   Never treat `admin` as the owner email.
2. **Language** — offer to detect / use what the profile already
   knows.

Then send the secure password link. Never ask them to type a
password in chat.

A module Talent must not re-ask a field this file already has.
Event Name, site title, hostname, and other extras stay on that
Talent.

## Where those facts live

A later Talent preflights these paths. Treat a printed value as
implicit. Do not re-ask it.

- **Email and language** sit in the module Talent's
  `profile.yaml`. WebsiteBot writes
  `~/.hermes/data/odoo-website/profile.yaml`. CrmBot writes
  `~/.hermes/data/crm-bot/profile.yaml`. When `~/.hermes/data`
  is not writable, the same file sits under
  `~/.hermes/odoo-website/` or `~/.hermes/crm-bot/`.
- **Password and login** sit in `.odoo-admin` (mode `0600`).
  Lines are `login=`, `password=`, and `api_key=`. WebsiteBot
  `setup_admin.py` writes
  `~/.hermes/data/odoo-website/.odoo-admin`. CrmBot
  `setup_admin.py` uses the same file shape. CrmBot also reads
  the WebsiteBot sibling file.

Never treat `login=admin` as the owner email. A later Talent
prints `ADMIN`, `LANGUAGE`, and `ADMIN_FILE`. A printed email
with `@` is implicit. `ADMIN_FILE: present` means the password
file is already there.

## Bot notes — when to load this file

A module Talent loads this file when `ENGINE` is missing, or
when `ADMIN`, `LANGUAGE`, or `ADMIN_FILE` is missing. Then it
continues its own setup.

```
skill_view name='odoo-community' file_path='references/setup.md'
```

Do not load this file after those three facts are present,
unless they said they have no password.

## Bot notes — password (never in chat)

The owner has no password until they set one on the private
intake. The env var is `ODOO_ADMIN_PASSWORD`. The module Talent
names the `connect_account` label (WebsiteBot: `Website
back-office password`. CrmBot: `CRM login password`).

1. `credential_status` env_var `ODOO_ADMIN_PASSWORD`.
2. `none` → `connect_account` with that label and env_var
   `ODOO_ADMIN_PASSWORD`. Send the returned URL. Wait.
3. `pending` → send that same URL again. Wait.
4. `leased` or `submitted` → one sentence: the password is
   stored; you continue next. End the turn.
5. `delivered` or `process_ready` → the module Talent runs its
   own `setup_admin.py --from-env ODOO_ADMIN_PASSWORD`. Expect
   `ADMIN_READY`.

"I don't have a password" and "I want the login" are this path,
not a request to paste in chat.

Do not invent a password. Do not post one. Do not ask them to
type one in chat.
