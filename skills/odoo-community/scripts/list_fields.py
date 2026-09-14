#!/usr/bin/env python3
"""Fields on one model. Default: fields_get. --catalog uses ir.model.fields."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from local_odoo_rpc import OdooRPC


def _compact_fields_get(raw: dict) -> list[dict]:
    out = []
    for name, info in sorted((raw or {}).items()):
        if not isinstance(info, dict):
            continue
        row = {
            "name": name,
            "type": info.get("type"),
            "string": info.get("string"),
            "required": bool(info.get("required")),
            "readonly": bool(info.get("readonly")),
            "store": info.get("store"),
            "relation": info.get("relation") or "",
        }
        sel = info.get("selection")
        if isinstance(sel, list) and sel:
            row["selection"] = sel[:30]
        out.append(row)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(prog="list_fields.py")
    parser.add_argument("--model", required=True)
    parser.add_argument("--catalog", action="store_true")
    parser.add_argument("--match", default="")
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args()
    try:
        rpc = OdooRPC()
        model = args.model.strip()
        q = args.match.strip().lower()
        if args.catalog:
            domain = [("model", "=", model)]
            if q:
                domain = ["&", domain[0], "|", ("name", "ilike", q), ("field_description", "ilike", q)]
            rows = rpc.call(
                "ir.model.fields",
                "search_read",
                kwargs={
                    "domain": domain,
                    "fields": ["name", "field_description", "ttype", "required", "readonly", "store", "relation"],
                    "limit": args.limit,
                    "order": "name asc",
                },
            )
            print(json.dumps(
                {"ok": True, "model": model, "source": "ir.model.fields", "count": len(rows or []), "fields": rows},
                default=str,
            ))
            return 0
        raw = rpc.call(model, "fields_get", kwargs={})
        rows = _compact_fields_get(raw if isinstance(raw, dict) else {})
        if q:
            rows = [r for r in rows if q in r["name"].lower() or q in str(r.get("string") or "").lower()]
        print(json.dumps(
            {"ok": True, "model": model, "source": "fields_get", "count": len(rows), "fields": rows[: args.limit]},
            default=str,
        ))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
