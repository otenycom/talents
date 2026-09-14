#!/usr/bin/env python3
"""Views on one model: ir.ui.view + xml_id from ir.model.data."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from local_odoo_rpc import OdooRPC

_ARCH_CAP = 4000


def main() -> int:
    parser = argparse.ArgumentParser(prog="list_views.py")
    parser.add_argument("--model", required=True)
    parser.add_argument("--type", dest="view_type", default="")
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--limit", type=int, default=40)
    args = parser.parse_args()
    try:
        rpc = OdooRPC()
        model = args.model.strip()
        domain = [("model", "=", model)]
        if args.view_type:
            domain.append(("type", "=", args.view_type))
        fields = ["id", "name", "type", "xml_id", "inherit_id", "priority", "key"]
        if args.full:
            fields.append("arch_db")
        rows = rpc.call(
            "ir.ui.view",
            "search_read",
            kwargs={"domain": domain, "fields": fields, "limit": args.limit, "order": "priority asc, id asc"},
        ) or []
        ids = [r["id"] for r in rows if isinstance(r, dict) and r.get("id")]
        xml_map = {}
        if ids:
            data = rpc.call(
                "ir.model.data",
                "search_read",
                kwargs={
                    "domain": [("model", "=", "ir.ui.view"), ("res_id", "in", ids)],
                    "fields": ["module", "name", "res_id"],
                    "limit": 200,
                },
            ) or []
            for rec in data:
                xml_map[rec["res_id"]] = f"{rec.get('module')}.{rec.get('name')}"
        out = []
        for rec in rows:
            item = dict(rec)
            rid = rec.get("id")
            if rid in xml_map and not item.get("xml_id"):
                item["xml_id"] = xml_map[rid]
            arch = item.get("arch_db")
            if isinstance(arch, str) and not args.full and len(arch) > _ARCH_CAP:
                item["arch_db"] = arch[:_ARCH_CAP] + "…"
            out.append(item)
        print(json.dumps({"ok": True, "model": model, "count": len(out), "views": out}, default=str))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
