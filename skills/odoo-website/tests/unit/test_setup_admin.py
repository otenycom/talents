"""setup_admin.py — stored-file helpers + missing profile (offline; no live Odoo)."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "setup_admin.py"


def _load():
    spec = importlib.util.spec_from_file_location("setup_admin_under_test", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HH_HOME", str(tmp_path))
    monkeypatch.delenv("ODOO_WEBSITE_DATA_DIR", raising=False)
    data = tmp_path / ".hermes" / "data" / "odoo-website"
    data.mkdir(parents=True)
    return tmp_path, data


def test_refuses_without_owner_email(home, monkeypatch):
    tmp_path, data = home
    (data / "profile.yaml").write_text("site_name: X\nowner_email: \n", encoding="utf-8")
    mod = _load()
    rc = mod.main([])
    assert rc == 1


def test_read_stored_falls_back_to_parent_bootstrap(home):
    tmp_path, _data = home
    (tmp_path / "odoo-site").mkdir()
    boot = tmp_path / "odoo-site" / ".odoo-admin"
    boot.write_text("login=admin\npassword=boot-pass\napi_key=bootkey\n", encoding="utf-8")
    os.chmod(boot, 0o600)
    mod = _load()
    assert mod._read_stored() == ("admin", "boot-pass", "bootkey")


def test_write_stored_keeps_bootstrap_when_hermes_dir_not_writable(home):
    tmp_path, data = home
    (tmp_path / "odoo-site").mkdir()
    boot = tmp_path / "odoo-site" / ".odoo-admin"
    boot.write_text("login=admin\npassword=old\napi_key=\n", encoding="utf-8")
    os.chmod(boot, 0o600)
    os.chmod(data, 0o500)
    mod = _load()
    mod._write_stored("admin", "new-pass", "newkey")
    assert mod._read_stored() == ("admin", "new-pass", "newkey")
    assert oct(boot.stat().st_mode & 0o777) == "0o600"
    os.chmod(data, 0o700)


def test_write_and_read_stored_roundtrip(home):
    tmp_path, data = home
    mod = _load()
    mod._write_stored("ries@example.com", "s3cret-pass", "deadbeefapikey")
    path = data / ".odoo-admin"
    assert path.exists()
    assert oct(path.stat().st_mode & 0o777) == "0o600"
    assert mod._read_stored() == ("ries@example.com", "s3cret-pass", "deadbeefapikey")
    assert path.read_text(encoding="utf-8").splitlines()[2] == "api_key=deadbeefapikey"


def test_gen_password_length_and_charset():
    mod = _load()
    p = mod._gen_password(32)
    assert len(p) == 32
    assert p.isalnum()


def test_odoo_db_host_prefers_postgres_talent_cluster(home):
    tmp_path, _data = home
    (tmp_path / "postgres" / "data").mkdir(parents=True)
    (tmp_path / "odoo-site" / "pgdata").mkdir(parents=True)
    mod = _load()
    assert mod._odoo_db_host() == "127.0.0.1"


def test_write_odoo_conf_sets_proxy_mode_and_stays_0600(home):
    tmp_path, _data = home
    (tmp_path / "odoo-site").mkdir()
    mod = _load()
    mod._write_odoo_conf(admin_passwd="master-secret", proxy_mode=True)
    path = tmp_path / "odoo-site" / "odoo.conf"
    text = path.read_text(encoding="utf-8")
    assert "admin_passwd = master-secret" in text
    assert "proxy_mode = True" in text
    assert oct(path.stat().st_mode & 0o777) == "0o600"


def test_rotate_clone_secrets_skips_ready_short_circuit(home, monkeypatch):
    """A cloned 0600 file must not skip the rotate."""
    tmp_path, data = home
    (data / "profile.yaml").write_text("owner_email: ries@example.com\n", encoding="utf-8")
    mod = _load()
    mod._write_stored("ries@example.com", "old-pass", "deadbeefapikey")
    monkeypatch.setattr(mod, "_json2_bearer_ok", lambda _key: True)

    class _Boom(Exception):
        pass

    def _no_net(_url, timeout=10):
        raise _Boom("should still reach odoo_down after skipping the short circuit")

    monkeypatch.setattr(mod.urllib.request, "urlopen", _no_net)
    rc = mod.main(["--rotate-clone-secrets"])
    assert rc == 1
