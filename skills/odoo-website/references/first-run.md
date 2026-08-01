# WebsiteBot first-run — the one-time INSTALL drill

Pulled ONLY when `preflight.py` prints `READY: no`. Copy-paste-exact, mechanical, idempotent.
It captures the site details, installs Odoo, and drives to `READY`. Run it **in the owner's
language**; send the welcome + questions as short Telegram messages, not a wall of text.

## Guard (always first)

```
python3 ~/.hermes/skills/talents/odoo-website/scripts/preflight.py
```

`READY: yes` → skip this drill, go straight to BUILD/CARE. `READY: no` → continue.

## Step 1 — Welcome + intake

Greet the owner, say what you do in one line ("I build a real website inside your box and put
it online at your own address"), then ask for — in one or two short messages:

1. **What the site is** (name + one line of purpose, e.g. "Bella's Cafe — menu + opening hours").
2. **A web address name** (the subdomain `<name>.oteny.bot` — 3–30 chars, lowercase letters,
   digits, hyphens). Offer their bot's id as a default.
3. **An email** for the site's admin login (their back-office login after publish — never ask
   for a password in chat).
4. **Their language** and **timezone** (offer to detect / default to what the profile already knows).

## Step 2 — Save the profile + identity (file writes, not exec)

Write `~/.hermes/data/odoo-website/profile.yaml` by filling every field of
`~/.hermes/skills/talents/odoo-website/profile/profile.yaml.template` from the answers. Then
render the two memory files from their templates (replace every `{{placeholder}}`; drop a line
whose source field is unset):

- `~/.hermes/memories/USER.md`  ← `profile/USER.md.template`  (shared identity)
- `~/.hermes/data/odoo-website/memory.md` ← `profile/memory.md.template` (domain memory)

Create the data dir first if needed: `mkdir -p ~/.hermes/data/odoo-website`.

## Step 3 — Install Odoo (the one script — approval-clean)

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
`*.oteny.bot` / drop link as if the new site were already built. The only site engine is
Odoo via `install_odoo.sh` → `setup_admin.py` → `preflight.py` → `READY: yes`. A static
fake or a leftover hosted marker is a failed install, not a shortcut.

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

## Step 5 — Re-check → READY

```
python3 ~/.hermes/skills/talents/odoo-website/scripts/preflight.py
```

When it prints `READY: yes`, tell the owner "Your website engine is ready — what should the
site say?" and continue with BUILD in [`build-and-host.md`](build-and-host.md).

If `READY: no` persists:

```
python3 ~/.hermes/skills/talents/odoo-website/scripts/selfcheck.py
```
