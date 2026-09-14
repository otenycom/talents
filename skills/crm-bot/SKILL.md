---
name: crm-bot
description: "Capture leads and run CRM in your Odoo"
version: 1.0.13
author: Oteny
license: Apache-2.0
metadata:
  hermes:
    tags: [crm, leads, odoo, booth, oxp, meeting, briefing]
    related_skills: [oteny-sites, oteny-services, odoo-community, postgres]
---

# CrmBot — leads first, then the rest of CRM

**Builds on:** `postgres`, then `odoo-community`, then this Talent's CRM
scripts. Load those talents. Call **their** scripts. Do not keep a second
installer.
**Do not start:** trees are not a listen on `:5432` / `:8069`. The owner
must ask.
**MCP:** none. **Cron:** none. **Talent below:** none.

This page is the hot path. One `skill_view` of `crm-bot`. Run the
named script. Confirm only an id that script printed this turn.
After a name-only upsert, ask company, email, phone, and job in
that same confirm.

Setup lives in [`references/first-run.md`](references/first-run.md). Load
that file when preflight says `ENGINE: missing`, they asked to set up /
want the CRM login, or `EVENT` is `-` on a serving box. If `ADMIN` or
`LANGUAGE` is missing, or `ADMIN_FILE` is not `owner_set`, that file loads
odoo-community `references/setup.md` first. After ready, do not load it
again. A prewarmed box's `ADMIN_FILE: bake_placeholder` is not a finished
setup — it is the mint-time secret rotation, a password the owner has
never seen.

## About this Talent

The CRM Talent helps you collect leads at trade shows. A badge photo,
a voice recording, or a short note in chat becomes a contact and a
lead in Odoo while the visitor is still at the stand.

Contact fields come from the transcript or the badge. An online search
then fills what is missing when you already have a company or a unique
role. The lead holds meeting notes, follow-up activities, and the voice
note. A photo in chat can become the contact's profile picture.

Staff can post in a group whose title ends with Leads. A DM or a voice
turn that names a person is the same capture. Two people who meet the
same visitor still get one contact. After the show you book meetings
and ask for briefings on the same Odoo. The rest of CRM stays on that
Odoo. You do not need a second Talent.

The first run installs Odoo and the CRM module when you ask, then
puts the site online. On a box that already has Odoo it only adds
the CRM module. The Odoo app menu opens CRM first, not Discuss.
The team opens the live card from that link. The files are
already on the box.

## What the owner types

| They send | You do |
| --- | --- |
| `Set up CRM.` / they asked to install | Cold: Event Name plus community setup, then install and put it online. Warm: Event Name, then the CRM module |
| `I don't have a password.` / `I want the CRM login.` | Secure password link — never a paste in chat |
| A name, badge, voice note, or a group titled `… Leads` | Capture on this page |
| `How many leads?` / `Show me the OXP leads.` | `list_leads.py` |
| `Delete lead 42.` | Confirm, then `delete_lead.py` |
| `Book a meeting with …` / `Brief me on …` | CRM work on the same Odoo (not a second Talent) |
| `Put CRM online.` | First-run already hosts after the password. A later ask → `host_website` port 8069 |

## Every message — triage first

```
python3 ~/.hermes/skills/talents/crm-bot/scripts/preflight.py
```

- They asked to set up, or `ENGINE: missing`, or `EVENT` is `-` on a
  serving box → [`first-run.md`](references/first-run.md). Stop. Do
  not capture yet.
- **ODOO: down** → ensure the stack. **Do not invent a lead id.**
- `CRM_HOME: discuss` →
  `python3 ~/.hermes/skills/talents/odoo-community/scripts/pin_crm_home.py`
  `--require-crm`. Expect `CRM_HOME_PINNED`. Then continue this same
  triage. Do not stop.
- No password / want the CRM login, and `ADMIN_FILE` is not `owner_set`
  (`bake_placeholder` counts) → load odoo-community
  `references/setup.md`; then continue
  [`first-run.md`](references/first-run.md).
