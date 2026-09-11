---
name: crm-bot
description: "Capture leads and run CRM in your Odoo"
version: 1.0.6
author: Oteny
license: Apache-2.0
metadata:
  hermes:
    tags: [crm, leads, odoo, booth, oxp, meeting, briefing]
    related_skills: [oteny-sites, oteny-services, odoo-community, postgres]
---

# CrmBot — leads first, then the rest of CRM

**Builds on:** `postgres`, then `odoo-community`, then this Talent's CRM scripts. Load those talents. Call **their** scripts. Do not keep a second installer.
**Do not start:** trees are not a listen on `:5432` / `:8069`. The owner must ask.
**MCP:** none. **Cron:** none. **Talent below:** none.

**Pit of failure.** The first page named CRM work and hid the stack. The model waited for a human to name `postgres`. After ready it named the email and hid the password door. The owner had no password. Chat then asked them to type one.
**Pit of success.** This page names the stack and the order. Ask the owner for event, admin email, and language. After first-run say Postgres and Odoo are up, CRM is ready, only when they said yes, `write_profile.py` printed `PROFILE_WRITTEN`, and preflight shows serving. Do not take the box login as the admin email. The ready sentence names the URL, the login email, and the secure password link in the same turn. "I don't have a password" mints or reuses that link. Chat never collects the secret.

Detail:
[`references/first-run.md`](references/first-run.md),
[`references/capture.md`](references/capture.md),
[`references/lessons.md`](references/lessons.md).

## About this Talent

The CRM Talent helps you collect leads at trade shows. A badge photo,
a voice recording, or a short note in chat becomes a contact and a
lead in Odoo while the visitor is still at the stand.

Contact fields come from the transcript or the badge. An online search
then fills what is missing. The lead holds meeting notes, follow-up
activities, and the voice note. A photo in chat can become the
contact's profile picture.

Staff can post in a group whose title ends with Leads. Two people who
meet the same visitor still get one contact. After the show you book
meetings and ask for briefings on the same Odoo. The rest of CRM stays
on that Odoo. You do not need a second Talent.

You can put CRM online so the team opens the live card from a link.
The files are already on the box. The first run installs Odoo and the
CRM module when you ask.

## What the owner types

| They send | You do |
| --- | --- |
| `Set up CRM.` / they asked to install | first-run if the engine is missing |
| `I don't have a password.` / `I want the CRM login.` | Secure password link — never a paste in chat |
| A message in a group titled `… Leads` | Task C — capture |
| `Delete lead 42.` | Confirm, then `delete_lead.py` |
| `Book a meeting with …` / `Brief me on …` | CRM work on the same Odoo (not a second Talent) |
| `Put CRM online.` | Confirm, then `host_website` port 8069 |

## Every message — triage first

```
python3 ~/.hermes/skills/talents/crm-bot/scripts/preflight.py
```

- **ENGINE: missing** and they asked to set up → [`first-run.md`](references/first-run.md).
- **ODOO: down** → ensure the stack. **Do not invent a lead id.**
- No password / want the CRM login → [`first-run.md`](references/first-run.md)
  password checklist.
- Group title ends in ` Leads` → [`capture.md`](references/capture.md).
- Delete / meeting / briefing → that task. Do not bounce to "leads only".

## Bot notes — public URL

Never ship `lead-bot.oteny.bot` or `/odoo/crm/<id>` as a constant.
After upsert, call `list_hosted_websites`. If a site is active, give
`{public_url}/odoo/crm/{lead_id}`. If nothing is hosted, give the
local `lead_id` only and say the public link appears after they ask
to put CRM online.

## Safety boundary

- Never post a password or API key.
- Never ask the owner to type a password, API key, or other secret
  in chat. Offer the secure intake link in the same turn.
- Confirm before delete and before first publish.
- `psql` and `odoo shell` are banned except the one mint inside
  `setup_admin.py`.
- Only publish content the owner is entitled to publish.

## Common pitfalls

See [`lessons.md`](references/lessons.md) — lessons and pitfalls
from the PeekMSX pilot. The two that still bite:

- Waiting for web search before the first upsert.
- Confirming "attached" from a payload count (Odoo 19 chatter needs
  `message_post(..., attachment_ids=)`).
