# Custom domain — what to type in chat

Your site must already be live at `https://<slug>.oteny.bot`. Then talk to your
OtenyBot in Telegram (or web chat). **Copy the lines below**, swap in your domain
and site name, and send them one step at a time. You never run tools or code —
the bot does that.

---

## 1. Ask the bot to attach your domain

Send:

```
Attach my domain example.com to site <slug> (include www).
My DNS is on Cloudflare (free is fine).
```

That covers both `example.com` and `www.example.com`. You do not need a special
`+www` flag.

**What to expect back:** the bot confirms, then gives you DNS rows. Enter them in
Cloudflare → DNS (Proxied / orange cloud):

| Type | Name | Content |
|------|------|---------|
| CNAME | `@` | `customers.oteny.bot` |
| CNAME | `www` | `customers.oteny.bot` |

If it also asks for a TXT ownership record, add that too.

**Do not** point DNS at `https://<slug>.oteny.bot` or CNAME to `<slug>.oteny.bot`
— on Cloudflare that shows Error **1014**. Always use `customers.oteny.bot`.

---

## 2. Check when the certificate is ready

After DNS is saved, wait a bit, then send:

```
What's the status of my custom domains on site <slug>?
```

Repeat until the bot says the domain and SSL are **active** (often 15–30 minutes
after DNS).

---

## 3. Make that domain the site's public address

When status is active, send:

```
Set my site's public URL to https://example.com
```

Then open `https://example.com` and `https://www.example.com` in a browser.

---

## If your DNS is on AWS Route53 (not Cloudflare)

Route53 cannot CNAME the bare domain the same way. Send this instead of step 1:

```
Attach only www.example.com to site <slug>.
I'll redirect the bare domain to www myself on Route53.
```

Then follow the bot's DNS instructions (`www` → `customers.oteny.bot`, apex redirect
to `https://www…`). When ready, send:

```
Set my site's public URL to https://www.example.com
```

Prefer Cloudflare DNS if you want the bare domain itself to work without a separate
redirect setup.

---

## Remove a domain later

```
Remove custom domain www.example.com from site <slug>.
```

---

## Bot notes (when the owner sends the lines above)

- Step 1 → confirm → `attach_site_domains(site_slug=…, domain="example.com")`
  (apex + www). Route53 line → `hostnames=["www.example.com"]` only.
- Reply with the CNAME paste sheet (`customers.oteny.bot`, never `<slug>.oteny.bot`).
- Step 2 → `list_site_domains` until status/SSL active.
- Step 3 → set Odoo `web.base.url` to the vanity HTTPS URL.
- Cap: 4 custom hostnames per site. Charge 0.
