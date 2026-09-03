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
    # Odoo looks up post_init_hook on the addon package — must re-export from hooks.
    init_py = (root / "__init__.py").read_text(encoding="utf-8")
    assert "from .hooks import post_init_hook" in init_py
    assert "from . import hooks" not in init_py
    manifest = (root / "__manifest__.py").read_text(encoding="utf-8")
    assert '"post_init_hook": "post_init_hook"' in manifest
    xml = (root / "data/website_homepage.xml").read_text(encoding="utf-8")
    assert "Moon Skydive Club" in xml
    assert "oteny_site_moondive.homepage" in xml
    assert "/oteny-home" in xml
    hooks = (root / "hooks.py").read_text(encoding="utf-8")
    assert "homepage_url" in hooks
    assert "homepage_id" not in hooks
    # Prove the package namespace actually binds the hook (not just submodule import).
    import sys
    import types
    pkg_name = "oteny_site_moondive_testpkg"
    pkg = types.ModuleType(pkg_name)
    pkg.__path__ = [str(root)]  # type: ignore[attr-defined]
    sys.modules[pkg_name] = pkg
    hooks_mod = types.ModuleType(f"{pkg_name}.hooks")
    exec(compile(hooks, f"{pkg_name}.hooks", "exec"), hooks_mod.__dict__)
    sys.modules[f"{pkg_name}.hooks"] = hooks_mod
    exec(compile(init_py, f"{pkg_name}", "exec"), pkg.__dict__)
    assert callable(pkg.post_init_hook)
    del sys.modules[pkg_name]
    del sys.modules[f"{pkg_name}.hooks"]


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


def test_docs_give_the_exact_upgrade_command():
    """An owner cannot act on "get a bigger plan" — the docs must carry the literal command
    the bot tells them to send. Power, not Max: the site runs on a container now."""
    root = Path(__file__).resolve().parents[2]
    first = (root / "references/first-run.md").read_text(encoding="utf-8")
    skill = (root / "SKILL.md").read_text(encoding="utf-8")
    assert "/oteny_subscribe upgrade power" in first
    assert "/oteny_subscribe upgrade power" in skill


def test_git_helper_ignores_an_inherited_git_dir(mod, tmp_path, monkeypatch):
    """A hook run inside a linked worktree exports GIT_DIR; the scaffold's nested git
    must still act on its own cwd, never on the repo that ran the hook."""
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "not-a-repo"))
    monkeypatch.setenv("GIT_WORK_TREE", str(tmp_path / "not-a-tree"))
    repo = tmp_path / "scaffold"
    repo.mkdir()
    mod._git(repo, "init", "-q")
    assert (repo / ".git").is_dir()
    assert not (tmp_path / "not-a-repo").exists()
