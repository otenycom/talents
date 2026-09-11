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
