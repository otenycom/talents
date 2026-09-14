#!/usr/bin/env python3
"""site_rpc.py — the ONE way WebsiteBot edits the Odoo site (External JSON-2).

Locked path. Do NOT improvise: no browser builder drive, no custom modules, no
``odoo shell`` password resets, no guessing between "API vs builder". Authenticate
with the bearer ``api_key`` from ``.odoo-admin`` (created by ``setup_admin.py``).

Odoo 19: ``POST /json/2/<model>/<method>`` with ``Authorization: bearer <key>``.
XML-RPC / JSON-RPC are deprecated — do not use them.

The wire (bearer POST, the ``call`` kwargs map) lives in odoo-community's
``local_odoo_rpc.py`` — see that module's docstring for why: CrmBot's
``odoo_rpc.py`` used to duplicate this same HTTP stack byte-for-byte. This
file keeps only the ``ping`` / ``set-homepage`` / ``set-base-url`` CLI
subcommands.

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
import urllib.request
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from website_paths import admin_candidates


def _find_community_scripts() -> Path:
    """Locate odoo-community's ``scripts/`` dir: env var → catalog sibling
    (this checkout) → box path (``HH_HOME`` when set). Raises when community
    was never delivered."""
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
from local_odoo_rpc import OdooRPC as _CommunityOdooRPC

_URL = "http://127.0.0.1:8069"


class OdooRPC(_CommunityOdooRPC):
    user_agent = "WebsiteBot-site_rpc"

    def __init__(self):
        # WebsiteBot's own admin_candidates() honors ODOO_WEBSITE_DATA_DIR
        # first, then falls back to the community-wide list — see that
        # module for why the community default alone is not enough here.
        super().__init__(admin_candidates=admin_candidates)


def cmd_ping(_: argparse.Namespace) -> int:
    rpc = OdooRPC()
    try:
        with urllib.request.urlopen(f"{_URL}/web/version", timeout=15) as resp:
            ver = json.loads(resp.read().decode("utf-8"))
    except Exception:  # noqa: BLE001
        ver = {}
    n = rpc.call("website.page", "search_count", kwargs={"domain": []})
    print(
        f"SITE_RPC_OK ping version={ver.get('version', '?')} pages={n}"
    )
    return 0


def cmd_set_homepage(ns: argparse.Namespace) -> int:
    rpc = OdooRPC()
    title = ns.title.strip()
    body = ns.body_html
    pages = rpc.call(
        "website.page",
        "search_read",
        kwargs={
            "domain": [["is_published", "=", True], ["url", "in", ["/", "/homepage", ""]]],
            "fields": ["id", "view_id", "url"],
            "limit": 1,
        },
    )
    if not pages:
        pages = rpc.call(
            "website.page",
            "search_read",
            kwargs={
                "domain": [["url", "=", "/"]],
                "fields": ["id", "view_id", "url"],
                "limit": 1,
            },
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
        rpc.call(
            "ir.ui.view",
            "write",
            kwargs={"ids": [view_id], "vals": {"arch": arch, "name": title}},
        )
    rpc.call(
        "website.page",
        "write",
        kwargs={"ids": [page["id"]], "vals": {"name": title, "is_published": True}},
    )
    print(f"SITE_RPC_OK homepage id={page['id']} title={title!r}")
    return 0


def cmd_set_base_url(ns: argparse.Namespace) -> int:
    rpc = OdooRPC()
    url = ns.url.strip().rstrip("/")
    if not url.startswith("https://"):
        print("SITE_RPC_FAILED base_url_must_be_https", file=sys.stderr)
        return 1
    rpc.call(
        "ir.config_parameter",
        "set_param",
        kwargs={"key": "web.base.url", "value": url},
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
