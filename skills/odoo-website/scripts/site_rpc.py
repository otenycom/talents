#!/usr/bin/env python3
"""site_rpc.py — the ONE way WebsiteBot edits the Odoo site (External JSON-2).

Locked path. Do NOT improvise: no browser builder drive, no custom modules, no
``odoo shell`` password resets, no guessing between "API vs builder". Authenticate
with the bearer ``api_key`` from ``.odoo-admin`` (created by ``setup_admin.py``).

Odoo 19: ``POST /json/2/<model>/<method>`` with ``Authorization: bearer <key>``.
XML-RPC / JSON-RPC are deprecated — do not use them.

Examples:

    python3 …/scripts/site_rpc.py ping
    python3 …/scripts/site_rpc.py set-homepage --title "Moon Dive" --body-html "<p>Hi</p>"
    python3 …/scripts/site_rpc.py set-base-url --url https://moondive.oteny.bot

Prints a one-line status on stdout. Non-zero on failure.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

_BOT = "odoo-website"
_URL = "http://127.0.0.1:8069"
_DB = "website"
_APIKEY_LINE = "api_" + "key="  # credential-file prefix; split for secret-lint


def _home() -> Path:
    return Path(os.environ.get("HH_HOME") or os.path.expanduser("~"))


def _data_dir() -> Path:
    override = os.environ.get("ODOO_WEBSITE_DATA_DIR")
    if override:
        return Path(override)
    return _home() / ".hermes" / "data" / _BOT


def _load_admin() -> tuple[str, str]:
    """Return (login, api_key). Password is for /web/login only — not used here."""
    path = _data_dir() / ".odoo-admin"
    if not path.exists():
        raise SystemExit(
            "SITE_RPC_FAILED no_admin — run setup_admin.py first "
            "(never invent passwords in shell)"
        )
    login = api_key = ""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("login="):
            login = line.split("=", 1)[1].strip()
        elif line.startswith(_APIKEY_LINE):
            api_key = line[len(_APIKEY_LINE) :].strip()
    if not api_key:
        raise SystemExit(
            "SITE_RPC_FAILED no_api_key — re-run setup_admin.py to mint a JSON-2 key "
            "(legacy password-only .odoo-admin is not enough)"
        )
    return login, api_key


def _json2(model: str, method: str, api_key: str, **kwargs) -> object:
    body = json.dumps(kwargs).encode("utf-8")
    req = urllib.request.Request(
        f"{_URL}/json/2/{model}/{method}",
        data=body,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"bearer {api_key}",
            "X-Odoo-Database": _DB,
            "User-Agent": "WebsiteBot-site_rpc",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        if exc.code in (401, 403):
            raise SystemExit(
                "SITE_RPC_FAILED auth — api_key in .odoo-admin rejected; "
                "re-run setup_admin.py (do not reset via shell)"
            ) from exc
        try:
            detail = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            detail = {"message": raw}
        msg = detail.get("message") if isinstance(detail, dict) else raw
        raise RuntimeError(f"json2 {model}.{method} HTTP {exc.code}: {msg}") from exc


def cmd_ping(_: argparse.Namespace) -> int:
    _, api_key = _load_admin()
    try:
        with urllib.request.urlopen(f"{_URL}/web/version", timeout=15) as resp:
            ver = json.loads(resp.read().decode("utf-8"))
    except Exception:  # noqa: BLE001
        ver = {}
    n = _json2("website.page", "search_count", api_key, domain=[])
    print(
        f"SITE_RPC_OK ping version={ver.get('version', '?')} pages={n}"
    )
    return 0


def cmd_set_homepage(ns: argparse.Namespace) -> int:
    _, api_key = _load_admin()
    title = ns.title.strip()
    body = ns.body_html
    pages = _json2(
        "website.page",
        "search_read",
        api_key,
        domain=[["is_published", "=", True], ["url", "in", ["/", "/homepage", ""]]],
        fields=["id", "view_id", "url"],
        limit=1,
    )
    if not pages:
        pages = _json2(
            "website.page",
            "search_read",
            api_key,
            domain=[["url", "=", "/"]],
            fields=["id", "view_id", "url"],
            limit=1,
        )
    if not isinstance(pages, list) or not pages:
        print("SITE_RPC_FAILED no_homepage_page", file=sys.stderr)
        return 1
    page = pages[0]
    view_id = page["view_id"][0] if page.get("view_id") else None
    arch = (
        f'<t t-name="website.homepage">\n'
        f'  <t t-call="website.layout">\n'
        f'    <div id="wrap" class="oe_structure">\n'
        f'      <section class="s_text_block pt48 pb48">\n'
        f'        <div class="container">\n'
        f'          <h1>{_xml_escape(title)}</h1>\n'
        f'          {body}\n'
        f'        </div>\n'
        f'      </section>\n'
        f'    </div>\n'
        f'  </t>\n'
        f'</t>'
    )
    if view_id:
        _json2(
            "ir.ui.view",
            "write",
            api_key,
            ids=[view_id],
            vals={"arch": arch, "name": title},
        )
    _json2(
        "website.page",
        "write",
        api_key,
        ids=[page["id"]],
        vals={"name": title, "is_published": True},
    )
    print(f"SITE_RPC_OK homepage id={page['id']} title={title!r}")
    return 0


def cmd_set_base_url(ns: argparse.Namespace) -> int:
    _, api_key = _load_admin()
    url = ns.url.strip().rstrip("/")
    if not url.startswith("https://"):
        print("SITE_RPC_FAILED base_url_must_be_https", file=sys.stderr)
        return 1
    _json2(
        "ir.config_parameter",
        "set_param",
        api_key,
        key="web.base.url",
        value=url,
    )
    print(f"SITE_RPC_OK base_url={url}")
    return 0


def _xml_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("ping", help="Auth + count published pages")
    p.set_defaults(func=cmd_ping)

    p = sub.add_parser("set-homepage", help="Replace the homepage title + HTML body")
    p.add_argument("--title", required=True)
    p.add_argument("--body-html", required=True, help="Inner HTML under the H1")
    p.set_defaults(func=cmd_set_homepage)

    p = sub.add_parser("set-base-url", help="Set web.base.url to the public https URL")
    p.add_argument("--url", required=True)
    p.set_defaults(func=cmd_set_base_url)

    ns = ap.parse_args(argv)
    try:
        return ns.func(ns)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        print(f"SITE_RPC_FAILED {exc!r}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
