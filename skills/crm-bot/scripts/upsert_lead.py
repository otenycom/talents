#!/usr/bin/env python3
"""Lead Bot capture — upsert helpers for the trade-show lead flow.

Called by the Hermes agent (via `python3 .../scripts/upsert_lead.py`) with a
small JSON payload on stdin. Keeps all Odoo model-shape knowledge in one
place so the SKILL.md checklist can stay short.

Design (per lead-bot SKILL.md "Task C — capture a prospect"):
- One res.partner per prospect (matched by email, else name+company, else
  name). The prospect's company is a real company partner (is_company,
  carrying the address found by enrichment) and the person hangs under it
  as `parent_id`, so the opportunity form shows "Company, Person" in the
  Contact field. (`partner_name` / `function` on the lead are not shown on
  an opportunity form, so they cannot carry it.) Existing records only get
  their gaps filled, never overwritten — unless `correction` is true,
  in which case provided fields overwrite and `replace` rewrites the
  notes/transcript in place.
- One crm.lead per prospect per event. If an open lead already exists for
  that partner (this event), UPDATE it (append the new sections, attach
  media, fill the gaps). Otherwise CREATE a new lead.
- `source_id` = the event (utm.source, created on first use); `medium_id` =
  "Trade show"; a crm.tag named after the event so the show is visible on
  the form. The lead is owned by the booth owner (`LEADBOT_OWNER_LOGIN`,
  default `admin`), never by the automation user.
- The agreed follow-up is BOOKED: one Call activity on the lead, due on
  `followup_date` (default: three days out), assigned to the owner, and the
  follow-up lines are listed in the notes as discrete lines.
- The notes (`description`) are structured: Captured at / Summary / Oteny
  follow-up / Lookup (with sources) / Transcript, then the legacy
  `transcript_html` and the enrichment note (`enrichment_html`) as-is.
- Raw badge photo + interview media are attached to the lead's chatter,
  never deleted (kept indefinitely per owner decision).
"""
from __future__ import annotations

import html
import json
import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from odoo_rpc import OdooRPC  # noqa: E402

OWNER_LOGIN = os.environ.get("LEADBOT_OWNER_LOGIN", "admin")
MEDIUM_NAME = "Trade show"
FOLLOWUP_DEFAULT_DAYS = 3
ADDRESS_FIELDS = ("website", "phone", "street", "city", "zip", "country_id")

def _public_lead_url(lead_id: int) -> str | None:
    """Never invent a host. The bot fills this from list_hosted_websites."""
    base = (os.environ.get("CRM_PUBLIC_URL") or "").rstrip("/")
    if not base:
        return None
    return f"{base}/odoo/crm/{lead_id}"




def esc(text) -> str:
    return html.escape(str(text or ""), quote=True)


def _paras(text: str) -> str:
    """One short <p> per sentence/line so Odoo HTML notes wrap on mobile.

    A single long <p> in the html field does not wrap (flex min-width +
    overflow-wrap unset on contenteditable) — lines clip on both sides.
    """
    raw = str(text or "").strip()
    if not raw:
        return ""
    chunks: list[str] = []
    for line in re.split(r"\n+", raw):
        line = line.strip()
        if not line:
            continue
        pieces = re.split(r"(?<=[.!?])\s+", line) if len(line) > 90 else [line]
        buf = ""
        for piece in pieces:
            if buf and len(buf) + 1 + len(piece) > 90:
                chunks.append(buf)
                buf = piece
            else:
                buf = f"{buf} {piece}".strip() if buf else piece
        if buf:
            chunks.append(buf)
    return "".join(f"<p>{esc(c)}</p>" for c in chunks)


def _filled(vals: dict) -> dict:
    return {k: v for k, v in vals.items() if v not in (None, "", False)}


def apply_replacements(text: str, mapping: dict | None) -> str:
    """Rewrite notes/transcript in place for a booth correction."""
    if not text or not mapping:
        return text or ""
    for old, new in mapping.items():
        if not old:
            continue
        text = re.sub(re.escape(str(old)), str(new), text, flags=re.IGNORECASE)
    return text


def _country_id(rpc: OdooRPC, code: str | None):
    if not code:
        return False
    ids = rpc.call("res.country", "search", [[("code", "=", code.upper())]], {"limit": 1})
    return ids[0] if ids else False


