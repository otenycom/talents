# Task C — capture a prospect

Trigger: a message in a Telegram group whose **title ends in
` Leads`**. Event name = title minus that suffix.

Two passes, always. Pass 1: transcribe/read → upsert → confirm the
id (and the public URL only if `list_hosted_websites` has one).
Pass 2: `web_search` → second upsert. Never delay pass 1.

When Odoo is down, say so. Run `ensure_odoo.sh`. **Do not invent a
lead id.**

## Bot notes

1. Badge photo → `parse_document`. Voice → `transcribe_audio`. Text
   as-is.
2. Fast upsert — no web search yet:

   ```
   echo '<json>' | python3 ~/.hermes/skills/talents/crm-bot/scripts/upsert_lead.py
   ```

3. Payload: `name`, `company`, `email`, `phone`, `function`, `event`
   (required), `event_note`, `summary`, `followups`, `followup_date`,
   `transcript`, `media`. Booth correction:
   `correction: true` plus `replace: {"old": "new"}`.
4. Script returns `partner_id`, `company_id`, `lead_id`, `action`,
   and `url` only when `CRM_PUBLIC_URL` is set. You set that from
   `list_hosted_websites`. If `lead_id` is null, the capture failed.
5. Confirm in the group with the id. Add the public link only when
   a hosted site exists.
6. Then enrich with `web_search` and a second upsert.

## Dedupe (cross-staff)

Two staff posting the same person must hit one partner. Match email
first, then phone, then name+company. Do not create a second lead
for the same partner + event.

## Delete

Owner says delete. Confirm. Then:

```
python3 ~/.hermes/skills/talents/crm-bot/scripts/delete_lead.py --lead-id <id>
```

## Known event (OXP)

Odoo Experience 2026, 24–26 September 2026, stand J3.
`event_note`: `Odoo Experience, stand J3, 24–26 September 2026`.
"After the show" → `followup_date: 2026-09-28`.
