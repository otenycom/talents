# First-run — getting WebsiteBot ready

Pulled only when `preflight.py` prints `READY: no`. Owners answer in
chat; **they never run install commands**. You ask, save, install,
then say the site engine is ready.

Admin email, language, and the password link are **not** this file.
They live in odoo-community
[`references/setup.md`](../../odoo-community/references/setup.md).
Load that file when `ENGINE` is missing, when `ADMIN` or
`LANGUAGE` is missing, or when `ADMIN_FILE` is not `owner_set`.
Then continue this file.

`ADMIN_FILE: bake_placeholder` is not a finished setup. Every
prewarmed box ships a `.odoo-admin` with `login=admin` from the
mint-time secret rotation — a password nobody has seen. Treat
`bake_placeholder` exactly like `missing`.

---

## What you ask the owner (send in chat — short messages)

Greet them, say in one line that you build a real website and put it
online at their own address, then ask — in one or two short messages
— until you have answers:

1. **What the site is** — name + one line of purpose
   (e.g. they reply: `Bella's Cafe — menu + opening hours`)
2. **A web address name** — the `<name>` in
   `https://<name>.oteny.bot`
   (3–30 chars, lowercase letters, digits, hyphens; offer their bot
   id as default)
3. **Timezone** (offer to detect / use what the profile already
   knows)
4. **Where Odoo lives**
   - **On this bot (recommended)** → Max box
   - **Odoo Online / their own Odoo URL** → remote; say clearly: **a
     custom Odoo module is impossible** there (config via API only)
5. **How to build** (local only) — if unsure, default to a **custom
   module**. If they want a module but this bot's box is **too
   small**, stop and tell them to send exactly:

   ```
   /oteny_subscribe upgrade power
   ```

   Then come back. Do not install until the box is big enough.

Do **not** ask admin email, language, or a password here. If
`ADMIN` or `LANGUAGE` is missing, or `ADMIN_FILE` is not
`owner_set`, load odoo-community `references/setup.md` and ask
only the missing field there. If community setup already has
`ADMIN` and `LANGUAGE`, and `ADMIN_FILE` is `owner_set`, skip
them.

**Hard stop until they answer.** First reply = intake only — no
install, no publish, no HTML, no browser, no `oteny-drop` /
`drop.oteny.bot`.

---

## Bot notes — INSTALL drill (after answers)

### Guard (always first)

```
python3 ~/.hermes/skills/talents/odoo-website/scripts/preflight.py
```

`READY: yes` → skip this file, go to BUILD/CARE. `READY: no` →
continue.

If `ADMIN` or `LANGUAGE` is missing (no owner email or no language),
or `ADMIN_FILE` is not `owner_set` (no `.odoo-admin`, or only a
mint-time `bake_placeholder` login), load

```
skill_view name='odoo-community' file_path='references/setup.md'
```

Then continue this file. Do not re-ask those three.

### Save profile + identity

Do not use `write_file` for the profile. Run:

```
python3 ~/.hermes/skills/talents/odoo-website/scripts/write_profile.py \
  --site-name "<name>" --site-purpose "<purpose>" --site-slug "<slug>" \
  --owner-email "<email>" --language "<lang>" --timezone "<tz>" \
  --odoo-locus local --build-backend module --git-customer-facing false
```

Pass `--owner-email` and `--language` from community setup (or from
the profile that already has them). Expect `PROFILE_WRITTEN`. Fields
match `profile/profile.yaml.template`
(`odoo_locus`, `build_backend`, `git_customer_facing`,
`git_remote_url`). If `PROFILE_WRITE_FAILED`, tell the owner the
folder could not be created. Stop. Do not say the website engine is
ready.

Then render:

- `~/.hermes/memories/USER.md` ← `profile/USER.md.template`
- `~/.hermes/data/odoo-website/memory.md` ← `profile/memory.md.template`

**Online/remote:** skip local install below; continue JSON-2 BUILD in
[`build-and-host.md`](build-and-host.md) (credentials via secure
intake).

### Install the local engine (Power or Max only)