def build_description(payload: dict, *, created: bool) -> str:
    """The structured notes. Only the sections present in the payload are
    rendered, so an update appends just what is new."""
    parts: list[str] = []
    event = payload.get("event") or "Unspecified event"
    if created:
        note = payload.get("event_note")
        where = f"{esc(event)} ({esc(note)})" if note else esc(event)
        parts.append(f"<p><b>Captured at</b> {where}.</p>")
    if payload.get("summary"):
        parts.append("<p><b>Summary</b></p>" + _paras(payload["summary"]))
    followups = [f for f in (payload.get("followups") or []) if f]
    if followups:
        items = "".join(f"<li>{esc(f)}</li>" for f in followups)
        parts.append(f"<p><b>Oteny follow-up</b></p><ul>{items}</ul>")
    lookup = payload.get("lookup") or []
    if isinstance(lookup, str):
        lookup = [lookup]
    if lookup:
        items = []
        for entry in lookup:
            if isinstance(entry, dict):
                note = esc(entry.get("note"))
                src = entry.get("source")
                if src:
                    note += f' — <a href="{esc(src)}">{esc(src)}</a>'
                items.append(f"<li>{note}</li>")
            else:
                items.append(f"<li>{esc(entry)}</li>")
        parts.append("<p><b>Lookup</b></p><ul>" + "".join(items) + "</ul>")
    if payload.get("transcript"):
        parts.append("<p><b>Transcript</b></p>" + _paras(payload["transcript"]))
    if payload.get("transcript_html"):
        parts.append(payload["transcript_html"])
    if payload.get("enrichment_html"):
        parts.append(payload["enrichment_html"])
    if payload.get("unconfirmed"):
        parts.append(
            "<p><em>&#9888; Enrichment unconfirmed — verify company/email "
            "before follow-up.</em></p>"
        )
    return "".join(parts)


def get_or_create_source(rpc: OdooRPC, event_name: str) -> int:
    return rpc.get_or_create_by_name("utm.source", event_name)


def ensure_partner(rpc: OdooRPC, payload: dict, addr: dict) -> tuple[int, int | None]:
    """The prospect partner, with its company partner linked as parent.

    Returns (partner_id, company_id). The company carries the address when
    there is one; a person without a company carries it instead. Existing
    partners get their gaps filled (parent company, job title, email,
    phone, address) and are never overwritten."""
    name = payload.get("name")
    company = payload.get("company")
    email = payload.get("email")
    company_id = None
    if company:
        company_id = rpc.ensure_company(company)
        current = rpc.read_partner(company_id, list(ADDRESS_FIELDS))
        gaps = {k: v for k, v in _filled(addr).items() if not current.get(k)}
        if gaps:
            rpc.write_partner(company_id, gaps)

    partner_id = rpc.find_partner(name, company, email, phone=payload.get("phone"))
    if not partner_id:
        if name:
            vals = {"name": name, "is_company": False}
            if company_id:
                vals["parent_id"] = company_id
            else:
                vals.update(_filled(addr))
            if payload.get("function"):
                vals["function"] = payload["function"]
            if email:
                vals["email"] = email
            if payload.get("phone"):
                vals["phone"] = payload["phone"]
            partner_id = rpc.create_partner(vals)
        elif company_id:
            partner_id = company_id
        else:
            partner_id = rpc.create_partner({"name": "Unknown prospect (booth capture)"})
        return partner_id, company_id

    current = rpc.read_partner(
        partner_id, ["is_company", "parent_id", "function", "email", *ADDRESS_FIELDS]
    )
    gaps = {}
    correction = bool(payload.get("correction"))
    if company_id and not current["is_company"] and company_id != partner_id:
        parent = current["parent_id"][0] if current.get("parent_id") else None
        if correction or not parent:
            gaps["parent_id"] = company_id
    if payload.get("function") and not current["function"]:
        gaps["function"] = payload["function"]
    if email and not current["email"]:
        gaps["email"] = email
    for k, v in _filled(addr).items():
        if not current.get(k) and (k == "phone" or not company_id):
            gaps[k] = v
    if gaps:
        rpc.write_partner(partner_id, gaps)
    return partner_id, company_id


def book_followup(rpc: OdooRPC, lead_id: int, payload: dict, owner_id: int | None):
    """One Call activity for the agreed follow-up, unless one is already open."""
    followups = [f for f in (payload.get("followups") or []) if f]
    if not followups:
        return None
    summary = followups[0] if len(followups) == 1 else f"{len(followups)} follow-ups: " + "; ".join(followups)
    for act in rpc.open_activities(lead_id):
        if (act.get("summary") or "") == summary[:200]:
            return act["id"]
    due = payload.get("followup_date") or (date.today() + timedelta(days=FOLLOWUP_DEFAULT_DAYS)).isoformat()
    note = "<ul>" + "".join(f"<li>{esc(f)}</li>" for f in followups) + "</ul>"
    return rpc.schedule_activity(lead_id, summary, due, owner_id or rpc.uid, note_html=note)


