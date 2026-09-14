---
name: crm-bot
description: "Capture leads and run CRM in your Odoo"
version: 1.0.14
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
note. A photo in chat becomes the contact's profile picture.

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
| A name, badge, voice note, or a group titled `… Leads` | Capture below |
| `How many leads?` / `Show me the OXP leads.` / `What is on Kajal's card?` / `Does she have a photo?` | `list_leads.py` |
| `Delete lead 42.` | Confirm, then `delete_lead.py` |
| `Book a meeting with …` / `Brief me on …` | CRM work on the same Odoo (not a second Talent) |
| `Put CRM online.` | First-run already hosts after the password. A later ask → `host_website` port 8069 |
| A model / a record / a view / SQL this table does not name | odoo-community `references/local-odoo-client.md` |

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
- Count / list / "how many" / recall what is on a card → `list_leads.py`.
- A person, a badge, a voice note, a DM, or a group title that ends in
  ` Leads` → Capture below.
- Delete / meeting / briefing / publish → that task on this page.
- A model / a record / a view / SQL the table above does not name →
  one `skill_view` of odoo-community
  `references/local-odoo-client.md`, then that page's named script.
  Do not load it on a booth capture.

A failed script: show its error, then stop.

## Capture — one pass now, enrich after

Trigger: DM, voice, or a Telegram group whose **title ends in ` Leads`**.
Event name = the profile `event_name`, or the group title minus that
suffix, or ask once.

OXP, OXB, and "Odoo Experience" are the same show: Odoo Experience 2026, 24–26 September 2026. `event_note`: `Odoo Experience,
24–26 September 2026`. "After the show" → `followup_date: 2026-09-28`.

### Scenario → script or tool

| This message | Do this |
| --- | --- |
| Quoted voice text already in the message | Put it in `transcript`. If the message also has `saved at:` / `[voice file: …]`, put that path in `media` too |
| Audio file path only, no transcript yet | `transcribe_audio` on that path, then the same upsert |
| Person photo path (`[Image attached at: …]`) | That path in `media` with label `photo`. The script sets the contact picture |
| Badge or business-card photo | `parse_document` on that path, then upsert with the fields plus the path in `media` |
| New person, or more facts for a person already on a card | `upsert_lead.py` this turn, with every field and every this-message path you have |
| Owner said the card is wrong | Same `upsert_lead.py` with `correction: true` (and `replace` for a wrong word in the notes) — never a second lead |
| Have a full person name and/or a company, not yet enriched | `web_search` for contact details and background, then a second `upsert_lead.py` with the new fields |
| Public link on the confirm | `url` from this upsert when the profile already holds the live host; else `list_hosted_websites`, then write that host into the profile |
| Delete or take-down | Confirm, then `delete_lead.py` / `unhost_website` |
| Owner asked to start Postgres or Odoo | The first-run script list — trees on disk are not a listen |

Live voice uses the same table: a new person is upsert; a question about
a card is `list_leads.py`; then speak.

### Capture checklist

1. `preflight.py` if you have not run it this turn.
2. Collect name, company, email, phone, job, notes, and every file path
   from **this** message.
3. `echo '<json>' | upsert_lead.py` once, with those fields and `media`.
4. Confirm only the `lead_id` (and `url` if the script printed one). List
   the empty fields. Ask for those.
5. If you now have a full person name and/or a company, enrich:
   `web_search`, then a second upsert with the new fields and a short
   `lookup` note. A given name alone waits until the owner adds a family
   name or a company.

### Payload keys

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

`event` is required. A later upsert without these keys only fills empty
fields. It does not overwrite a name, company, email, or phone that is
already on the card.

**Correction:** send `"correction": true` and the correct field values —
those overwrite the lead card (name, company, job, email, phone,
address). Add `"replace"` when a word in the notes is wrong: each key is
the wrong text, each value is the right text. The script rewrites the
notes in place; it does not add a new notes block.

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

The script prints `partner_id`, `company_id`, `lead_id`, `action`, and
`url` only when `CRM_PUBLIC_URL` is set (you set that from
`list_hosted_websites`). If `lead_id` is null, the capture failed — say
the error. Confirm only what the script printed this turn.

### What the Odoo card holds

Odoo 19 stores this as `crm.lead`. The form the owner opens is usually
an **opportunity** (`type` defaults to that unless Leads mode is on).

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

Each row carries a short note snippet plus `has_photo`, `has_audio`, and
`avatar` — read those to answer "what is on the card" or "does she have
a photo" without a second tool. Quote `count` and the rows this script
printed.

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

A `slug_taken` response is not a retry signal for the exact same name
— the platform reads a repeat as a collision against your own
reservation. Follow odoo-community `references/setup.md`
"Bot notes — site name taken" instead (two silent random-suffix
retries, then ask). Call the site's public web address by that name to
the owner — never "slug". After a successful host, follow that file
"Bot notes — public URL is live" before you give the URL; give it only
once `edge_reachable` is true, never while status is still
`provisioning` or `wait_for_public_dns.py` printed `PUBLIC_URL_PENDING`.
They already asked, so do not ask again, and do not load `oteny-sites`
for this. Confirm before `unhost_website`.

## Safety boundary

- Password or API key → the secure intake link (`connect_account` /
  community setup). The owner never types a secret in chat.
- Confirm a lead, a count, a delete, or a URL by quoting the `lead_id` /
  `count` / `url` a script or `list_hosted_websites` printed **this
  turn**. When Odoo is down, `upsert_lead.py` already prints
  `lead_id: null` — say that error.
- Confirm before delete and before take-down.
- First-run install and first-run publish do not ask again after the
  password is in.
- `psql` and `odoo shell` are banned except the one mint inside
  `setup_admin.py`.
- Only publish content the owner is entitled to publish.
- The default `admin` login, the box login, and `USER.md` are never the
  owner email. A sibling `.odoo-admin` `login=` with `@` is the existing
  owner email — use it on a warm box, and do not ask again.