Load `odoo-community` (`skill_view name='odoo-community'`). That
Talent loads `postgres`. Tell them: "Setting up your website engine
— usually a few minutes (~3–5, longer on a smaller box); I'll ping
you when it's ready." Do **not** say 30 minutes. Hard-stop until
they answered intake **and** said yes to the local engine. Then:

1. `sh ~/.hermes/skills/talents/odoo-community/scripts/install_odoo.sh`
   Expect `ODOO_INSTALLED`.
2. `sh ~/.hermes/skills/talents/odoo-community/scripts/install_modules.sh website`
3. `sh ~/.hermes/skills/talents/odoo-community/scripts/ensure_odoo.sh`
   Expect `ODOO_UP`.
4. `register_service` name `postgres`, then name `odoo-community`.

Do not call `odoo-website/scripts/install_odoo.sh`. Use the
community scripts above. Never `pgserver`. Never the nightly zip.
Idempotent if interrupted.

**While READY: no — never** `python3 -m http.server`, static HTML
folders, `host_website` on a non-Odoo port, reuse of an existing
`*.oteny.bot` link, or `oteny-drop` / `drop.oteny.bot`. Only path:
community `install_odoo.sh` → `install_modules.sh website` →
`setup_admin.py` → `preflight.py` → `READY: yes`. If `host_website`
later returns `slug_taken`, pick another slug — do **not** fall
back to drop.

### Lock admin login

```
sh ~/.hermes/skills/talents/odoo-website/scripts/ensure_site.sh
```

Check preflight's `ADMIN_FILE` first. Not `owner_set`
(`bake_placeholder` — the mint-time secret rotation, never a
password the owner has seen — or `missing`) → go to "Bot notes —
password" below and apply with `--from-env ODOO_ADMIN_PASSWORD`.
Do not call `setup_admin.py` bare while `ADMIN_FILE` is
`bake_placeholder`; the script now refuses that call and prints
`ADMIN_SETUP_FAILED owner_password_required`.

`ADMIN_FILE: owner_set` → reuse it:

```
python3 ~/.hermes/skills/talents/odoo-website/scripts/setup_admin.py
```

Expect `ADMIN_READY <owner_email>`. Never invent passwords in chat,
never `odoo shell` resets. Password protocol: odoo-community
`references/setup.md`. Label: `Website back-office password`.
Details: [`build-and-host.md`](build-and-host.md).

### Re-check → READY

```
python3 ~/.hermes/skills/talents/odoo-website/scripts/preflight.py
```

When `READY: yes` and `build_backend: module`:

```
python3 ~/.hermes/skills/talents/odoo-website/scripts/site_module.py init \
  --slug <site_slug> --name "<site_name>"
```

Then tell the owner **exactly** this sentence, and only when
`write_profile.py` printed `PROFILE_WRITTEN` and preflight shows
`READY: yes`:

**Postgres and Odoo are up. Your website engine is ready — what should the site say?**

Keep that sentence exact. In the **same turn**, offer the
back-office login: the admin email plus the secure password link
(community setup). A first-page walk-through stays optional. Do not
wait for them to ask. Do not ask them to type a password in chat.

(then BUILD in [`build-and-host.md`](build-and-host.md)). Mention
briefly: the site lives in a git repo the bot owns; they can later
make it customer-facing.

## Bot notes — password (never in chat)

If `ADMIN` or `LANGUAGE` is missing, or `ADMIN_FILE` is not
`owner_set` (`bake_placeholder` counts), load odoo-community
`references/setup.md`. Then continue. Label the link `Website
back-office password`. Apply with

```
python3 ~/.hermes/skills/talents/odoo-website/scripts/setup_admin.py
--from-env ODOO_ADMIN_PASSWORD
```

Expect `ADMIN_READY`.

## Owner has no password

Same path. "I don't have a password" and "I want the back-office
login" load community setup. They are not a request to paste in
chat.

If `READY: no` persists:

```
python3 ~/.hermes/skills/talents/odoo-website/scripts/selfcheck.py
```
