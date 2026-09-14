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


def test_reports_substrate_tier_and_mem_from_injected_env(tmp_path, monkeypatch, capsys):
    # The deployer injects the envelope; preflight surfaces it so the persona + install_odoo.sh
    # can refuse an under-provisioned box and tell the owner to upgrade to Max (§14.2).
    monkeypatch.setenv("HH_HOME", str(_fake_home(tmp_path)))
    monkeypatch.setenv("OTENY_SUBSTRATE", "vm")
    monkeypatch.setenv("OTENY_TIER", "max")
    monkeypatch.setenv("OTENY_MEM_GB", "8")
    _load().main()
    out = capsys.readouterr().out
    assert "SUBSTRATE: vm" in out
    assert "TIER: max" in out
    assert "MEM_GB: 8.0" in out


def test_substrate_unknown_without_a_signal(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HH_HOME", str(_fake_home(tmp_path)))
    monkeypatch.delenv("OTENY_SUBSTRATE", raising=False)
    _load().main()
    assert "SUBSTRATE: unknown" in capsys.readouterr().out


def test_admin_file_owner_set_when_login_is_a_real_email(tmp_path, monkeypatch, capsys):
    home = _fake_home(tmp_path, profile={"owner_email": "ries@vriend.com"})
    (home / ".hermes" / "data" / "odoo-website" / ".odoo-admin").write_text(
        "login=ries@vriend.com\npassword=s3cret\napi_key=k\n", encoding="utf-8",
    )
    monkeypatch.setenv("HH_HOME", str(home))
    _load().main()
    out = capsys.readouterr().out
    assert "ADMIN: ries@vriend.com" in out
    assert "ADMIN_FILE: owner_set" in out
    assert "s3cret" not in out


def test_admin_file_bake_placeholder_not_owner_set(tmp_path, monkeypatch, capsys):
    """Every prewarmed box ships a ``.odoo-admin`` with ``login=admin`` from the
    mint-time clone-secret rotation. That is never a password the owner has
    seen, so it must report ``bake_placeholder``, not ``owner_set``."""
    home = _fake_home(tmp_path)
    (home / ".hermes" / "data" / "odoo-website" / ".odoo-admin").write_text(
        "login=admin\npassword=mint-rotated-secret\napi_key=k\n", encoding="utf-8",
    )
    monkeypatch.setenv("HH_HOME", str(home))
    _load().main()
    out = capsys.readouterr().out
    assert "ADMIN: -" in out
    assert "ADMIN_FILE: bake_placeholder" in out
    assert "mint-rotated-secret" not in out


def test_admin_file_missing_without_any_odoo_admin(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HH_HOME", str(_fake_home(tmp_path)))
    _load().main()
    assert "ADMIN_FILE: missing" in capsys.readouterr().out


def test_site_slug_reuses_sibling_crm_bot_claim(tmp_path, monkeypatch, capsys):
    """A CrmBot cold install on this box already claimed a site name — WebsiteBot
    must reuse it (READY, not blocked on its own missing site_slug), never
    re-ask and never silently fall back to the tenant ref."""
    profile = {k: v for k, v in _FULL_PROFILE.items() if k != "site_slug"}
    home = _fake_home(tmp_path, installed=True, profile=profile)
    crm = home / ".hermes" / "data" / "crm-bot"
    crm.mkdir(parents=True)
    (crm / "profile.yaml").write_text("site_slug: ries-cafe\n", encoding="utf-8")
    monkeypatch.setenv("HH_HOME", str(home))
    rc = _load().main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "READY: yes" in out
    assert "site_slug=ries-cafe" in out
    assert "MISSING" not in out


def test_site_slug_missing_without_own_or_sibling_claim(tmp_path, monkeypatch, capsys):
    profile = {k: v for k, v in _FULL_PROFILE.items() if k != "site_slug"}
    home = _fake_home(tmp_path, installed=True, profile=profile)
    monkeypatch.setenv("HH_HOME", str(home))
    _load().main()
    out = capsys.readouterr().out
    assert "READY: no" in out
    assert "site_slug" in out
    assert "site_slug=-" in out
