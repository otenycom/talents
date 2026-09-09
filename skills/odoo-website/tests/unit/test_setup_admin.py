"""setup_admin.py — stored-file helpers + missing profile (offline; no live Odoo)."""
from __future__ import annotations

import importlib.util
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


def test_db_cli_args_uses_tcp_when_postgres_prefix_exists(tmp_path):
    (tmp_path / "postgres" / "data").mkdir(parents=True)
    args = _load()._db_cli_args(tmp_path)
    assert "--db_host=127.0.0.1" in args
    assert not any("pgdata" in a for a in args)


def test_db_cli_args_keeps_legacy_socket_when_only_pgdata(tmp_path):
    args = _load()._db_cli_args(tmp_path)
    assert f"--db_host={tmp_path / 'odoo-site' / 'pgdata'}" in args
    assert "--db_host=127.0.0.1" not in args
