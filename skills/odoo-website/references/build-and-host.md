# Building the site + hosting it (WebsiteBot)

Loaded after INSTALL is done (`preflight.py` → `READY: yes`). This is the BUILD → HOST → CARE
detail behind the SKILL body's checklists.

## Locked build path (do not improvise)

**One path only: Odoo External JSON-2 via the shipped scripts** (`POST /json/2/<model>/<method>`
with a bearer API key). That is how you create and edit pages. Do **not** use XML-RPC /
`/jsonrpc` (deprecated in Odoo 19).

| Do | Don't |
| --- | --- |
| `ensure_site.sh` then `site_rpc.py …` | Drive the drag-and-drop builder in a browser |
| `setup_admin.py` for any admin/password / API-key change | `odoo shell`, SQL, or "reset via the database" |
| Small HTML content through `set-homepage` | Install custom modules / invent a new stack |
| Confirm copy with the owner before publish | Debate "API vs builder vs custom module" in chat |

The website builder UI exists for the **owner** in the back office after handoff — not as
your primary edit tool. You build for them over JSON-2.

## Admin credentials (bot-only file)

After INSTALL, `setup_admin.py` has already:

1. Set the admin **login/email** to `owner_email` from `profile.yaml`.
2. Generated a strong **password** (owner `/web/login`) and a persistent **API key**
   (`rpc` scope for JSON-2), stored **only** at
   `~/.hermes/data/odoo-website/.odoo-admin` (mode 0600:
   `login=` / `password=` / `api_key=`).

**Never post those secrets in chat.** `site_rpc.py` loads `api_key` itself. If auth fails,
re-run `setup_admin.py` — do not improvise a shell reset.

## Build the site

1. Make sure Odoo is up:
   ```
   sh ~/.hermes/skills/talents/odoo-website/scripts/ensure_site.sh
   ```
2. Sanity-check RPC:
   ```
   python3 ~/.hermes/skills/talents/odoo-website/scripts/site_rpc.py ping
   ```
3. Set homepage content (example):
   ```
   python3 ~/.hermes/skills/talents/odoo-website/scripts/site_rpc.py set-homepage \
     --title "Moon Skydive Club" \
     --body-html '<p>Jump from Starship. Land on the Moon. Bring snacks.</p>'
   ```
4. Add more pages later the same way (extend `site_rpc.py` or call `/json/2/` through
   `execute_code` with the same `.odoo-admin` `api_key` — still no browser builder).
5. Record what you built in `~/.hermes/data/odoo-website/memory.md`.

Work in small steps. After each meaningful change, tell the owner what changed.

Shop (`website_sale`) or booking (`website_appointment`): only if the owner asked — install
via RPC (`ir.module.module` button_immediate_install), not by improvising Apps UI clicks.

## Host it (make it public)

1. **Confirm** with the owner: "Shall I put it online at `https://<slug>.oteny.bot`?" Wait for yes.
2. Host with the built-in tool, passing the keep-alive so the platform can auto-restart Odoo:
   ```
   host_website(local_port=8069, site_slug="<slug>",
                ensure_cmd="sh /home/hermes/.hermes/skills/talents/odoo-website/scripts/ensure_site.sh")
   ```
3. Poll `list_hosted_websites` until `status: active` + `health_state: ok` (~1 min).
4. Point Odoo at the public URL:
   ```
   python3 ~/.hermes/skills/talents/odoo-website/scripts/site_rpc.py set-base-url \
     --url https://<slug>.oteny.bot
   ```
5. **Give the owner the public `url`**, then run the **owner handoff** below.

## Owner handoff — back-office login (after first host)

The owner may want to open the website editor themselves. Chat never carries a password
([credential-intake](https://oteny.com) rule). Do this, in order:

1. **Tell them the facts (no secrets):**
   - Public site: `https://<slug>.oteny.bot`
   - Back office login page: `https://<slug>.oteny.bot/web/login`
   - **Login email:** the `owner_email` they gave at setup (already configured)
2. **They choose a password (secure, not Telegram):**
   - Ask: "Want your own password for the website editor? Reply **set my website password**
     and paste it through Oteny's private credential form / connect link — never in this chat."
   - When a password arrives out-of-band as env `ODOO_WEBSITE_OWNER_PASSWORD` or a 0600 file,
     apply it:
     ```
     python3 ~/.hermes/skills/talents/odoo-website/scripts/setup_admin.py --from-env ODOO_WEBSITE_OWNER_PASSWORD
     # or:  …/setup_admin.py --password-file ~/.hermes/data/odoo-website/.owner-password-pending
     ```
     Then delete the pending file / clear the env. Confirm: "Your login email is … — open
     `/web/login` and use the password you just set."
3. **If they don't set a password:** that's fine — you keep editing for them via `site_rpc.py`.
   Do **not** email "Reset Password" unless mail is actually configured (it usually isn't on
   this embedded Odoo). Do **not** paste the generated admin password into Telegram.

## Care loop (ongoing)

- **Content edits / new pages** → `ensure_site.sh`, then `site_rpc.py` (or the same RPC
  pattern). Same public URL — no re-host.
- **Health** → `list_hosted_websites`; on `down`, run `ensure_site.sh`, re-check.
- **SEO basics:** clear titles, `web.base.url` set (above), sensible menu. Odoo generates a sitemap.
- **Take it down** → `unhost_website(site_slug="<slug>")`. The install stays; re-host anytime.

## Notes / limits (honest)

- First install on Max is usually **~3–5 minutes**, not half an hour. Later starts are seconds.
- The site is only live while the bot is **active** (archived bot → hosted site sleeps).
- The embedded database has no `pg_trgm` — fuzzy back-office search is weaker; the public site is fine.
- Requires the **Max plan** (dedicated VM). A healthy **cx23** (~4 GiB) is enough for light sites.
