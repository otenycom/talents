#!/usr/bin/env python3
"""CRUD on one Odoo model via JSON-2 — the on-demand fallback (odoo-community
`references/local-odoo-client.md`) for a job a consumer's own checklist does
not name.

Subcommands: search, count, read, create, write, unlink.
create/write/unlink require --confirm. Domain/vals JSON on stdin or flags.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from local_odoo_rpc import OdooRPC, as_id


def _stdin() -> dict:
    if sys.stdin.isatty():
        return {}
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("stdin JSON must be an object")
    return data


def _ids(value: str | None, extra) -> list[int]:
    out: list[int] = []
    if value:
        for part in str(value).split(","):
            part = part.strip()
            if part:
                out.append(int(part))
    if extra is not None:
        if isinstance(extra, list):
            out.extend(int(x) for x in extra)
        else:
            out.append(int(extra))
    return out


def _fields(value: str | None, extra) -> list[str]:
    if extra:
        return list(extra)
    if not value:
        return ["id", "display_name"]
    return [p.strip() for p in value.split(",") if p.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(prog="crud.py")
    parser.add_argument("action", choices=["search", "count", "read", "create", "write", "unlink"])
    parser.add_argument("--model", required=True)
    parser.add_argument("--ids", default="")
    parser.add_argument("--fields", default="")
    parser.add_argument("--domain", default="")
    parser.add_argument("--limit", type=int, default=80)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--order", default="")
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    try:
        body = _stdin()
        domain = body.get("domain")
        if domain is None and args.domain:
            domain = json.loads(args.domain)
        if domain is None:
            domain = []
        vals = body.get("vals") or body.get("vals_list")
        fields = _fields(args.fields, body.get("fields"))
        ids = _ids(args.ids, body.get("ids"))
        rpc = OdooRPC()
        action = args.action
        if action in ("create", "write", "unlink") and not args.confirm:
            print(json.dumps({"ok": False, "error": "confirm_required"}))
            return 0
        if action == "search":
            kw = {"domain": domain, "fields": fields, "limit": args.limit, "offset": args.offset}
            if args.order:
                kw["order"] = args.order
            rows = rpc.call(args.model, "search_read", kwargs=kw)
            id_list = [as_id(r.get("id")) for r in (rows or []) if isinstance(r, dict)]
            print(json.dumps(
                {"ok": True, "model": args.model, "method": "search_read", "ids": id_list, "records": rows},
                default=str,
            ))
            return 0
        if action == "count":
            n = rpc.call(args.model, "search_count", kwargs={"domain": domain})
            print(json.dumps({"ok": True, "model": args.model, "method": "search_count", "count": n}))
            return 0
        if action == "read":
            if not ids:
                print(json.dumps({"ok": False, "error": "ids_required"}))
                return 0
            rows = rpc.call(args.model, "read", kwargs={"ids": ids, "fields": fields})
            print(json.dumps(
                {"ok": True, "model": args.model, "method": "read", "ids": ids, "records": rows},
                default=str,
            ))
            return 0
        if action == "create":
            if not isinstance(vals, dict):
                print(json.dumps({"ok": False, "error": "vals_object_required"}))
                return 0
            new_id = as_id(rpc.call(args.model, "create", kwargs={"vals_list": [vals]}))
            print(json.dumps({"ok": True, "model": args.model, "method": "create", "id": new_id}))
            return 0
        if action == "write":
            if not ids or not isinstance(vals, dict):
                print(json.dumps({"ok": False, "error": "ids_and_vals_required"}))
                return 0
            rpc.call(args.model, "write", kwargs={"ids": ids, "vals": vals})
            print(json.dumps({"ok": True, "model": args.model, "method": "write", "ids": ids}))
            return 0
        if action == "unlink":
            if not ids:
                print(json.dumps({"ok": False, "error": "ids_required"}))
                return 0
            rpc.call(args.model, "unlink", kwargs={"ids": ids})
            print(json.dumps({"ok": True, "model": args.model, "method": "unlink", "ids": ids}))
            return 0
        print(json.dumps({"ok": False, "error": "unknown_action"}))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
