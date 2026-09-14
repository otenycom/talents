#!/usr/bin/env python3
"""CrmBot → Odoo External JSON-2. No XML-RPC. No odoo.* import.

Auth is the bearer key setup_admin.py mints into
``~/.hermes/data/crm-bot/.odoo-admin``. Same database name ``website``
as odoo-community (a carried cluster needs no rename).

The wire (bearer POST, ``as_id`` create-unwrap, ``call`` kwargs map,
``attach_file``) lives in odoo-community's ``local_odoo_rpc.py`` — see that
module's docstring. This file keeps CrmBot's own lead/partner helpers on a
thin subclass.
"""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from crm_paths import admin_candidates


def _find_community_scripts() -> Path:
    """Locate odoo-community's ``scripts/`` dir: env var → catalog sibling
    (this checkout) → box path (``HH_HOME`` when set). Raises when community
    was never delivered."""
    import os

    override = os.environ.get("ODOO_COMMUNITY_SCRIPTS")
    candidates = [Path(override)] if override else []
    candidates.append(Path(__file__).resolve().parents[2] / "odoo-community" / "scripts")
    candidates.append(
        Path(os.environ.get("HH_HOME") or os.path.expanduser("~"))
        / ".hermes" / "skills" / "talents" / "odoo-community" / "scripts"
    )
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    raise RuntimeError("ODOO_RPC_FAILED no_community_scripts — community was not delivered")


_COMMUNITY_SCRIPTS = _find_community_scripts()
if str(_COMMUNITY_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_COMMUNITY_SCRIPTS))
from local_odoo_rpc import OdooRPC as _CommunityOdooRPC, as_id

# ``_as_id`` is directly unit-tested (test_odoo_rpc_uid.py) — re-bind the
# community name so that contract keeps holding on this module.
_as_id = as_id


class OdooRPC(_CommunityOdooRPC):
    user_agent = "CrmBot-odoo_rpc"

    def __init__(self):
        # CrmBot's own admin_candidates() honors CRM_BOT_DATA_DIR first, then
        # falls back to the community-wide list — see that module for why
        # the community default alone is not enough here.
        super().__init__(admin_candidates=admin_candidates)

    def find_user(self, login: str):
        ids = self.call("res.users", "search", [[("login", "=", login)]], {"limit": 1})
        return ids[0] if ids else None

    def get_or_create_by_name(self, model: str, name: str, extra: dict | None = None) -> int:
        ids = self.call(model, "search", [[("name", "=ilike", name)]], {"limit": 1})
        if ids:
            return _as_id(ids)
        return _as_id(self.call(model, "create", [{"name": name, **(extra or {})}]))

    def find_partner(self, name, company, email, phone=None):
        """Cross-staff dedupe: email, then phone, then name+company, then name."""
        if email:
            ids = self.call("res.partner", "search", [[("email", "=ilike", email)]], {"limit": 1})
            if ids:
                return ids[0]
        if phone:
            ids = self.call("res.partner", "search", [[("phone", "=", phone)]], {"limit": 1})
            if ids:
                return ids[0]
        if name and company:
            ids = self.call(
                "res.partner",
                "search",
                [[
                    "&",
                    ("name", "=ilike", name),
                    "|",
                    ("parent_id.name", "=ilike", company),
                    ("parent_id", "=", False),
                ]],
                {"limit": 1, "order": "id asc"},
            )
            if ids:
                return ids[0]
        if name:
            ids = self.call(
                "res.partner",
                "search",
                [[("name", "=ilike", name), ("is_company", "=", False)]],
                {"limit": 1, "order": "id asc"},
            )
            if ids:
                return ids[0]
        if company and not name:
            ids = self.call(
                "res.partner",
                "search",
                [[("name", "=ilike", company), ("is_company", "=", True)]],
                {"limit": 1},
            )
            if ids:
                return ids[0]
        return None

    def ensure_company(self, company: str) -> int:
        ids = self.call(
            "res.partner", "search",
            [[("name", "=ilike", company), ("is_company", "=", True)]],
            {"limit": 1},
        )
        if ids:
            return _as_id(ids)
        return _as_id(self.call("res.partner", "create", [{"name": company, "is_company": True}]))

    def create_partner(self, vals: dict) -> int:
        return _as_id(self.call("res.partner", "create", [vals]))

    def write_partner(self, partner_id: int, vals: dict) -> bool:
        return self.call("res.partner", "write", [[partner_id], vals])

    def read_partner(self, partner_id: int, fields: list[str]) -> dict:
        rows = self.call("res.partner", "read", [[partner_id]], {"fields": fields})
        return rows[0]

    def create_lead(self, vals: dict) -> int:
        return _as_id(self.call("crm.lead", "create", [vals]))

    def write_lead(self, lead_id: int, vals: dict) -> bool:
        return self.call("crm.lead", "write", [[lead_id], vals])

    def read_lead(self, lead_id: int, fields: list[str]) -> dict:
        return self.call("crm.lead", "read", [[lead_id]], {"fields": fields})[0]

    def find_open_lead_for_partner(self, partner_id: int, event: str | None = None):
        # Do not filter type='lead' — Odoo 19 defaults to opportunity (pitfall 15).
        domain = [("partner_id", "=", partner_id), ("active", "=", True)]
        if event:
            domain.append(("source_id.name", "=", event))
        ids = self.call("crm.lead", "search", [domain], {"limit": 1, "order": "create_date desc"})
        return ids[0] if ids else None

    def unlink_lead(self, lead_id: int) -> bool:
        return self.call("crm.lead", "unlink", [[lead_id]])

    def open_activities(self, lead_id: int) -> list[dict]:
        return self.call(
            "mail.activity", "search_read",
            [[("res_model", "=", "crm.lead"), ("res_id", "=", lead_id)]],
            {"fields": ["id", "summary", "date_deadline", "user_id"]},
        )

    def schedule_activity(self, lead_id: int, summary: str, date_deadline: str,
                          user_id: int, note_html: str | None = None):
        summary = summary[:200]
        self.call(
            "crm.lead", "activity_schedule", [[lead_id]],
            {
                "act_type_xmlid": "mail.mail_activity_data_call",
                "date_deadline": date_deadline,
                "summary": summary,
                "note": note_html or "",
                "user_id": user_id,
            },
        )
        acts = [a for a in self.open_activities(lead_id) if (a.get("summary") or "") == summary]
        return acts[-1]["id"] if acts else None

    def post_note(self, lead_id: int, body_html: str):
        return self.call(
            "crm.lead", "message_post", [[lead_id]],
            {"body": body_html, "message_type": "comment", "subtype_xmlid": "mail.mt_note"},
        )

    def attach_file(self, lead_id: int, file_path: str, name: str | None = None):
        return super().attach_file("crm.lead", lead_id, file_path, caption=name)

    def set_partner_avatar(self, partner_id: int, file_path: str) -> None:
        """Write ``res.partner.image_1920`` from a photo file (base64). CRM-
        specific business rule (when a photo becomes the contact picture) —
        see ``upsert_lead.py`` for the caller-side decision of *when* to call
        this. The community base has no avatar concept of its own."""
        import base64

        p = Path(file_path)
        if not p.is_file():
            raise FileNotFoundError(f"media file missing: {file_path}")
        data = p.read_bytes()
        if not data:
            raise ValueError(f"media file empty: {file_path}")
        self.write_partner(partner_id, {"image_1920": base64.b64encode(data).decode()})
