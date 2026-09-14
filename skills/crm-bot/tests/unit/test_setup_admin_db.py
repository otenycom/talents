"""setup_admin talks to the local cluster the installers already chose."""
from __future__ import annotations

import importlib.util
import io
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


def test_refuses_to_invent_a_password_on_bake_placeholder(tmp_path, monkeypatch):
    """A mint-rotated ``login=admin`` file must never be silently reused to set
    the owner's real login without a --from-env/--password-file secret. This is
    the defense-in-depth backstop for the CrmBot/WebsiteBot bake-placeholder fix:
    the skill prose must always route through the secure link first, but the
    script itself must refuse rather than invent a password nobody has seen if
    that prose is ever bypassed."""
    monkeypatch.setenv("HH_HOME", str(tmp_path))
    monkeypatch.delenv("CRM_BOT_DATA_DIR", raising=False)
    data = tmp_path / ".hermes" / "data" / "crm-bot"
    data.mkdir(parents=True)
    (data / "profile.yaml").write_text(
        "owner_email: ries@vriend.com\n", encoding="utf-8",
    )
    website = tmp_path / ".hermes" / "data" / "odoo-website"
    website.mkdir(parents=True)
    (website / ".odoo-admin").write_text(
        "login=admin\npassword=mint-rotated-secret\napi_key=k\n", encoding="utf-8",
    )

    mod = _load()
    monkeypatch.setattr(mod.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(b""))
    monkeypatch.setattr(mod, "_session_authenticate", lambda opener, login, password: 2)

    rc = mod.main([])

    assert rc == 1
    assert mod._read_stored() == ("admin", "mint-rotated-secret", "k")
