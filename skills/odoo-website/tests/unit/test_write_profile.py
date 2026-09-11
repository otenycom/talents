"""WebsiteBot write_profile must land the file or fail loudly."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "write_profile.py"


def _load():
    spec = importlib.util.spec_from_file_location("ow_write_profile_under_test", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_write_profile_creates_yaml(tmp_path, monkeypatch):
    dest = tmp_path / "odoo-website"
    monkeypatch.setenv("ODOO_WEBSITE_DATA_DIR", str(dest))
    path = _load().write_profile(
        site_name="Bella", site_purpose="menu", site_slug="bella",
        owner_email="a@b.c", language="nl",
    )
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "site_name: Bella" in text
    assert "owner_email: a@b.c" in text


def test_write_profile_refuses_bad_email(tmp_path, monkeypatch):
    monkeypatch.setenv("ODOO_WEBSITE_DATA_DIR", str(tmp_path / "odoo-website"))
    with pytest.raises(ValueError, match="owner_email"):
        _load().write_profile(owner_email="nope")
