# First-run — getting WebsiteBot ready

Pulled only when `preflight.py` prints `READY: no`. Owners answer in chat; **they never
run install commands**. You ask, save, install, then say the site engine is ready.

---

## What you ask the owner (send in chat — short messages)

Greet them, say in one line that you build a real website and put it online at their own
address, then ask — in one or two short messages — until you have answers:

1. **What the site is** — name + one line of purpose  
   (e.g. they reply: `Bella's Cafe — menu + opening hours`)
2. **A web address name** — the `<name>` in `https://<name>.oteny.bot`  
   (3–30 chars, lowercase letters, digits, hyphens; offer their bot id as default)
3. **An email** for the site's admin login (back-office later — **never** ask for a
   password in chat)
4. **Language** and **timezone** (offer to detect / use what the profile already knows)
5. **Where Odoo lives**
   - **On this bot (recommended)** → Max box
   - **Odoo Online / their own Odoo URL** → remote; say clearly: **a custom Odoo module
     is impossible** there (config via API only)
6. **How to build** (local only) — if unsure, default to a **custom module**. If they want
   a module but this bot is **not on Max**, stop and tell them to send exactly:

   ```
   /oteny_subscribe upgrade max
   ```

   Then come back. Do not install until they are on Max.

**Hard stop until they answer.** First reply = intake only — no install, no publish, no
HTML, no browser, no `oteny-drop` / `drop.oteny.bot`.

---

## Bot notes — INSTALL drill (after answers)

### Guard (always first)

```
python3 ~/.hermes/skills/talents/odoo-website/scripts/preflight.py
```

`READY: yes` → skip this file, go to BUILD/CARE. `READY: no` → continue.

### Save profile + identity

Write `~/.hermes/data/odoo-website/profile.yaml` from
`profile/profile.yaml.template` (every field), including:

- `odoo_locus`: `local` | `online` | `remote`
- `build_backend`: `module` (local Max default) | `json2` (Online/remote or local opt-in)
- `git_customer_facing`: `false` until they opt in
- `git_remote_url`: `""` until set

Render:

- `~/.hermes/memories/USER.md` ← `profile/USER.md.template`
- `~/.hermes/data/odoo-website/memory.md` ← `profile/memory.md.template`

`mkdir -p ~/.hermes/data/odoo-website` if needed.

**Online/remote:** skip local install below; continue JSON-2 BUILD in
[`build-and-host.md`](build-and-host.md) (credentials via secure intake).

### Install Odoo (local Max only)

Tell them: "Setting up your website engine — usually a few minutes on Max (~3–5); I'll
ping you when it's ready." Do **not** say 30 minutes. Then:

```
sh ~/.hermes/skills/talents/odoo-website/scripts/install_odoo.sh
```

Expect `ODOO_INSTALLED <sha>`. Idempotent if interrupted.

**While READY: no — never** `python3 -m http.server`, static HTML folders,
`host_website` on a non-Odoo port, reuse of an existing `*.oteny.bot` link, or
`oteny-drop` / `drop.oteny.bot`. Only path: `install_odoo.sh` → `setup_admin.py` →
`preflight.py` → `READY: yes`. If `host_website` later returns `slug_taken`, pick another
slug — do **not** fall back to drop.

### Lock admin login

```
sh ~/.hermes/skills/talents/odoo-website/scripts/ensure_site.sh
python3 ~/.hermes/skills/talents/odoo-website/scripts/setup_admin.py
```

Expect `ADMIN_READY <owner_email>`. Never invent passwords in chat, never `odoo shell`
resets. Details: [`build-and-host.md`](build-and-host.md).

### Re-check → READY

```
python3 ~/.hermes/skills/talents/odoo-website/scripts/preflight.py
```

When `READY: yes` and `build_backend: module`:

```
python3 ~/.hermes/skills/talents/odoo-website/scripts/site_module.py init \
  --slug <site_slug> --name "<site_name>"
```

Then tell the owner **exactly**:

**Your website engine is ready — what should the site say?**

(then BUILD in [`build-and-host.md`](build-and-host.md)). Mention briefly: the site lives
in a git repo the bot owns; they can later make it customer-facing.

If `READY: no` persists:

```
python3 ~/.hermes/skills/talents/odoo-website/scripts/selfcheck.py
```
