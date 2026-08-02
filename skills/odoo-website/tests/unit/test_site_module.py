"""site_module.py — scaffold + homepage XML (offline, no Odoo)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "site_module.py"


def _load():
    spec = importlib.util.spec_from_file_location("site_module_under_test", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def mod(tmp_path, monkeypatch):
    monkeypatch.setenv("HH_HOME", str(tmp_path))
    monkeypatch.setenv("ODOO_WEBSITE_DATA_DIR", str(tmp_path / ".hermes/data/odoo-website"))
    data = tmp_path / ".hermes/data/odoo-website"
    data.mkdir(parents=True)
    (data / "profile.yaml").write_text(
        "site_name: Moon Skydive Club\n"
        "site_purpose: funny jumps\n"
        "site_slug: moondive\n"
        "owner_email: pilot@example.com\n"
        "language: en\n"
        "odoo_locus: local\n"
        "build_backend: module\n",
        encoding="utf-8",
    )
    return _load()


def test_module_name(mod):
    assert mod.module_name("moondive") == "oteny_site_moondive"
    assert mod.module_name("moon-dive") == "oteny_site_moon_dive"


def test_init_scaffolds_git_and_files(mod, tmp_path):
    assert mod.cmd_init(type("A", (), {"slug": "moondive", "name": "Moon Skydive Club",
                                       "force": False})()) == 0
    root = tmp_path / "odoo-site/addons/oteny_site_moondive"
    assert (root / "__manifest__.py").exists()
    assert (root / "data/website_homepage.xml").exists()
    assert (root / "static/src/scss/site.scss").exists()
    assert (root / "hooks.py").exists()
    assert (root / ".git").is_dir()
    xml = (root / "data/website_homepage.xml").read_text(encoding="utf-8")
    assert "Moon Skydive Club" in xml
    assert "oteny_site_moondive.homepage" in xml


def test_set_homepage_rewrites_xml(mod, tmp_path, monkeypatch):
    mod.cmd_init(type("A", (), {"slug": "moondive", "name": "Moon", "force": False})())
    # Do not run real odoo -u — stub _upgrade
    monkeypatch.setattr(mod, "_upgrade", lambda slug: 0)
    rc = mod.cmd_set_homepage(type("A", (), {
        "slug": "moondive",
        "title": "Moon Skydive Club",
        "body_html": "<p>Jump from Starship. Land on the Moon. Bring snacks.</p>",
    })())
    assert rc == 0
    xml = (tmp_path / "odoo-site/addons/oteny_site_moondive/data/website_homepage.xml"
           ).read_text(encoding="utf-8")
    assert "Moon Skydive Club" in xml
    assert "Bring snacks" in xml


def test_docs_mention_upgrade_max_command():
    root = Path(__file__).resolve().parents[2]
    first = (root / "references/first-run.md").read_text(encoding="utf-8")
    skill = (root / "SKILL.md").read_text(encoding="utf-8")
    assert "/oteny_subscribe upgrade max" in first
    assert "/oteny_subscribe upgrade max" in skill