- Count / list / "how many" → List below.
- A person, a badge, a voice note, a DM, or a group title that ends in
  ` Leads` → Capture below.
- Delete / meeting / briefing / publish → that task on this page.

This page is enough. Do not `skill_view` another `crm-bot` file except
`first-run.md`. Do not `read_file` or `patch` the scripts. Do not
`tool_describe` a tool this page names. Do not load `oteny-sites` only to
publish CRM.

## Capture — one pass now, enrich after

Trigger: DM, voice, or a Telegram group whose **title ends in ` Leads`**.
Event name = the profile `event_name`, or the group title minus that
suffix, or ask once.

OXP, OXB, and "Odoo Experience" are the same show: Odoo Experience 2026, 24–26 September 2026. `event_note`: `Odoo Experience,
24–26 September 2026`. "After the show" → `followup_date: 2026-09-28`.

### Bot notes — capture

1. Badge photo → `parse_document`. Voice → `transcribe_audio`. Text as-is.
   Take every field the owner already gave: name, company, email, phone,
   job, notes.
2. Fast upsert. No web search yet. Do not read the script.

   ```
   echo '<json>' | python3 ~/.hermes/skills/talents/crm-bot/scripts/upsert_lead.py
   ```

3. Payload keys (put every value you have; `event` is required):

   ```
   {
     "name": "",
     "company": "",
     "email": "",
     "phone": "",
     "function": "",
     "website": "",
     "street": "",
     "city": "",
     "zip": "",
     "country_code": "",
     "event": "",
     "event_note": "",
     "summary": "",
     "followups": [],
     "followup_date": "",
     "transcript": "",
     "media": [{"path": "", "label": "badge photo"}]
   }
   ```

   A later upsert without these keys only fills empty fields. It does not
   overwrite a name, company, email, or phone that is already on the card.

   When the owner says the card is wrong, upsert the same person and event
   again. Do not create a second lead.

   - Send `"correction": true` and the correct field values. Those values
     overwrite the lead card (name, company, job, email, phone, address).
   - If a word in the notes is wrong, also send `"replace"`: each key is
     the wrong text, each value is the right text. The script rewrites
     the notes in place. It does not add a new notes block.

   ```
   {
     "name": "Angela Schenk",
     "company": "Odoo",
     "event": "Odoo Experience 2026",
     "correction": true,
     "replace": {"Acme": "Odoo"}
   }
   ```

   Owner said "not Acme, Odoo" → that payload. Owner said "add her email"
   and the card had none → normal upsert, no `correction`.
4. The script prints `partner_id`, `company_id`, `lead_id`, `action`, and
   `url` only when `CRM_PUBLIC_URL` is set. You set that from
   `list_hosted_websites`. If `lead_id` is null, the capture failed. Say
   the error. Do not invent an id. Do not confirm a lead you did not
   upsert this turn.
5. Confirm in the same chat with the id. Add the public link only when a
   hosted site exists: `{public_url}/odoo/crm/{lead_id}`.
6. In that same confirm, list what the card still lacks (company, email,
   phone, job). Ask for those. Do not wait for a badge if the owner is
   talking.
7. Then enrich. `web_search` only when you have a company or a unique
   role. Query = name + company + event. Never search a bare personal
   name. Second upsert with the new fields only.

### What the Odoo card holds

Odoo 19 stores this as `crm.lead`. The form the owner opens is usually
an **opportunity** (`type` defaults to that unless Leads mode is on).
Do not search `type = 'lead'`.

The Contact field is `partner_id`. A person hangs under their company as
`parent_id`, so the form shows "Company, Person". `partner_name` and
`function` on the lead are not the Contact line.

Fill these when you have them:

| Owner said | JSON key | Odoo field |
| --- | --- | --- |
| Person | `name` | `contact_name` + partner |
| Company | `company` | company partner + `partner_name` |
| Job | `function` | `function` |
| Email | `email` | `email_from` |
| Phone | `phone` | `phone` |
| Notes | `summary` / `transcript` | `description` |
| Event | `event` | `source_id` + tag |
| Follow-up | `followups` + `followup_date` | Call activity |

A name-only card is an unfinished capture, not a done lead.

### Dedupe (cross-staff)

Two staff posting the same person must hit one partner. Match email
first, then phone, then name+company. Do not create a second lead for
the same partner + event.

## List / count

```
python3 ~/.hermes/skills/talents/crm-bot/scripts/list_leads.py
python3 ~/.hermes/skills/talents/crm-bot/scripts/list_leads.py --event "Odoo Experience 2026"
python3 ~/.hermes/skills/talents/crm-bot/scripts/list_leads.py --name "Angela"
```

Read `count` and the rows. Quote those numbers. Do not open
`odoo_rpc.py`. Do not write ad-hoc JSON-2.

## Delete

Owner says delete. Confirm. Then:

```
python3 ~/.hermes/skills/talents/crm-bot/scripts/delete_lead.py --lead-id <id>
```

## Meeting / briefing

Same Odoo. Do not bounce to "leads only". Book a meeting as a follow-up
on the lead when they name the person and a time. A briefing is a short
read of that card plus `list_leads.py` if they asked about the show.

## Bot notes — public URL

Never ship `lead-bot.oteny.bot` or `/odoo/crm/<id>` as a constant.
After upsert, call `list_hosted_websites`. If a site is
`edge_reachable`, give `{public_url}/odoo/crm/{lead_id}`. If
nothing is hosted or the public name is not live yet, give the
local `lead_id` only and say the public link appears after the
site is live.

First-run hosts after the password on a cold box, and after Event
Name on a warm box if nothing is hosted. A later `Put CRM online`
→ `host_website` with port `8069`, `site_slug` from `SITE_NAME`
when preflight shows one, and `ensure_cmd`

`sh ~/.hermes/skills/talents/odoo-community/scripts/ensure_odoo.sh`

On `slug_taken`, follow odoo-community `references/setup.md`
"Bot notes — site name taken". After a successful host, follow
that file "Bot notes — public URL is live" before you give the
URL. They already asked. Do not ask again. Do not load
`oteny-sites` for that. Confirm before `unhost_website`.

## Safety boundary

- Never post a password or API key.
- Never ask the owner to type a password, API key, or other secret
  in chat. Offer the secure intake link in the same turn.
- Confirm before delete and before take-down.
- First-run install and first-run publish do not ask again after
  the password is in.
- `psql` and `odoo shell` are banned except the one mint inside
  `setup_admin.py`.
- Only publish content the owner is entitled to publish.
- Never invent a CRM id when Odoo is down.
- Never confirm a lead, a count, or a delete that a script did not
  print this turn.

## Never

- Do not wait for `web_search` before the first upsert.
- Do not search a bare personal name.
- Do not `read_file` or `patch` CrmBot scripts. If a script fails, show
  the error and stop.
- Do not `tool_describe` tools this page already names.
- Do not take the box login, `USER.md`, or the default `admin` login
  as the admin email. A sibling `.odoo-admin` `login=` with `@` is
  the existing owner email. Use it on a warm box. Do not ask again.
- Never say "slug" to the owner — say "the name in your public web
  address."
- Never retry `host_website` under the exact name that just came back
  `slug_taken`. The platform reads a repeat as a collision against
  your own reservation, not as "this one is already yours."
- Never give a public URL while `host_website` still says
  `provisioning`, or while `wait_for_public_dns.py` printed
  `PUBLIC_URL_PENDING`, or while `edge_reachable` is not true.
- `ir.attachment` with only `res_model` / `res_id` is invisible on the
  Odoo 19 CRM form. The script posts `attachment_ids` on the chatter.
  Keep the real filename extension.
- JSON-2 `create` returns `[id]`. The scripts unwrap that. Do not send
  a list as a Many2one id.
