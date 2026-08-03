# Building the site + hosting it (WebsiteBot)

Loaded after INSTALL is done (`preflight.py` → `READY: yes`), or for Online/remote after
credentials land. This is the BUILD → HOST → CARE detail behind the SKILL body.

## Pick the locked path (do not debate)

Read `build_backend` + `odoo_locus` from `~/.hermes/data/odoo-website/profile.yaml`.

| `build_backend` | When | Edit with |
| --- | --- | --- |
| **`module`** (default on local Max) | Local Odoo on this Max VM | `site_module.py` (files → `-u`) |
| **`json2`** | Odoo Online / remote URL, or local opt-in | `site_rpc.py` (External JSON-2) |

- **Online/remote:** custom module is **impossible** — always `json2`.
- **Not on Max but wants module:** stop and send `/oteny_subscribe upgrade max`.
- Never invent a third stack. Never `python -m http.server` / `oteny-drop`.

| Do | Don't |
| --- | --- |
| Follow `build_backend` from the profile | Debate module vs RPC in chat |
| `ensure_site.sh` before local edits | Browser drag-and-drop as the primary editor |
| `setup_admin.py` for admin/password / API-key | `odoo shell` / SQL password resets |
| Confirm before first publish | Fall back to drop.oteny.bot |

## Admin credentials (bot-only file, local)

After local INSTALL, `setup_admin.py` has already set admin email + password + JSON-2
`api_key` in `~/.hermes/data/odoo-website/.odoo-admin` (mode 0600). **Never post secrets in
chat.** `site_rpc.py` loads `api_key` itself.

## BUILD — module path (default on Max/local)

1. Ensure Odoo is up:
   ```
   sh ~/.hermes/skills/talents/odoo-website/scripts/ensure_site.sh
   ```
2. Scaffold once (idempotent; creates git repo):
   ```
   python3 ~/.hermes/skills/talents/odoo-website/scripts/site_module.py init \
     --slug <slug> --name "<site_name>"
   ```
3. Set homepage (writes QWeb XML + optional SCSS lives under
   `~/odoo-site/addons/oteny_site_<slug>/`, then `-u`):
   ```
   python3 ~/.hermes/skills/talents/odoo-website/scripts/site_module.py set-homepage \
     --title "Moon Skydive Club" \
     --body-html '<p>Jump from Starship. Land on the Moon. Bring snacks.</p>'
   ```
4. Python controllers/models and `static/src/scss/site.scss` are allowed — edit files in the
   module, then:
   ```
   python3 ~/.hermes/skills/talents/odoo-website/scripts/site_module.py upgrade
   ```
5. **Git:** bot-owned by default. Ask once (and again later): want this repo customer-facing?
   If yes → remote URL via Oteny credential intake (never Telegram) →
   `site_module.py git-remote --url <url>`.
6. Record what you built in `~/.hermes/data/odoo-website/memory.md`.

**UI note:** the Website Builder can edit pages, but **module upgrades can overwrite** those
edits. Prefer chat/module as source of truth in module mode.

## BUILD — JSON-2 path (Online / opt-in local)

1. Local: `ensure_site.sh` then `site_rpc.py ping`. Online/remote: use their base URL + API
   key from secure intake (extend `site_rpc` / env as needed — still External JSON-2, never
   XML-RPC).
2. Homepage:
   ```
   python3 ~/.hermes/skills/talents/odoo-website/scripts/site_rpc.py set-homepage \
     --title "…" --body-html "…"
   ```
3. Builder UI is fine for the owner after handoff in JSON-2 mode.

Shop (`website_sale`) / booking (`website_appointment`): only if asked — install via RPC
(`ir.module.module` button_immediate_install) on local, or Apps on Online.

## Host it (local Max — make it public)

1. **Confirm:** "Shall I put it online at `https://<slug>.oteny.bot`?" Wait for yes.
2. Host:
   ```
   host_website(local_port=8069, site_slug="<slug>",
                ensure_cmd="sh /home/hermes/.hermes/skills/talents/odoo-website/scripts/ensure_site.sh")
   ```
3. Poll `list_hosted_websites` until `status: active` + `health_state: ok` (~1 min).
4. Base URL:
   ```
   python3 ~/.hermes/skills/talents/odoo-website/scripts/site_rpc.py set-base-url \
     --url https://<slug>.oteny.bot
   ```
5. Give the public URL, then owner handoff below.
6. **Custom domain (optional):** see [`custom-domain.md`](custom-domain.md) —
   preferred Cloudflare CNAME → `customers.oteny.bot`; AWS Route53 = www + apex redirect.
   After SSL active, re-run `set-base-url` to the vanity HTTPS URL.

## Owner handoff — back-office login (after first host, local)

1. Facts (no secrets): public URL, `/web/login`, login **email** = `owner_email`.
2. Password via private credential form / connect link — never chat. Apply with
   `setup_admin.py --from-env` / `--password-file`.
3. If module mode: remind that Website Builder edits may be overwritten when the bot
   upgrades the site module.

## Care loop

- **Module edits** → edit files → `site_module.py upgrade` (or `set-homepage`).
- **JSON-2 edits** → `site_rpc.py`.
- **Down?** → `list_hosted_websites` + `ensure_site.sh`.
- **Take down** → `unhost_website(site_slug="<slug>")`.

## Notes / limits (honest)

- First local install on Max is usually **~3–5 minutes**. Later starts are seconds.
- Module backend requires **Max** (`/oteny_subscribe upgrade max` if they are not).
- Online/remote: any plan, JSON-2 only — no custom module.
- The site is only live while the bot is **active**.