def upsert_prospect(rpc: OdooRPC, payload: dict) -> dict:
    """payload keys (all optional except at least one of name/company/email):
    name, company, email, phone, function, website, street, city, zip,
    country_code, event (required in practice), event_note, summary,
    followups (list), followup_date (ISO date), lookup (list of str or
    {"note","source"}), transcript (raw text), transcript_html (legacy,
    already HTML), enrichment_html (already HTML), unconfirmed (bool),
    media: list of {"path": "...", "label": "badge photo"|"interview audio"|...}
    """
    name = payload.get("name")
    company = payload.get("company")
    email = payload.get("email")
    event = payload.get("event") or "Unspecified event"
    addr = {
        "website": payload.get("website"),
        "phone": payload.get("phone"),
        "street": payload.get("street"),
        "city": payload.get("city"),
        "zip": payload.get("zip"),
        "country_id": _country_id(rpc, payload.get("country_code")),
    }

    partner_id, company_id = ensure_partner(rpc, payload, addr)
    owner_id = rpc.find_user(OWNER_LOGIN)
    source_id = get_or_create_source(rpc, event)
    medium_id = rpc.get_or_create_by_name("utm.medium", MEDIUM_NAME)
    tag_id = rpc.get_or_create_by_name("crm.tag", event)

    lead_fields = _filled({
        "contact_name": name,
        "partner_name": company,
        "function": payload.get("function"),
        "email_from": email,
        **addr,
    })

    lead_id = rpc.find_open_lead_for_partner(partner_id, event=event)
    correction = bool(payload.get("correction"))
    replacements = payload.get("replace") or {}
    if lead_id:
        current = rpc.read_lead(
            lead_id, ["description", "user_id", "medium_id", "tag_ids", *lead_fields.keys()],
        )
        if correction:
            vals = dict(lead_fields)
        else:
            vals = {k: v for k, v in lead_fields.items() if not current.get(k)}
        desc = current.get("description") or ""
        if replacements:
            desc = apply_replacements(desc, replacements)
        extra = build_description(payload, created=False)
        if replacements:
            vals["description"] = desc
        elif extra:
            vals["description"] = desc + extra
        current_user = current["user_id"][0] if current.get("user_id") else None
        if owner_id and (not current_user or current_user == rpc.uid):
            vals["user_id"] = owner_id
        if not current.get("medium_id"):
            vals["medium_id"] = medium_id
        if tag_id not in (current.get("tag_ids") or []):
            vals["tag_ids"] = [[4, tag_id]]
        if vals:
            rpc.write_lead(lead_id, vals)
        action = "updated"
    else:
        lead_vals = {
            "name": f"{name or company or 'Prospect'} — {event}",
            "partner_id": partner_id,
            "description": build_description(payload, created=True),
            "source_id": source_id,
            "medium_id": medium_id,
            "tag_ids": [[4, tag_id]],
            **lead_fields,
        }
        if owner_id:
            lead_vals["user_id"] = owner_id
        lead_id = rpc.create_lead(lead_vals)
        action = "created"

    for m in payload.get("media", []):
        rpc.attach_file(lead_id, m["path"], name=m.get("label"))

    activity_id = book_followup(rpc, lead_id, payload, owner_id)

    note = f"Booth capture ({action}) for event '{esc(event)}'."
    if activity_id:
        act = next((a for a in rpc.open_activities(lead_id) if a["id"] == activity_id), None)
        if act:
            note += f" Follow-up booked for {esc(act['date_deadline'])}: {esc(act['summary'])}."
    rpc.post_note(lead_id, note)

    return {
        "partner_id": partner_id,
        "company_id": company_id,
        "lead_id": lead_id,
        "activity_id": activity_id,
        "action": action,
        "url": _public_lead_url(lead_id),
    }


if __name__ == "__main__":
    raw = sys.stdin.read()
    payload = json.loads(raw)
    try:
        rpc = OdooRPC()
        result = upsert_prospect(rpc, payload)
    except Exception as exc:
        print(json.dumps({"error": str(exc), "lead_id": None, "url": None}))
        raise SystemExit(2)
    print(json.dumps(result))
