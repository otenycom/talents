"""setup_admin talks to the local cluster the installers already chose."""
from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "setup_admin.py"


def _load():
    spec = importlib.util.spec_from_file_location("crm_setup_admin_under_test", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_db_cli_args_uses_tcp_when_postgres_prefix_exists(tmp_path):
    (tmp_path / "postgres" / "data").mkdir(parents=True)
    args = _load()._db_cli_args(tmp_path)
    assert "--db_host=127.0.0.1" in args
    assert not any("pgdata" in a for a in args)


def test_db_cli_args_keeps_legacy_socket_when_only_pgdata(tmp_path):
    args = _load()._db_cli_args(tmp_path)
    assert f"--db_host={tmp_path / 'odoo-site' / 'pgdata'}" in args
    assert "--db_host=127.0.0.1" not in args
