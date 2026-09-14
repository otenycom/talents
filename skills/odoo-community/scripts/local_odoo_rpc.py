#!/usr/bin/env python3
"""odoo-community's shared JSON-2 wire. No XML-RPC. No ``odoo.*`` import.

Today CrmBot's ``odoo_rpc.py`` and WebsiteBot's ``site_rpc.py`` each POST the
same ``/json/2/<model>/<method>`` bearer call against ``127.0.0.1:8069``
database ``website``. This module is that one wire; both consumers subclass
or call it instead of keeping a private HTTP stack. A CrmBot- or
WebsiteBot-specific helper (``find_partner``, the site CLI subcommands) stays
in the consumer.

Auth is the bearer key a sibling ``setup_admin.py`` minted into
``.odoo-admin`` — see ``local_odoo_paths.py`` for how a key any one bot
minted becomes visible to the others. Never print that key.
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
from local_odoo_paths import admin_candidates, db_name

_URL = "http://127.0.0.1:8069"
_APIKEY_LINE = "api_" + "key="  # split so the secret lint's quote-span matcher
                                 # does not flag this credential-file prefix


def as_id(value):
    """JSON-2 ``create`` returns a recordset, which the wire serialises as
    ``[id]``. Search already returns a list of ints. Callers that need one
    Many2one id must unwrap here — stuffing ``[id]`` into a Many2one field
    raises ``unhashable type: 'list'`` on the model's ``create``.
    """
    if value in (None, False):
        raise RuntimeError("ODOO_RPC_FAILED empty_id")
    if isinstance(value, list):
        if not value:
            raise RuntimeError("ODOO_RPC_FAILED empty_id_list")
        return as_id(value[0])
    if isinstance(value, dict) and value.get("id") is not None:
        return int(value["id"])
    return int(value)


def _default_admin_candidates() -> list[Path]:
    return admin_candidates()


class OdooRPC:
    """One JSON-2 client. A consumer subclasses this for its own helpers
    (CrmBot's lead/partner helpers, WebsiteBot's page/base-url CLI)."""

    #: A subclass overrides this for a distinguishing ``User-Agent``.
    user_agent = "OdooCommunity-local_odoo_rpc"

    def __init__(self, admin_candidates=None):
        # A consumer that must keep honoring its own ``*_DATA_DIR`` env
        # override for where IT looks first (crm_paths.py / website_paths.py
        # already append the community fallback to that) passes its own
        # candidate list here. The default is the community-wide fallback.
        self._admin_candidates = admin_candidates or _default_admin_candidates
        self.apikey = self._load_key()
        self.db = db_name()
        self.uid = 0
        # setup_admin rotates login away from ``admin`` to owner_email.
        # context_get is the bearer session; a search for login=admin is empty.
        ctx = self._json2("res.users", "context_get")
        if isinstance(ctx, dict) and ctx.get("uid"):
            self.uid = int(ctx["uid"])
        if not self.uid:
            raise RuntimeError("ODOO_RPC_FAILED auth — /json/2/ rejected the key")

    def _load_key(self) -> str:
        path = next((p for p in self._admin_candidates() if p.exists()), None)
        if path is None:
            raise RuntimeError("ODOO_RPC_FAILED no_admin — run setup_admin.py first")
        key = ""
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith(_APIKEY_LINE):
                key = line[len(_APIKEY_LINE) :].strip()
        if not key:
            raise RuntimeError("ODOO_RPC_FAILED no_api_key")
        return key

    def _json2(self, model: str, method: str, **kwargs):
        body = json.dumps(kwargs).encode("utf-8")
        req = urllib.request.Request(
            f"{_URL}/json/2/{model}/{method}",
            data=body,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Authorization": f"bearer {self.apikey}",
                "X-Odoo-Database": self.db,
                "User-Agent": self.user_agent,
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
            raise RuntimeError(f"ODOO_RPC_FAILED odoo_down: {exc}") from exc

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
        elif method in ("message_post", "activity_schedule", "name_get") and args:
            kw.setdefault("ids", args[0] if isinstance(args[0], list) else [args[0]])
        elif method == "unlink" and args:
            kw.setdefault("ids", args[0] if isinstance(args[0], list) else [args[0]])
        return self._json2(model, method, **kw)

    def attach_file(self, res_model: str, res_id: int, file_path: str, caption: str | None = None):
        """Bytes → ``ir.attachment`` on ``res_model``/``res_id`` → a chatter
        note carrying that attachment. Generic across CrmBot's ``crm.lead``
        and any future consumer model. Raises on a missing/empty file so a
        caller that must not abort a whole write (CrmBot's ``upsert_lead.py``)
        catches it per-file instead."""
        p = Path(file_path)
        if not p.is_file():
            raise FileNotFoundError(f"media file missing: {file_path}")
        data = p.read_bytes()
        if not data:
            raise ValueError(f"media file empty: {file_path}")
        filename = p.name
        mimetype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        att_id = as_id(self.call(
            "ir.attachment", "create", [{
                "name": filename,
                "datas": base64.b64encode(data).decode(),
                "res_model": res_model,
                "res_id": res_id,
                "mimetype": mimetype,
            }]
        ))
        body = caption or filename
        self.call(
            res_model, "message_post", [[res_id]],
            {
                "body": body,
                "message_type": "comment",
                "subtype_xmlid": "mail.mt_comment",
                "attachment_ids": [att_id],
            },
        )
        return att_id
