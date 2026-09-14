"""Writable WebsiteBot data dir.

``~/.hermes/data`` can be root-owned on a fresh box. Prefer
``~/.hermes/data/odoo-website``. When that parent is not writable, use
``~/.hermes/odoo-website``.
"""
from __future__ import annotations

import os
from pathlib import Path

_BOT = "odoo-website"
_ENV = "ODOO_WEBSITE_DATA_DIR"


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
    raise last or PermissionError("no writable odoo-website data dir")


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
    return [dest / ".odoo-admin" for dest in data_dir_candidates()]


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


def crm_bot_profile_path() -> Path | None:
    """CrmBot's sibling ``profile.yaml``, if this box has one.

    Mirrors CrmBot's own ``crm_paths.website_profile_path`` in reverse — a
    box where CrmBot ran the cold install first already has an owner email,
    language, and site name WebsiteBot must not re-ask for.
    """
    root = home() / ".hermes"
    for dest in (root / "data" / "crm-bot", root / "crm-bot"):
        path = dest / "profile.yaml"
        if path.is_file() and path.stat().st_size:
            return path
    return None


def sibling_site_slug() -> str:
    """CrmBot's already-claimed site name, or ``""`` when none is known."""
    path = crm_bot_profile_path()
    if not path:
        return ""
    return (_parse_simple_yaml(path).get("site_slug") or "").strip()


def admin_login_and_file() -> tuple[str, str]:
    """Return ``(login, admin_file_state)``. Never the password.

    Mirrors CrmBot's ``crm_paths._admin_login_and_file``. ``admin_file_state``
    is one of:

    - ``"owner_set"`` — a stored ``login`` is a real email. The owner (or a
      prior ``setup_admin.py`` run on their behalf) put it there.
    - ``"bake_placeholder"`` — a ``.odoo-admin`` holds a login and password,
      but the login is not an email. The mint-time clone-secret rotation
      always writes ``login=admin``, never a password the owner has seen.
      Treat it exactly like ``"missing"`` for every "has the owner set up"
      decision.
    - ``"missing"`` — no candidate file parses at all.

    ``login`` (the return value's first element) is set only for
    ``"owner_set"``; a default ``admin`` login is never the owner email.
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
            if "@" in login:
                return login, "owner_set"
            return "", "bake_placeholder"
    return "", "missing"
