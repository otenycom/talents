# Building the site + hosting it (WebsiteBot)

Loaded after INSTALL is done (`preflight.py` → `READY: yes`). This is the BUILD → HOST → CARE
detail behind the SKILL body's checklists.

## The Odoo admin login (credential-safe)

Odoo runs on `127.0.0.1:8069` inside the box with a local admin account. **Never post the admin
password in chat.** On first build:

1. Set the admin login to the owner's `owner_email` and generate a strong password IN THE BOX
   (do not choose a human one). Store it only where the box keeps it (Odoo's own DB); if you
   must record it for yourself, write it to `~/.hermes/data/odoo-website/.odoo-admin` (0600),
   never to chat or memory.md.
2. Tell the owner they can manage the site's back office at their public URL under `/odoo`
   after hosting, and that they can reset the admin password from the login page (Odoo emails
   `owner_email`). Relay a **link**, never a secret.

This follows the platform credential-intake rule: a secret never travels through chat.

## Build the site

You drive Odoo's **website builder** — a real drag-and-drop site editor — via its local admin.
Practical loop:

1. Make sure Odoo is up: `sh ~/.hermes/skills/talents/odoo-website/scripts/ensure_site.sh`.
2. Create the pages the owner asked for (home, menu, about, contact, shop, booking…). Use the
   website module's pages + snippets. Keep the owner's content in their words; confirm copy
   before publishing pages.
3. Add a shop (the `website_sale` module) only if they want to sell; a booking form
   (`website_appointment`) only if they want bookings — install the module first
   (`ensure_site.sh` re-run isn't needed; install via the Odoo Apps back office).
4. Record what you built in `~/.hermes/data/odoo-website/memory.md` (pages, theme, decisions),
   so a later turn doesn't re-ask.

Work in small steps. After each meaningful change, tell the owner what changed.

## Host it (make it public)

1. **Confirm** with the owner: "Shall I put it online at `https://<slug>.oteny.bot`?" Wait for yes.
2. Host with the built-in tool, passing the keep-alive so the platform can auto-restart Odoo:
   ```
   host_website(local_port=8069, site_slug="<slug>",
                ensure_cmd="sh /home/hermes/.hermes/skills/talents/odoo-website/scripts/ensure_site.sh")
   ```
3. Poll `list_hosted_websites` until `status: active` + `health_state: ok` (~1 min).
4. **Give the owner the public `url`.** Also set Odoo's `web.base.url` to the public URL so
   generated links (emails, sitemap, canonical tags) point at `https://<slug>.oteny.bot`, not
   `localhost` — do this in the Odoo back office System Parameters.

## Care loop (ongoing)

- **Content edits / new pages** → `ensure_site.sh` (Odoo up), edit in the builder, confirm live
  (same URL, no re-host).
- **Health** → `list_hosted_websites`; on `down`, run `ensure_site.sh` to restart Odoo, re-check.
  The platform also retries your `ensure_cmd` every reconcile tick.
- **SEO basics** the owner will appreciate: a clear page title + meta description per page, the
  `web.base.url` set (above), and a sensible menu. Odoo generates a sitemap automatically.
- **Take it down** → `unhost_website(site_slug="<slug>")`. The install stays; re-host anytime.

## Notes / limits (honest)

- The site is only live while the bot is **active** (a hosted site sleeps when the bot is
  archived). Tell the owner if they ask why it's unreachable after a long idle.
- The embedded database has no `pg_trgm`/contrib extensions — fuzzy back-office search is
  slightly less fancy, but the public site is unaffected.
- Best on the **power** plan — the site needs headroom (Odoo + its database run alongside the
  agent). On the lite plan the install refuses (too tight).
