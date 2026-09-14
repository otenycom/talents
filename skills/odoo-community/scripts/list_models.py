#!/usr/bin/env python3
"""Look up ir.model rows by technical name or human name."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from local_odoo_rpc import OdooRPC


def main() -> int:
    parser = argparse.ArgumentParser(prog="list_models.py")
    parser.add_argument("--match", required=True)
    parser.add_argument("--limit", type=int, default=40)
    args = parser.parse_args()
    try:
        q = args.match.strip()
        rpc = OdooRPC()
        domain = ["|", ("model", "ilike", q), ("name", "ilike", q)]
        rows = rpc.call(
            "ir.model",
            "search_read",
            kwargs={
                "domain": domain,
                "fields": ["id", "model", "name", "transient", "state"],
                "limit": args.limit,
                "order": "model asc",
            },
        )
        print(json.dumps({"ok": True, "query": q, "count": len(rows or []), "models": rows}, default=str))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
