#!/usr/bin/env python3
"""Per-turn context for CrmBot. Exit 0 always. Readiness is in the output."""
from __future__ import annotations

import socket
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from crm_paths import profile_path

_PORT = 8069


def _home() -> Path:
    from crm_paths import home
    return home()


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


def _profile_present() -> bool:
    path = profile_path()
    return path.is_file() and path.stat().st_size > 0


def main() -> int:
    print(f"ENGINE: {'installed' if _engine() else 'missing'}")
    print(f"ODOO: {'serving' if _odoo_serving() else 'down'}")
    print(f"POSTGRES: {'up' if _pg_up() else 'down'}")
    print(f"JSON2: {'ok' if _json2_ok() else 'down'}")
    print(f"PROFILE: {'present' if _profile_present() else 'missing'}")
    print("PUBLIC: use list_hosted_websites — never a hardcoded host")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
