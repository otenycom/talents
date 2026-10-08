"""Writable CrmBot data dir.

``~/.hermes/data`` can be root-owned on a fresh box (host mkdir as root).
Hermes then cannot create ``data/crm-bot``. Prefer the canonical
``~/.hermes/data/crm-bot`` path. When that parent is not writable, use
``~/.hermes/crm-bot`` (the home folder is already the sandbox user's).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_BOT = "crm-bot"
_ENV = "CRM_BOT_DATA_DIR"


def _find_community_scripts() -> Path:
    """Locate odoo-community's ``scripts/`` dir: env var → catalog sibling
    (this checkout) → box path (``HH_HOME`` when set). See
    odoo-community's ``local_odoo_rpc.py`` for the shared client this
    unlocks. Raises when community was never delivered."""
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


def community_paths():
    """odoo-community's ``local_odoo_paths`` module. Lazy import — a caller
    that only wants ``profile_path()`` / ``writable_data_dir()`` does not
    fail just because community was not delivered to this box. That module
    owns ``normalize_login()`` and ``admin_login_and_file()``."""
    scripts = _find_community_scripts()
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    import local_odoo_paths
    return local_odoo_paths


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


def normalize_login(raw) -> str:
    """odoo-community's one login rule (strip + lowercase)."""
    return community_paths().normalize_login(raw)


def admin_candidates() -> list[Path]:
    """Own candidates first (honors ``CRM_BOT_DATA_DIR``), then whatever the
    community-wide fallback (crm-bot, odoo-website, odoo-community) adds that
    is not already covered — the same rule WebsiteBot's ``admin_candidates()``
    now uses the other way."""
    paths = [dest / ".odoo-admin" for dest in data_dir_candidates()]
    for path in community_paths().admin_candidates():
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


def implicit_setup() -> dict:
    """Fields already on the box. Never a password.

    Shared contract: odoo-community ``references/setup.md``.
    WebsiteBot writes ``owner_email`` + ``language`` + ``site_slug`` in
    its ``profile.yaml`` and the login password in ``.odoo-admin``.
    Event name is CrmBot-only. ``admin_file`` is one of ``"owner_set"``,
    ``"bake_placeholder"``, ``"key_only"``, or ``"missing"`` — see
    odoo-community ``local_odoo_paths.admin_login_and_file``.
    """
    crm = _parse_simple_yaml(profile_path())
    sibling = website_profile_path()
    website = _parse_simple_yaml(sibling) if sibling else {}
    admin_email, admin_file = community_paths().admin_login_and_file(
        admin_candidates(),
    )
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
    site_slug = (crm.get("site_slug") or "").strip() or (
        website.get("site_slug") or ""
    ).strip()
    return {
        "event_name": (crm.get("event_name") or "").strip(),
        "owner_email": email,
        "language": language,
        "admin_file": admin_file,
        "site_slug": site_slug,
    }
