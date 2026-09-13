"""Writable CrmBot data dir.

``~/.hermes/data`` can be root-owned on a fresh box (host mkdir as root).
Hermes then cannot create ``data/crm-bot``. Prefer the canonical
``~/.hermes/data/crm-bot`` path. When that parent is not writable, use
``~/.hermes/crm-bot`` (the home folder is already the sandbox user's).
"""
from __future__ import annotations

import os
from pathlib import Path

_BOT = "crm-bot"
_ENV = "CRM_BOT_DATA_DIR"


def home() -> Path:
    return Path(os.environ.get("HH_HOME") or os.path.expanduser("~"))


def data_dir_candidates() -> list[Path]:
    override = os.environ.get(_ENV)
    if override:
        return [Path(override)]
    root = home() / ".hermes"
    return [root / "data" / _BOT, root / _BOT]


def writable_data_dir() -> Path:
    last: OSError | None = None
    for dest in data_dir_candidates():
        try:
            dest.mkdir(parents=True, exist_ok=True)
            probe = dest / ".writable"
            probe.write_text("", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return dest
        except OSError as exc:
            last = exc
    raise last or PermissionError("no writable crm-bot data dir")


def existing_data_dir() -> Path:
    for dest in data_dir_candidates():
        if dest.is_dir():
            return dest
    return data_dir_candidates()[0]


def profile_path() -> Path:
    for dest in data_dir_candidates():
        path = dest / "profile.yaml"
        if path.is_file() and path.stat().st_size > 0:
            return path
    return data_dir_candidates()[0] / "profile.yaml"


def admin_candidates() -> list[Path]:
    paths = [dest / ".odoo-admin" for dest in data_dir_candidates()]
    extra = home() / ".hermes" / "data" / "odoo-website" / ".odoo-admin"
    sibling = home() / ".hermes" / "odoo-website" / ".odoo-admin"
    for path in (extra, sibling):
        if path not in paths:
            paths.append(path)
    return paths


def _parse_simple_yaml(path: Path) -> dict:
    if not path.is_file() or not path.stat().st_size:
        return {}
    out: dict = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def website_profile_path() -> Path | None:
    root = home() / ".hermes"
    for dest in (root / "data" / "odoo-website", root / "odoo-website"):
        path = dest / "profile.yaml"
        if path.is_file() and path.stat().st_size:
            return path
    return None


def _admin_login_and_file() -> tuple[str, bool]:
    """Return ``(login, file_present)``. Never the password.

    ``login`` is set only when it contains ``@``. A default ``admin``
    login is not the owner email. ``file_present`` is true when a
    sibling or CrmBot ``.odoo-admin`` holds both login and password.
    """
    for path in admin_candidates():
        if not path.is_file() or not path.stat().st_size:
            continue
        login = password = ""
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("login="):
                login = line.split("=", 1)[1].strip()
            elif line.startswith("password="):
                password = line.split("=", 1)[1].strip()
        if login and password:
            email = login if "@" in login else ""
            return email, True
    return "", False


def implicit_setup() -> dict:
    """Fields already on the box. Never a password.

    Shared contract: odoo-community ``references/setup.md``.
    WebsiteBot writes ``owner_email`` + ``language`` in its
    ``profile.yaml`` and the login password in ``.odoo-admin``.
    Event name is CrmBot-only.
    """
    crm = _parse_simple_yaml(profile_path())
    sibling = website_profile_path()
    website = _parse_simple_yaml(sibling) if sibling else {}
    admin_email, admin_file = _admin_login_and_file()
    email = (crm.get("owner_email") or "").strip()
    if "@" not in email:
        email = admin_email
    if "@" not in email:
        email = (website.get("owner_email") or "").strip()
        if "@" not in email:
            email = ""
    language = (crm.get("language") or "").strip() or (
        website.get("language") or ""
    ).strip()
    return {
        "event_name": (crm.get("event_name") or "").strip(),
        "owner_email": email,
        "language": language,
        "admin_file": admin_file,
    }
