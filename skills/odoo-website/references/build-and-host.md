# Build, host, and care — what to type in chat

After INSTALL (`READY: yes`), or for Online/remote after credentials land. Owners describe
the site in chat; **you** edit and host. They never run scripts.

---

## What the owner types

### Build / change content

```
Make the homepage title "Example Cafe" and say we open 9–5 with a short menu.
```

```
Add a page about our story.
```

```
Enable a small shop.   (only if they ask)
```

### Put it online (local Max)

```
Put my site online.
```

You confirm first (`Shall I put it online at https://<slug>.oteny.bot?`). They send:

```
Yes, go ahead.
```

### Check status / get the link

```
Is my site up?
```

```
What's the public link?
```

### Own domain

See [`custom-domain.md`](custom-domain.md) — e.g.:

```
Attach my domain example.com to site <slug> (include www).
My DNS is on Cloudflare (free is fine).
```

### Take it down

```
Take the site down.
```

(Confirm before `unhost_website`.)

### Back-office login

```
I want the back-office login for my site.
```

You give public URL + `/web/login` + login **email** only; password via secure connect
link — never in chat.

---

## Bot notes — pick the locked path

Read `build_backend` + `odoo_locus` from `~/.hermes/data/odoo-website/profile.yaml`.

| `build_backend` | When | Edit with |
| --- | --- | --- |
| **`module`** (default on local Max) | Local Odoo on this Max VM | `site_module.py` |
| **`json2`** | Odoo Online / remote, or local opt-in | `site_rpc.py` |

- **Online/remote:** custom module **impossible** — always `json2`.
- **Not on Max but wants module:** tell them to send `/oteny_subscribe upgrade max`.
- Never invent a third stack. Never `python -m http.server` / `oteny-drop`.

| Do | Don't |
| --- | --- |
| Follow `build_backend` from the profile | Debate module vs RPC in chat |
| `ensure_site.sh` before local edits | Browser drag-and-drop as the primary editor |
| `setup_admin.py` for admin/password / API-key | `odoo shell` / SQL password resets |
| Confirm before first publish | Fall back to drop.oteny.bot |
| Keep the app on the hosted `local_port` (8069) unless Oteny’s edge recipe says otherwise | `apt install` nginx, edit `/etc/nginx`, or move `http_port` freestyle to “fix” Cloudflare 502s — edge maintenance during restarts is a platform/recipe concern, not a one-off shell fix |

### Admin credentials (bot-only file, local)

`~/.hermes/data/odoo-website/.odoo-admin` (0600) holds email + password + JSON-2
`api_key`. **Never post secrets in chat.** `site_rpc.py` loads `api_key` itself.

### BUILD — module path

1. `sh ~/.hermes/skills/talents/odoo-website/scripts/ensure_site.sh`
2. `site_module.py init --slug <slug> --name "<site_name>"` (idempotent; creates git)
3. `site_module.py set-homepage --title "…" --body-html '…'`
4. Controllers / `static/src/scss/site.scss` OK → then `site_module.py upgrade`
5. Git is bot-owned by default. Ask once: customer-facing remote? If yes → credential
   intake (never Telegram) → `site_module.py git-remote --url <url>`
6. Append facts to `~/.hermes/data/odoo-website/memory.md`

**UI note:** Website Builder edits may be **overwritten** by module upgrades — prefer
chat/module as source of truth in module mode.

### BUILD — JSON-2 path

1. Local: `ensure_site.sh` then `site_rpc.py ping`. Online/remote: base URL + API key
   from secure intake (External JSON-2 only — never XML-RPC).
2. `site_rpc.py set-homepage --title "…" --body-html "…"`
3. Builder UI is fine for the owner after handoff in JSON-2 mode.

Shop (`website_sale`) / booking (`website_appointment`): only if asked — install via RPC
on local, or Apps on Online.

### HOST (local Max)

1. Confirm public URL. Wait for yes.
2. `host_website(local_port=8069, site_slug="<slug>",
   ensure_cmd="sh /home/hermes/.hermes/skills/talents/odoo-website/scripts/ensure_site.sh")`
3. Poll `list_hosted_websites` until `status: active` + `health_state: ok` (~1 min).
4. `site_rpc.py set-base-url --url https://<slug>.oteny.bot`
5. Give the public URL, then handoff below.
6. Custom domain → [`custom-domain.md`](custom-domain.md).

### Owner handoff (after first host, local)

1. Facts (no secrets): public URL, `/web/login`, login **email** = `owner_email`.
2. Password via private credential form / connect link — apply with
   `setup_admin.py --from-env` / `--password-file`.
3. Module mode: Website Builder edits may be overwritten on module upgrade.

### Care loop

- Module → edit files → `site_module.py upgrade` / `set-homepage`.
- JSON-2 → `site_rpc.py`.
- Down → `list_hosted_websites` + `ensure_site.sh`.
- Take down → `unhost_website(site_slug="<slug>")` after confirm.

### Limits (honest)

- First local install on Max: usually **~3–5 minutes**. Later starts are seconds.
- Module backend needs **Max**. Online/remote: any plan, JSON-2 only.
- The site is only live while the bot is **active**.
