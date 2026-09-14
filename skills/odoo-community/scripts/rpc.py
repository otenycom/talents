#!/usr/bin/env python3
"""Generic JSON-2 escape hatch. Stdin JSON: model, method, optional confirm,
plus kwargs. Use only when `crud.py` does not cover the call.

Writes (create / write / unlink) require confirm=true. Never prints the API
key.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from local_odoo_rpc import OdooRPC, as_id

_WRITE = {"create", "write", "unlink"}


def _load_stdin() -> dict:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("stdin JSON must be an object")
    return data


def main() -> int:
    try:
        payload = _load_stdin()
        model = str(payload.pop("model", "") or "")
        method = str(payload.pop("method", "") or "")
        confirm = bool(payload.pop("confirm", False))
        if not model or not method:
            print(json.dumps({"ok": False, "error": "model and method required"}))
            return 0
        if method in _WRITE and not confirm:
            print(json.dumps({"ok": False, "error": "confirm_required"}))
            return 0
        rpc = OdooRPC()
        result = rpc.call(model, method, kwargs=payload)
        if method == "create":
            result = as_id(result)
        print(json.dumps({"ok": True, "model": model, "method": method, "result": result}, default=str))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
