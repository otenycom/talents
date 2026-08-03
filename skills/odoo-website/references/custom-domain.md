# Custom domain for a WebsiteBot site

Use after the site is live on `https://<slug>.oteny.bot` (`list_hosted_websites` →
`status: active`). Tools: `attach_site_domains`, `list_site_domains`,
`detach_site_domain` (charge 0).

## Preferred: Cloudflare DNS (or ALIAS)

Most WebsiteBot owners: put the domain on **Cloudflare DNS** (free plan OK), or any
DNS that supports apex ALIAS/ANAME.

1. Confirm with the owner before attaching.
2. `attach_site_domains(site_slug=<slug>, domain="example.com")` — expands to
   `example.com` + `www.example.com`.
3. Owner creates **CNAME** (proxied/flattened) for **both** `@` and `www` →
   **`customers.oteny.bot`**.
4. **Never** CNAME to `<slug>.oteny.bot` — if they are also on Cloudflare that is
   Error **1014**.
5. Poll `list_site_domains` until status/SSL active (~15–30 min after DNS).
6. Set Odoo `web.base.url` to `https://example.com` (canonical apex).

True apex URL in the address bar.

## Reference: AWS Route53

Route53 cannot CNAME the zone apex to `customers.oteny.bot`. Use this pattern:

1. `attach_site_domains(site_slug=<slug>, hostnames=["www.example.com"])`.
2. Route53: `www` **CNAME** → `customers.oteny.bot`.
3. Route53: apex **Alias** → S3 website endpoint (or CloudFront) configured to
   **301** all requests to `https://www.example.com`.
4. Set `web.base.url` to `https://www.example.com`.

Visitors typing the root land on `www`. Offer the preferred Cloudflare path when
they want a bare-apex URL.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Error 1014 | They CNAMEd to `<slug>.oteny.bot` — change target to `customers.oteny.bot` |
| Stuck validating | DNS not pointing yet, or wrong target; wait for SSL `active` |
| Cap refused | Max 4 custom hostnames per site — detach one first |
