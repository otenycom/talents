# Owner setup — admin email, language, password, site name

This file owns the owner facts every Odoo module Talent shares:
admin email, language, and password always; the public site name
only on a fresh install (no other Talent asks it once this file
has). Install is a different file:
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
3. **Site name** — only when `ENGINE` is missing (a fresh
   install). Ask for "the name in your public web address" —
   never say "slug." Offer the tenant ref as a default if they
   have no preference. On a warm box, do not ask this; the
   address (if any) already exists.

Then send the secure password link. Never ask them to type a
password in chat.

A module Talent must not re-ask a field this file already has.
Event Name and other module-specific extras stay on that Talent.
The site's public name is covered here, cold installs only — see
below.

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
- **Site name** sits as `site_slug` in the same `profile.yaml` as
  email and language. A later Talent prints `SITE_NAME`. A
  sibling Talent's already-claimed name counts as implicit too —
  do not ask again just because this Talent's own profile is
  the one still missing it.

Never treat `login=admin` as the owner email. A later Talent
prints `ADMIN`, `LANGUAGE`, and `ADMIN_FILE`. A printed email
with `@` is implicit. `ADMIN_FILE` is one of three states:

- `owner_set` — the stored login is a real email. Only this state
  means the owner already has a password. Skip the intake.
- `bake_placeholder` — a `.odoo-admin` exists and parses, but the
  login is not an email. Every prewarmed box ships this file:
  mint time rotates the shared bake password to a fresh, unknown
  value for security, but the login stays the literal `admin`,
  because no owner is known yet. Nobody has seen that password.
  Treat this exactly like `missing`.
- `missing` — no `.odoo-admin` parses at all.

A `bake_placeholder` file is not evidence of a finished setup. It
is proof the opposite is true: this box has never had an owner
password. Always run the intake below when `ADMIN_FILE` is
`bake_placeholder` or `missing`, the same as on a genuinely fresh
box.

## Bot notes — when to load this file

A module Talent loads this file when `ENGINE` is missing, `ADMIN`
or `LANGUAGE` is missing, or `ADMIN_FILE` is not `owner_set`.
Then it continues its own setup.

```
skill_view name='odoo-community' file_path='references/setup.md'
```

Do not load this file once `ADMIN` and `LANGUAGE` are set and
`ADMIN_FILE` is `owner_set`, unless they said they have no
password.

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

## Bot notes — site name taken

`host_website` refuses a name already claimed by another tenant:
`{"ok": false, "reason": "slug_taken", "site_slug": "<name>"}`.
This is the platform's own global uniqueness check — there is no
separate availability check to call first. Only react to it when
it actually happens.

1. First `host_website` call uses the owner's own name, exactly
   as given. Success ends this — the one-shot path is unchanged.
2. On `slug_taken`, retry **silently, with no question to the
   owner**: append a random 3-digit number (`<name>-482`) and
   call `host_website` again. If that also comes back
   `slug_taken`, retry once more with a **different** random
   3-digit number (`<name>-107`). Two silent retries total,
   always under a name that was not just refused — a repeat call
   under the same name reads as a collision against your own
   reservation, not as "this one is already yours." If the base
   name is already at the 30-character limit, shorten it before
   appending the suffix.
3. The moment any call succeeds — first try or either retry —
   bring the site online and say clearly, in the same ready
   message, which public address the owner actually got. A
   silent retry is not a silent substitution: always name the
   final address, even when the owner was never asked in between.
4. Only if all three calls (the original name plus both random
   retries) come back `slug_taken` do you ask the owner for a
   different name — a real question, asked after the rest of
   setup has already finished, not before. Their answer restarts
   this same recipe from step 1.
5. The owner can change their mind later: `unhost_website` then
   `host_website` under a new name already does this. Nothing
   else to build for that — mention it in passing if they ask
   about changing the address.

Every other `host_website` failure (`bad_slug`, `reserved_slug`,
`reserved_prefix`, `too_many_sites`, `disabled`, `no_tenant`) is
covered by the existing rule: say what failed, never invent a
host, never say "ready" on a failure. Only `slug_taken` gets this
retry, because it is the only reason a different name fixes.
