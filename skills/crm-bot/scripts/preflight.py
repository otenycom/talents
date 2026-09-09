#!/usr/bin/env python3
"""Per-turn context for CrmBot. Exit 0 always. Readiness is in the output."""
from __future__ import annotations

import os
import socket
from pathlib import Path

_PORT = 8069


def _home() -> Path:
    return Path(os.environ.get("HH_HOME") or os.path.expanduser("~"))


def _odoo_serving() -> bool:
    try:
        s = socket.create_connection(("127.0.0.1", _PORT), timeout=3)
        s.close()
        return True
    except OSError:
        return False


def _engine() -> bool:
    base = _home() / "odoo-site"
    return (base / ".deps-installed").exists() and (base / "odoo" / "odoo").is_dir()


def _pg_up() -> bool:
    try:
        s = socket.create_connection(("127.0.0.1", 5432), timeout=2)
        s.close()
        return True
    except OSError:
        return False


def _json2_ok() -> bool:
    if not _odoo_serving():
        return False
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from odoo_rpc import OdooRPC
        rpc = OdooRPC()
        return bool(rpc.uid)
    except Exception:
        return False


def main() -> int:
    print(f"ENGINE: {'installed' if _engine() else 'missing'}")
    print(f"ODOO: {'serving' if _odoo_serving() else 'down'}")
    print(f"POSTGRES: {'up' if _pg_up() else 'down'}")
    print(f"JSON2: {'ok' if _json2_ok() else 'down'}")
    print("PUBLIC: use list_hosted_websites — never a hardcoded host")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
