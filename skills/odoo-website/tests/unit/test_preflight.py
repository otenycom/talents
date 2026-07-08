"""Unit tests for WebsiteBot's preflight.py — the per-turn readiness probe (never delivered).

Deterministic + offline: given a fake home, READY is `no` until BOTH the Odoo install marker
and a complete profile.yaml exist, and the parseable block is well-formed. Run:

    python3 -m pytest skills/odoo-website/tests/unit/ -q
"""
import importlib.util
import os
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "preflight.py"


def _load():
    spec = importlib.util.spec_from_file_location("odoo_website_preflight", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fake_home(tmp_path, *, installed=False, profile=None):
    home = tmp_path / "home"
    (home / ".hermes" / "data" / "odoo-website").mkdir(parents=True, exist_ok=True)
    if installed:
        base = home / "odoo-site"
        (base / "odoo" / "odoo").mkdir(parents=True, exist_ok=True)
        (base / ".deps-installed").write_text("", encoding="utf-8")
    if profile is not None:
        lines = [f'{k}: "{v}"' for k, v in profile.items()]
        (home / ".hermes" / "data" / "odoo-website" / "profile.yaml").write_text(
            "\n".join(lines), encoding="utf-8")
    return home


_FULL_PROFILE = {"site_name": "Cafe", "site_purpose": "menu", "site_slug": "cafe",
                 "owner_email": "a@b.com", "language": "en"}


def test_ready_no_when_nothing_set(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HH_HOME", str(_fake_home(tmp_path)))
    _load().main()
    out = capsys.readouterr().out
    assert "READY: no" in out
    assert "odoo_install" in out


def test_ready_no_when_installed_but_profile_incomplete(tmp_path, monkeypatch, capsys):
    home = _fake_home(tmp_path, installed=True, profile={"site_name": "Cafe"})
    monkeypatch.setenv("HH_HOME", str(home))
    _load().main()
    out = capsys.readouterr().out
    assert "READY: no" in out
    assert "profile:" in out                       # names the unset fields


def test_ready_yes_when_installed_and_profile_complete(tmp_path, monkeypatch, capsys):
    home = _fake_home(tmp_path, installed=True, profile=_FULL_PROFILE)
    monkeypatch.setenv("HH_HOME", str(home))
    rc = _load().main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "READY: yes" in out
    assert "site_slug=cafe" in out
    assert "MISSING" not in out


def test_exit_code_always_zero(tmp_path, monkeypatch):
    monkeypatch.setenv("HH_HOME", str(_fake_home(tmp_path)))
    assert _load().main() == 0            # readiness is in the output, never the exit code
