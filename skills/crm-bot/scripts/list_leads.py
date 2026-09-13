#!/usr/bin/env python3
"""List CRM leads. Use this for "how many" and "show me". Do not improvise JSON-2.

    python3 list_leads.py
    python3 list_leads.py --event "Odoo Experience 2026"
    python3 list_leads.py --name "Angela"

Prints JSON. Exits 2 when Odoo is down. Never invents an id.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from odoo_rpc import OdooRPC  # noqa: E402


def _event_name(source_id) -> str:
    if isinstance(source_id, (list, tuple)) and len(source_id) > 1:
        return str(source_id[1] or "")
    return str(source_id or "")


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
                ],
                "limit": ns.limit,
                "order": "id desc",
            },
        )
    except Exception as exc:
        print(json.dumps({"error": str(exc), "count": 0, "leads": []}))
        return 2
    leads = []
    for row in rows or []:
        leads.append({
            "lead_id": row.get("id"),
            "name": row.get("name") or "",
            "contact": row.get("contact_name") or "",
            "company": row.get("partner_name") or "",
            "email": row.get("email_from") or "",
            "phone": row.get("phone") or "",
            "function": row.get("function") or "",
            "event": _event_name(row.get("source_id")),
        })
    print(json.dumps({"count": len(leads), "leads": leads}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
