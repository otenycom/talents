#!/usr/bin/env python3
"""List CRM leads. Use this for "how many" and "show me". Do not improvise JSON-2.

    python3 list_leads.py
    python3 list_leads.py --event "Odoo Experience 2026"
    python3 list_leads.py --name "Angela"

Prints JSON. Exits 2 when Odoo is down. Never invents an id.

Each row carries a short note snippet plus ``has_photo`` / ``has_audio`` /
``avatar`` — enough for "how does Kajal look?" or "what is on the card?" to
answer from this one script, without a second round-trip (``session_search``
+ ``vision_analyze``) just to recall what a prior turn already attached.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from odoo_rpc import OdooRPC  # noqa: E402

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_NOTE_CAP = 200


def _event_name(source_id) -> str:
    if isinstance(source_id, (list, tuple)) and len(source_id) > 1:
        return str(source_id[1] or "")
    return str(source_id or "")


def _note_snippet(description_html: str) -> str:
    """Plain-text preview of the lead's notes: strip HTML, collapse
    whitespace, cap length — enough to recall "what is on the card" without
    re-reading the full HTML body."""
    text = _TAG_RE.sub(" ", description_html or "")
    text = _WS_RE.sub(" ", text).strip()
    if len(text) > _NOTE_CAP:
        text = text[:_NOTE_CAP].rstrip() + "…"
    return text


def _attachment_flags(rpc: OdooRPC, lead_ids: list[int]) -> dict[int, dict[str, bool]]:
    """One batched ``ir.attachment`` read for every lead on this page —
    ``has_photo`` / ``has_audio`` per ``res_id``, from the mimetype the
    upsert already stored (see ``local_odoo_rpc.attach_file``)."""
    flags: dict[int, dict[str, bool]] = {
        lead_id: {"has_photo": False, "has_audio": False} for lead_id in lead_ids
    }
    if not lead_ids:
        return flags
    rows = rpc.call(
        "ir.attachment",
        "search_read",
        kwargs={
            "domain": [("res_model", "=", "crm.lead"), ("res_id", "in", lead_ids)],
            "fields": ["res_id", "mimetype"],
        },
    )
    for row in rows or []:
        res_id = row.get("res_id")
        entry = flags.get(res_id)
        if entry is None:
            continue
        mimetype = str(row.get("mimetype") or "")
        if mimetype.startswith("image/"):
            entry["has_photo"] = True
        elif mimetype.startswith("audio/"):
            entry["has_audio"] = True
    return flags


def _avatar_flags(rpc: OdooRPC, partner_ids: list[int]) -> dict[int, bool]:
    """One batched ``res.partner`` read with ``bin_size`` — a cheap presence
    check per partner, never a full base64 image download."""
    ids = sorted({pid for pid in partner_ids if pid})
    if not ids:
        return {}
    rows = rpc.call(
        "res.partner", "read", [ids],
        {"fields": ["image_1920"], "context": {"bin_size": True}},
    )
    return {row["id"]: bool(row.get("image_1920")) for row in rows or []}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--event", default="")
    ap.add_argument("--name", default="")
    ap.add_argument("--limit", type=int, default=50)
    ns = ap.parse_args(argv)
    try:
        rpc = OdooRPC()
        # Do not filter type='lead' — Odoo 19 often stores an opportunity.
        domain: list = [("active", "=", True)]
        if ns.event:
            domain.append(("source_id.name", "ilike", ns.event))
        if ns.name:
            domain.extend([
                "|",
                ("contact_name", "ilike", ns.name),
                ("name", "ilike", ns.name),
            ])
        rows = rpc.call(
            "crm.lead",
            "search_read",
            [domain],
            {
                "fields": [
                    "id",
                    "name",
                    "contact_name",
                    "partner_name",
                    "email_from",
                    "phone",
                    "function",
                    "source_id",
                    "partner_id",
                    "description",
                ],
                "limit": ns.limit,
                "order": "id desc",
            },
        )
        lead_ids = [row["id"] for row in (rows or []) if row.get("id")]
        partner_ids = [
            row["partner_id"][0] for row in (rows or []) if row.get("partner_id")
        ]
        attachment_flags = _attachment_flags(rpc, lead_ids)
        avatar_flags = _avatar_flags(rpc, partner_ids)
    except Exception as exc:
        print(json.dumps({"error": str(exc), "count": 0, "leads": []}))
        return 2
    leads = []
    for row in rows or []:
        lead_id = row.get("id")
        partner_id = row["partner_id"][0] if row.get("partner_id") else None
        flags = attachment_flags.get(lead_id, {"has_photo": False, "has_audio": False})
        leads.append({
            "lead_id": lead_id,
            "name": row.get("name") or "",
            "contact": row.get("contact_name") or "",
            "company": row.get("partner_name") or "",
            "email": row.get("email_from") or "",
            "phone": row.get("phone") or "",
            "function": row.get("function") or "",
            "event": _event_name(row.get("source_id")),
            "note": _note_snippet(row.get("description") or ""),
            "has_photo": flags["has_photo"],
            "has_audio": flags["has_audio"],
            "avatar": bool(partner_id and avatar_flags.get(partner_id)),
        })
    print(json.dumps({"count": len(leads), "leads": leads}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
