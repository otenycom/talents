"""Lean account-key /json/2/ client (from talents _shared/scripts/dev_bot.Oteny)."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

_BROWSER_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


class OdooClient:
    """Bearer /json/2/ client. Compatible with hermeshost dogfood call shapes."""

    def __init__(self, base_url: str, db: str | None = None, api_key: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.db = db
        self.api_key = api_key

    def call(self, model: str, method: str, **kwargs):
        url = f"{self.base_url}/json/2/{model}/{method}"
        data = json.dumps(kwargs).encode()
        req = urllib.request.Request(
            url, data=data, method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "User-Agent": _BROWSER_UA,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                body = json.loads(r.read().decode() or "null")
        except urllib.error.HTTPError as e:
            detail = (e.read().decode() or "")[:400]
            raise RuntimeError(f"HTTP {e.code} from {model}/{method}: {detail}") from None
        if isinstance(body, dict) and body.get("name") and body.get("message"):
            raise RuntimeError(f"Odoo error: {body['name']}: {body['message']}")
        return body

    def search_read(self, model: str, domain, fields=None, limit=None, **kw):
        payload = {"domain": domain}
        if fields is not None:
            payload["fields"] = fields
        if limit is not None:
            payload["limit"] = limit
        payload.update(kw)
        return self.call(model, "search_read", **payload) or []


def client_from_key_file(
    path: str, *, base_url: str | None = None, db: str | None = None,
) -> OdooClient:
    p = Path(path).expanduser()
    key = p.read_text().strip() if p.is_file() else ""
    if not key:
        raise SystemExit(f"empty or missing API key file: {path}")
    return OdooClient(
        base_url=base_url or os.environ.get("OTENY_BASE_URL", "https://oteny.odoo.com"),
        db=db or os.environ.get("OTENY_DB") or None,
        api_key=key,
    )
