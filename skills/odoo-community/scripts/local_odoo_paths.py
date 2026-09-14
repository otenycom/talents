"""odoo-community's shared ``.odoo-admin`` locator.

CrmBot, WebsiteBot, and this Talent's own ``local-odoo-client.md`` fallback all
authenticate JSON-2 with the same bearer key: whichever of ``setup_admin.py``
(CrmBot's or WebsiteBot's copy — see the plan's "one JSON-2 client" design)
minted first into a sibling ``.odoo-admin``. This module is the one place that
walks the fixed bot list, so a key any one of them minted is visible to all
three. Never mint a second key here, and never write
``~/.hermes/data/odoo-client/`` — that Talent name never shipped (folded into
odoo-community instead).
"""
from __future__ import annotations

import os
from pathlib import Path

_BOTS = ("crm-bot", "odoo-website", "odoo-community")
_DEFAULT_DB = "website"


def home() -> Path:
    return Path(os.environ.get("HH_HOME") or os.path.expanduser("~"))


def admin_candidates() -> list[Path]:
    """``.odoo-admin`` under ``~/.hermes/data/<bot>`` then ``~/.hermes/<bot>``,
    for each bot in ``_BOTS``, in that order. This is the cross-bot fallback
    list — each bot's own ``crm_paths.py`` / ``website_paths.py`` still honors
    its own ``*_DATA_DIR`` env override for its own candidates first, and
    appends whatever this function finds that is not already covered.
    """
    root = home() / ".hermes"
    paths: list[Path] = []
    for bot in _BOTS:
        for dest in (root / "data" / bot, root / bot):
            path = dest / ".odoo-admin"
            if path not in paths:
                paths.append(path)
    return paths


def db_name() -> str:
    """``db=`` from the first admin file found; else the community default
    (``website`` — the same convention CrmBot / WebsiteBot already use)."""
    path = next((p for p in admin_candidates() if p.exists()), None)
    if path is None:
        return _DEFAULT_DB
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("db="):
            value = line.split("=", 1)[1].strip()
            if value:
                return value
    return _DEFAULT_DB
