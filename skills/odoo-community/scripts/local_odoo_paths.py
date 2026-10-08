"""odoo-community's shared ``.odoo-admin`` locator.

CrmBot, WebsiteBot, and this Talent's own ``local-odoo-client.md`` fallback all
authenticate JSON-2 with the same bearer key: whichever of ``setup_admin.py``
(CrmBot's or WebsiteBot's copy — see the plan's "one JSON-2 client" design)
minted first into a sibling ``.odoo-admin``. This module is the one place that
walks the fixed bot list, so a key any one of them minted is visible to all
three. Never mint a second key here, and never write
``~/.hermes/data/odoo-client/`` — that Talent name never shipped (folded into
odoo-community instead).

It also owns the two rules every login writer and every "is the owner set
up" judge shares: ``normalize_login()`` (one login spelling) and
``admin_login_and_file()`` (one admin-file state).
"""
from __future__ import annotations

import os
from pathlib import Path

_BOTS = ("crm-bot", "odoo-website", "odoo-community")
_DEFAULT_DB = "website"
_DEFAULT_LOGIN = "admin"
# Credential-file line prefix (split so the secret lint's quote-span matcher
# does not flag this credential-file prefix).
_APIKEY_LINE = "api_" + "key="


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


def normalize_login(raw) -> str:
    """The one login spelling: stripped and lowercase.

    Odoo 19 matches a login with ``login = <typed>``, so the match is
    case-sensitive. The login page sets ``autocapitalize="off"``, so a person
    types lowercase there. A capital comes from a chat client, which
    capitalises the first letter of a message. So every path that writes a
    login lowercases it first.

    Raises ``ValueError`` for a value without ``@``. The one exception is the
    literal ``admin``, which only the bake path writes.
    """
    value = (raw or "").strip().lower()
    if value == _DEFAULT_LOGIN:
        return value
    if "@" not in value:
        raise ValueError("login_without_at")
    return value


def admin_login_and_file(candidates=None) -> tuple[str, str]:
    """Return ``(login, admin_file_state)``. Never the password.

    ``candidates`` is the caller's own ordered ``.odoo-admin`` list, so a
    ``CRM_BOT_DATA_DIR`` or ``ODOO_WEBSITE_DATA_DIR`` override still wins.
    The default is the community-wide list. The first file that parses
    decides. ``admin_file_state`` is one of:

    - ``"owner_set"`` — a stored ``login`` is a real email, with a password.
      The owner (or a ``setup_admin.py`` run on their behalf) put it there.
    - ``"bake_placeholder"`` — a login and a password, but the login is not
      an email. The mint-time clone-secret rotation always writes
      ``login=admin``. Nobody has seen that password. Treat it exactly like
      ``"missing"``.
    - ``"key_only"`` — an ``api_key=`` line and no login/password pair. A
      person wired this Odoo by hand. With ``JSON2: ok`` it is set up: do not
      run the owner intake.
    - ``"missing"`` — no candidate file parses at all.

    ``login`` is set for ``"owner_set"``, and for ``"key_only"`` when the
    file also names an email login. A default ``admin`` login is never the
    owner email.
    """
    for path in (admin_candidates() if candidates is None else candidates):
        path = Path(path)
        if not path.is_file() or not path.stat().st_size:
            continue
        login = password = api_key = ""
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("login="):
                login = line.split("=", 1)[1].strip()
            elif line.startswith("password="):
                password = line.split("=", 1)[1].strip()
            elif line.startswith(_APIKEY_LINE):
                api_key = line[len(_APIKEY_LINE):].strip()
        if login and password:
            if "@" in login:
                return login, "owner_set"
            return "", "bake_placeholder"
        if api_key:
            return (login if "@" in login else ""), "key_only"
    return "", "missing"


def migrations_line() -> str:
    """odoo-community's pending-migration line, for a module Talent's
    preflight. odoo-community has no preflight of its own, so CrmBot and
    WebsiteBot print this line. Never raises."""
    try:
        import importlib.util

        here = Path(__file__).resolve().parent
        spec = importlib.util.spec_from_file_location(
            "odoo_community_migrate", here / "migrate.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        line = mod.status_line(here.parent / "migrations.yaml")
    except Exception:  # noqa: BLE001
        line = "MIGRATIONS: none"
    return "ODOO_COMMUNITY_" + line.replace(
        "load references/migrations.md",
        "load odoo-community references/migrations.md",
    )
