# WebsiteBot first-run — the one-time INSTALL drill

Pulled ONLY when `preflight.py` prints `READY: no`. Copy-paste-exact, mechanical, idempotent.
It captures the site details, installs Odoo (local Max), and drives to `READY`. Run it **in the
owner's language**; send the welcome + questions as short Telegram messages, not a wall of text.

## Guard (always first)

```
python3 ~/.hermes/skills/talents/odoo-website/scripts/preflight.py
```

`READY: yes` → skip this drill, go straight to BUILD/CARE. `READY: no` → continue.

## Step 1 — Welcome + intake

**Stop here until the owner answers.** Your first reply is intake only — no install, no
`site_rpc`, no `site_module`, no `host_website`, no HTML, no browser, no `oteny-drop` /
`drop.oteny.bot`.

Greet the owner, say what you do in one line ("I build a real website and put it online at
your own address"), then ask for — in one or two short messages:

1. **What the site is** (name + one line of purpose, e.g. "Bella's Cafe — menu + opening hours").
2. **A web address name** (the subdomain `<name>.oteny.bot` — 3–30 chars, lowercase letters,
   digits, hyphens). Offer their bot's id as a default.
3. **An email** for the site's admin login (their back-office login after publish — never ask
   for a password in chat).
4. **Their language** and **timezone** (offer to detect / default to what the profile already knows).
5. **Where Odoo lives** (locus) — keep it plain:
   - **On this bot (recommended)** → local site on their Max box.
   - **Odoo Online / their own Odoo URL** → remote; **a custom Odoo module is impossible**
     there (JSON-2 config only). Say that clearly if they pick Online/remote.
6. **How to build** (only if local) — if they do not know, **default to a custom module**
   (easier to recover/debug; Python + SCSS allowed). If they ask for a module but this bot
   is **not on Max**, **stop** and tell them exactly:

   > Custom Odoo modules need the **Max** plan (your own dedicated server). Upgrade in
   > Telegram with: `/oteny_subscribe upgrade max` — then come back and we continue.

   Do not install or scaffold a module until they are on Max.

## Step 2 — Save the profile + identity (file writes, not exec)

Write `~/.hermes/data/odoo-website/profile.yaml` by filling every field of
`~/.hermes/skills/talents/odoo-website/profile/profile.yaml.template` from the answers,
including:

- `odoo_locus`: `local` | `online` | `remote`
- `build_backend`: `module` (local Max default) | `json2` (Online/remote or local opt-in)
- `git_customer_facing`: `false` until they opt in
- `git_remote_url`: `""` until set

Then render the two memory files from their templates (replace every `{{placeholder}}`; drop
a line whose source field is unset):

- `~/.hermes/memories/USER.md`  ← `profile/USER.md.template`  (shared identity)
- `~/.hermes/data/odoo-website/memory.md` ← `profile/memory.md.template` (domain memory)

Create the data dir first if needed: `mkdir -p ~/.hermes/data/odoo-website`.

**Online/remote:** skip Steps 3–5 (no local install). Continue with JSON-2 BUILD against their
instance per [`build-and-host.md`](build-and-host.md) (credentials via secure intake).

## Step 3 — Install Odoo (local Max only — the one script)

Tell the owner: "Setting up your website engine — usually a few minutes on Max (~3–5); I'll
ping you when it's ready." Do **not** say 30 minutes. Then run the shipped installer (no
improvised shell — this ONE command; generous timeout / background + poll):

```
sh ~/.hermes/skills/talents/odoo-website/scripts/install_odoo.sh
```

It prints `ODOO_INSTALLED <sha>` on success. Idempotent — if interrupted, re-run. (Python venv
+ Odoo Community 19 + embedded Postgres under `~/odoo-site`.)

**Hard ban while READY: no:** never `python3 -m http.server`, never a hand-rolled static
HTML folder, never `host_website` on a non-Odoo port, never reuse an existing
`*.oteny.bot` link, and **never** `oteny-drop` / `drop.oteny.bot` (that is a file share,
not a website). The only site engine is Odoo via `install_odoo.sh` → `setup_admin.py` →
`preflight.py` → `READY: yes`. If `host_website` returns `slug_taken`, pick another slug
and retry — do **not** fall back to drop.

## Step 4 — Lock the admin login (mandatory, one script)

Odoo must be serving, then set the admin to the owner's email (password stays in-box only):

```
sh ~/.hermes/skills/talents/odoo-website/scripts/ensure_site.sh
python3 ~/.hermes/skills/talents/odoo-website/scripts/setup_admin.py
```

Expect `ADMIN_READY <owner_email>`. That also mints the JSON-2 bearer key into
`.odoo-admin` (`api_key=`) for `site_rpc.py`. **Never** invent passwords in chat, never
`odoo shell` resets, never "try another API route" — if this fails, re-run the two lines
above or `selfcheck.py`. Details: [`build-and-host.md`](build-and-host.md).

## Step 5 — Re-check → READY (+ module scaffold when backend=module)

```
python3 ~/.hermes/skills/talents/odoo-website/scripts/preflight.py
```

When it prints `READY: yes` and `build_backend: module`, scaffold the bot-owned site module
(git init included):

```
python3 ~/.hermes/skills/talents/odoo-website/scripts/site_module.py init \
  --slug <site_slug> --name "<site_name>"
```

Then tell the owner exactly:
**"Your website engine is ready — what should the site say?"**
(that exact phrase — then continue with BUILD in [`build-and-host.md`](build-and-host.md)).

Also mention (short): the site lives in a git repo the bot owns; they can later make it
customer-facing and set a remote for the bot to push to.

Do **not** say a vague "engine is ready" while still on a static file server.

If `READY: no` persists:

```
python3 ~/.hermes/skills/talents/odoo-website/scripts/selfcheck.py
```
