#!/usr/bin/env python3
"""Delete (unlink) a CRM lead after the owner confirmed.

    python3 delete_lead.py --lead-id 42

Prints JSON. Never invents an id. Exits 2 when Odoo is down.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from odoo_rpc import OdooRPC  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lead-id", type=int, required=True)
    ns = ap.parse_args(argv)
    try:
        rpc = OdooRPC()
        rpc.unlink_lead(ns.lead_id)
    except Exception as exc:
        print(json.dumps({"error": str(exc), "lead_id": None, "deleted": False}))
        return 2
    print(json.dumps({"lead_id": ns.lead_id, "deleted": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
