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
3. **An email** for the site's admin login (Odoo sends the login there; never a password in chat).
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

Tell the owner "Setting up your website engine — this takes a while (up to ~30 minutes the
first time, while it downloads and prepares everything); I'll let you know when it's ready."
It's a ONE-TIME setup — later starts are fast. Then run the shipped installer (no improvised
shell — this ONE command does the whole install; run it with a generous timeout / in the
background and poll, don't block the chat on it):

```
sh ~/.hermes/skills/talents/odoo-website/scripts/install_odoo.sh
```

It prints `ODOO_INSTALLED <sha>` on success. It's idempotent — if it's interrupted, just run
it again. (It sets up a Python venv + Odoo Community 19 + an embedded database under
`~/odoo-site`, all in your home so it survives box maintenance.)

## Step 4 — Re-check → READY

```
python3 ~/.hermes/skills/talents/odoo-website/scripts/preflight.py
```

When it prints `READY: yes`, the setup is done. Tell the owner "Your website engine is ready —
what would you like the site to say?" and continue with the BUILD checklist in
[`build-and-host.md`](build-and-host.md).

If `READY: no` persists, run the authority check for the exact missing list and fix it:

```
python3 ~/.hermes/skills/talents/odoo-website/scripts/selfcheck.py
```
