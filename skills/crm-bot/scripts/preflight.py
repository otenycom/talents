#!/usr/bin/env python3
"""Per-turn context for CrmBot. Exit 0 always. Readiness is in the output."""
from __future__ import annotations

import socket
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from crm_paths import implicit_setup, profile_path

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


def _xmlid_res_id(rpc, xmlid: str):
    module, _, name = xmlid.partition(".")
    if not module or not name:
        return None
    rows = rpc.call(
        "ir.model.data",
        "search_read",
        [[("module", "=", module), ("name", "=", name)]],
        {"fields": ["res_id"], "limit": 1},
    )
    if not rows:
        return None
    return int(rows[0]["res_id"])


def _menu_sequence(rpc, xmlid: str):
    mid = _xmlid_res_id(rpc, xmlid)
    if not mid:
        return None
    rows = rpc.call("ir.ui.menu", "read", [[mid]], {"fields": ["sequence"]})
    if not rows:
        return None
    return int(rows[0].get("sequence") or 0)


def crm_home_state(rpc) -> str:
    """``first`` when CRM's root menu beats Discuss. Else ``discuss`` or ``-``."""
    crm_seq = _menu_sequence(rpc, "crm.crm_menu_root")
    if crm_seq is None:
        return "-"
    discuss_seq = _menu_sequence(rpc, "mail.menu_root_discuss")
    if discuss_seq is None:
        return "first" if crm_seq <= 1 else "discuss"
    return "first" if crm_seq < discuss_seq else "discuss"


def _crm_status() -> tuple[str, str]:
    if not _odoo_serving():
        return "unknown", "-"
    try:
        from odoo_rpc import OdooRPC
        rpc = OdooRPC()
        ids = rpc.call(
            "ir.module.module",
            "search",
            [[("name", "=", "crm"), ("state", "=", "installed")]],
            {"limit": 1},
        )
        if not ids:
            return "missing", "-"
        return "installed", crm_home_state(rpc)
    except Exception:
        return "unknown", "-"


def main() -> int:
    implied = implicit_setup()
    print(f"ENGINE: {'installed' if _engine() else 'missing'}")
    print(f"ODOO: {'serving' if _odoo_serving() else 'down'}")
    print(f"POSTGRES: {'up' if _pg_up() else 'down'}")
    print(f"JSON2: {'ok' if _json2_ok() else 'down'}")
    crm, crm_home = _crm_status()
    print(f"CRM: {crm}")
    print(f"CRM_HOME: {crm_home}")
    print(f"PROFILE: {'present' if _profile_present() else 'missing'}")
    print(f"EVENT: {implied['event_name'] or '-'}")
    print(f"ADMIN: {implied['owner_email'] or '-'}")
    print(f"LANGUAGE: {implied['language'] or '-'}")
    print(f"ADMIN_FILE: {implied['admin_file']}")
    print(f"SITE_NAME: {implied['site_slug'] or '-'}")
    print("PUBLIC: use list_hosted_websites — never a hardcoded host")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
