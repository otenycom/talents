#!/usr/bin/env python3
"""CrmBot → Odoo External JSON-2. No XML-RPC. No odoo.* import.

Auth is the bearer key setup_admin.py mints into
``~/.hermes/data/crm-bot/.odoo-admin``. Same database name ``website``
as odoo-community (a carried cluster needs no rename).
"""
from __future__ import annotations

import base64
import json
import mimetypes
import sys
import urllib.error
import urllib.request
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from crm_paths import admin_candidates

_URL = "http://127.0.0.1:8069"
_DB = "website"
_APIKEY_LINE = "api_" + "key="


def _load_key() -> str:
    path = next((p for p in admin_candidates() if p.exists()), None)
    if path is None:
        raise RuntimeError("CRM_RPC_FAILED no_admin — run setup_admin.py first")
    key = ""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(_APIKEY_LINE):
            key = line[len(_APIKEY_LINE) :].strip()
    if not key:
        raise RuntimeError("CRM_RPC_FAILED no_api_key")
    return key


class OdooRPC:
    def __init__(self):
        self.apikey = _load_key()
        self.uid = 0
        # setup_admin rotates login away from ``admin`` to owner_email.
        # context_get is the bearer session; a search for login=admin is empty.
        ctx = self._json2("res.users", "context_get")
        if isinstance(ctx, dict) and ctx.get("uid"):
            self.uid = int(ctx["uid"])
        if not self.uid:
            raise RuntimeError("CRM_RPC_FAILED auth — /json/2/ rejected the key")

    def _json2(self, model: str, method: str, **kwargs):
        body = json.dumps(kwargs).encode("utf-8")
        req = urllib.request.Request(
            f"{_URL}/json/2/{model}/{method}",
            data=body,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Authorization": f"bearer {self.apikey}",
                "X-Odoo-Database": _DB,
                "User-Agent": "CrmBot-odoo_rpc",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"json2 {model}.{method} HTTP {exc.code}: {raw}") from exc
        except OSError as exc:
            raise RuntimeError(f"CRM_RPC_FAILED odoo_down: {exc}") from exc

    def call(self, model, method, args=None, kwargs=None):
        args = list(args or [])
        kw = dict(kwargs or {})
        if method in ("search", "search_count", "search_read") and args:
            kw.setdefault("domain", args[0])
        elif method == "create" and args:
            payload = args[0]
            kw.setdefault("vals_list", [payload] if isinstance(payload, dict) else payload)
        elif method == "write" and len(args) >= 2:
            ids = args[0] if isinstance(args[0], list) else [args[0]]
            kw.setdefault("ids", ids)
            kw.setdefault("vals", args[1])
        elif method == "read" and args:
            kw.setdefault("ids", args[0] if isinstance(args[0], list) else [args[0]])
        elif method in ("message_post", "activity_schedule") and args:
            kw.setdefault("ids", args[0] if isinstance(args[0], list) else [args[0]])
        elif method == "unlink" and args:
            kw.setdefault("ids", args[0] if isinstance(args[0], list) else [args[0]])
        return self._json2(model, method, **kw)

    def find_user(self, login: str):
        ids = self.call("res.users", "search", [[("login", "=", login)]], {"limit": 1})
        return ids[0] if ids else None

    def get_or_create_by_name(self, model: str, name: str, extra: dict | None = None) -> int:
        ids = self.call(model, "search", [[("name", "=ilike", name)]], {"limit": 1})
        if ids:
            return ids[0]
        return self.call(model, "create", [{"name": name, **(extra or {})}])

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
            return ids[0]
        return self.call("res.partner", "create", [{"name": company, "is_company": True}])

    def create_partner(self, vals: dict) -> int:
        return self.call("res.partner", "create", [vals])

    def write_partner(self, partner_id: int, vals: dict) -> bool:
        return self.call("res.partner", "write", [[partner_id], vals])

    def read_partner(self, partner_id: int, fields: list[str]) -> dict:
        rows = self.call("res.partner", "read", [[partner_id]], {"fields": fields})
        return rows[0]

    def create_lead(self, vals: dict) -> int:
        return self.call("crm.lead", "create", [vals])

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
        p = Path(file_path)
        if not p.is_file():
            raise FileNotFoundError(f"media file missing: {file_path}")
        data = p.read_bytes()
        if not data:
            raise ValueError(f"media file empty: {file_path}")
        filename = p.name
        mimetype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        att_id = self.call(
            "ir.attachment", "create", [{
                "name": filename,
                "datas": base64.b64encode(data).decode(),
                "res_model": "crm.lead",
                "res_id": lead_id,
                "mimetype": mimetype,
            }]
        )
        caption = name or filename
        self.call(
            "crm.lead", "message_post", [[lead_id]],
            {
                "body": caption,
                "message_type": "comment",
                "subtype_xmlid": "mail.mt_comment",
                "attachment_ids": [att_id],
            },
        )
        return att_id
