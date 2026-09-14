"""write_profile must land the file, and must not claim success when mkdir fails."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
_SCRIPT = _SCRIPTS / "write_profile.py"


def _load():
    spec = importlib.util.spec_from_file_location("crm_write_profile_under_test", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _load_paths():
    spec = importlib.util.spec_from_file_location(
        "crm_paths_under_test", _SCRIPTS / "crm_paths.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_write_profile_creates_yaml_under_data_dir(tmp_path, monkeypatch):
    dest = tmp_path / "crm-bot"
    monkeypatch.setenv("CRM_BOT_DATA_DIR", str(dest))
    path = _load().write_profile(
        event_name="OXP", owner_email="ries@vriend.com", language="nl",
    )
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "event_name: OXP" in text
    assert "owner_email: ries@vriend.com" in text
    assert "language: nl" in text


def test_write_profile_refuses_bad_email(tmp_path, monkeypatch):
    monkeypatch.setenv("CRM_BOT_DATA_DIR", str(tmp_path / "crm-bot"))
    with pytest.raises(ValueError, match="owner_email"):
        _load().write_profile(event_name="OXP", owner_email="not-an-email")


def test_write_profile_cli_reports_permission_denied(tmp_path, monkeypatch, capsys):
    parent = tmp_path / "data"
    parent.mkdir()
    parent.chmod(0o555)
    monkeypatch.setenv("CRM_BOT_DATA_DIR", str(parent / "crm-bot"))
    monkeypatch.setattr("sys.argv", [
        "write_profile.py", "--event-name", "OXP",
        "--owner-email", "ries@vriend.com", "--language", "nl",
    ])
    try:
        rc = _load().main()
    finally:
        parent.chmod(0o755)
    assert rc == 1
    err = capsys.readouterr().err
    assert "PROFILE_WRITE_FAILED permission_denied" in err


def assert_sandbox_profile(ctx):
    """Scenario hook: the sandbox data dir holds the booth profile."""
    path = Path(ctx["data_dir"]) / "profile.yaml"
    assert path.is_file(), f"missing {path}"
    text = path.read_text(encoding="utf-8")
    assert "event_name: OXP" in text
    assert "owner_email: ries@vriend.com" in text
    assert "language: nl" in text


def test_write_profile_falls_back_beside_hermes_when_data_not_writable(
    tmp_path, monkeypatch,
):
    hermes = tmp_path / ".hermes"
    data = hermes / "data"
    data.mkdir(parents=True)
    data.chmod(0o555)
    monkeypatch.delenv("CRM_BOT_DATA_DIR", raising=False)
    monkeypatch.setenv("HH_HOME", str(tmp_path))
    try:
        path = _load().write_profile(
            event_name="OXP", owner_email="ries@vriend.com", language="nl",
        )
    finally:
        data.chmod(0o755)
    assert path == hermes / "crm-bot" / "profile.yaml"
    assert path.is_file()
    assert "event_name: OXP" in path.read_text(encoding="utf-8")


def test_preflight_sees_sibling_profile(tmp_path, monkeypatch, capsys):
    dest = tmp_path / ".hermes" / "crm-bot"
    dest.mkdir(parents=True)
    (dest / "profile.yaml").write_text(
        "event_name: OXP\nowner_email: a@b.c\nlanguage: nl\n", encoding="utf-8",
    )
    monkeypatch.delenv("CRM_BOT_DATA_DIR", raising=False)
    monkeypatch.setenv("HH_HOME", str(tmp_path))
    spec = importlib.util.spec_from_file_location(
        "crm_preflight_sibling",
        Path(__file__).resolve().parents[2] / "scripts" / "preflight.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    assert mod.main() == 0
    assert "PROFILE: present" in capsys.readouterr().out


def test_preflight_prints_profile_missing_without_yaml(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HH_HOME", str(tmp_path))
    spec = importlib.util.spec_from_file_location(
        "crm_preflight_under_test",
        Path(__file__).resolve().parents[2] / "scripts" / "preflight.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    assert mod.main() == 0
    out = capsys.readouterr().out
    assert "PROFILE: missing" in out
    assert "EVENT: -" in out
    assert "ADMIN: -" in out
    assert "LANGUAGE: -" in out
    assert "ADMIN_FILE: missing" in out
    assert "CRM: unknown" in out
    assert "CRM_HOME: -" in out
    assert "password=" not in out.lower()


def test_preflight_prints_sibling_website_admin_and_language(
    tmp_path, monkeypatch, capsys,
):
    hermes = tmp_path / ".hermes"
    website = hermes / "data" / "odoo-website"
    website.mkdir(parents=True)
    (website / "profile.yaml").write_text(
        "owner_email: ries@vriend.com\nlanguage: nl\n", encoding="utf-8",
    )
    (website / ".odoo-admin").write_text(
        "login=ries@vriend.com\npassword=secret-from-website\napi_key=k\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("CRM_BOT_DATA_DIR", raising=False)
    monkeypatch.setenv("HH_HOME", str(tmp_path))
    spec = importlib.util.spec_from_file_location(
        "crm_preflight_warm",
        Path(__file__).resolve().parents[2] / "scripts" / "preflight.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    assert mod.main() == 0
    out = capsys.readouterr().out
    assert "ADMIN: ries@vriend.com" in out
    assert "LANGUAGE: nl" in out
    assert "ADMIN_FILE: owner_set" in out
    assert "EVENT: -" in out
    assert "secret-from-website" not in out


def test_preflight_prints_bake_placeholder_not_owner_set(
    tmp_path, monkeypatch, capsys,
):
    """A mint-time clone-secret rotation (``login=admin``) is never the owner's
    password — CrmBot must never report ``ADMIN_FILE: owner_set`` for it."""
    hermes = tmp_path / ".hermes"
    website = hermes / "data" / "odoo-website"
    website.mkdir(parents=True)
    (website / ".odoo-admin").write_text(
        "login=admin\npassword=mint-rotated-secret\napi_key=k\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("CRM_BOT_DATA_DIR", raising=False)
    monkeypatch.setenv("HH_HOME", str(tmp_path))
    spec = importlib.util.spec_from_file_location(
        "crm_preflight_bake_placeholder",
        Path(__file__).resolve().parents[2] / "scripts" / "preflight.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    assert mod.main() == 0
    out = capsys.readouterr().out
    assert "ADMIN_FILE: bake_placeholder" in out
    assert "ADMIN: -" in out
    assert "mint-rotated-secret" not in out


def test_write_profile_copies_sibling_email_when_flag_omitted(tmp_path, monkeypatch):
    hermes = tmp_path / ".hermes"
    website = hermes / "data" / "odoo-website"
    website.mkdir(parents=True)
    (website / "profile.yaml").write_text(
        "owner_email: ries@vriend.com\nlanguage: nl\n", encoding="utf-8",
    )
    dest = hermes / "data" / "crm-bot"
    monkeypatch.delenv("CRM_BOT_DATA_DIR", raising=False)
    monkeypatch.setenv("HH_HOME", str(tmp_path))
    path = _load().write_profile(event_name="OXP")
    assert path == dest / "profile.yaml"
    text = path.read_text(encoding="utf-8")
    assert "event_name: OXP" in text
    assert "owner_email: ries@vriend.com" in text
    assert "language: nl" in text


def test_implicit_setup_ignores_default_admin_login(tmp_path, monkeypatch):
    """A ``login=admin`` file is the mint-time clone-secret rotation, never a
    password the owner has seen — it must report ``bake_placeholder``, not the
    old ``admin_file is True`` that let a warm box skip the secure intake."""
    dest = tmp_path / ".hermes" / "crm-bot"
    dest.mkdir(parents=True)
    (dest / ".odoo-admin").write_text(
        "login=admin\npassword=admin\napi_key=k\n", encoding="utf-8",
    )
    monkeypatch.delenv("CRM_BOT_DATA_DIR", raising=False)
    monkeypatch.setenv("HH_HOME", str(tmp_path))
    implied = _load_paths().implicit_setup()
    assert implied["owner_email"] == ""
    assert implied["admin_file"] == "bake_placeholder"


def test_write_profile_stores_site_slug(tmp_path, monkeypatch):
    dest = tmp_path / "crm-bot"
    monkeypatch.setenv("CRM_BOT_DATA_DIR", str(dest))
    path = _load().write_profile(
        event_name="OXP", owner_email="ries@vriend.com", language="nl",
        site_slug="ries-cafe",
    )
    assert "site_slug: ries-cafe" in path.read_text(encoding="utf-8")


def test_write_profile_copies_sibling_site_slug_when_flag_omitted(
    tmp_path, monkeypatch,
):
    """A prior WebsiteBot cold install already claimed a name — CrmBot must
    reuse it, not silently default to the tenant ref, when the owner's own
    profile does not have one yet."""
    hermes = tmp_path / ".hermes"
    website = hermes / "data" / "odoo-website"
    website.mkdir(parents=True)
    (website / "profile.yaml").write_text(
        "owner_email: ries@vriend.com\nlanguage: nl\nsite_slug: ries-cafe\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("CRM_BOT_DATA_DIR", raising=False)
    monkeypatch.setenv("HH_HOME", str(tmp_path))
    path = _load().write_profile(event_name="OXP")
    assert "site_slug: ries-cafe" in path.read_text(encoding="utf-8")


def test_implicit_setup_reads_own_site_slug(tmp_path, monkeypatch):
    dest = tmp_path / ".hermes" / "crm-bot"
    dest.mkdir(parents=True)
    (dest / "profile.yaml").write_text("site_slug: ries-cafe\n", encoding="utf-8")
    monkeypatch.delenv("CRM_BOT_DATA_DIR", raising=False)
    monkeypatch.setenv("HH_HOME", str(tmp_path))
    assert _load_paths().implicit_setup()["site_slug"] == "ries-cafe"


def test_implicit_setup_falls_back_to_sibling_site_slug(tmp_path, monkeypatch):
    hermes = tmp_path / ".hermes"
    website = hermes / "data" / "odoo-website"
    website.mkdir(parents=True)
    (website / "profile.yaml").write_text(
        "owner_email: ries@vriend.com\nsite_slug: ries-cafe\n", encoding="utf-8",
    )
    monkeypatch.delenv("CRM_BOT_DATA_DIR", raising=False)
    monkeypatch.setenv("HH_HOME", str(tmp_path))
    assert _load_paths().implicit_setup()["site_slug"] == "ries-cafe"


def test_preflight_prints_site_name_when_known(tmp_path, monkeypatch, capsys):
    dest = tmp_path / ".hermes" / "crm-bot"
    dest.mkdir(parents=True)
    (dest / "profile.yaml").write_text("site_slug: ries-cafe\n", encoding="utf-8")
    monkeypatch.delenv("CRM_BOT_DATA_DIR", raising=False)
    monkeypatch.setenv("HH_HOME", str(tmp_path))
    spec = importlib.util.spec_from_file_location(
        "crm_preflight_site_name",
        Path(__file__).resolve().parents[2] / "scripts" / "preflight.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    assert mod.main() == 0
    assert "SITE_NAME: ries-cafe" in capsys.readouterr().out


def test_preflight_prints_site_name_dash_when_unknown(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HH_HOME", str(tmp_path))
    spec = importlib.util.spec_from_file_location(
        "crm_preflight_no_site_name",
        Path(__file__).resolve().parents[2] / "scripts" / "preflight.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    assert mod.main() == 0
    assert "SITE_NAME: -" in capsys.readouterr().out


class _FakeRpc:
    def __init__(self, xmlids):
        self.xmlids = xmlids

    def call(self, model, method, args=None, kwargs=None):
        args = list(args or [])
        if model == "ir.model.data" and method == "search_read":
            domain = args[0]
            module = next(v for k, _, v in domain if k == "module")
            name = next(v for k, _, v in domain if k == "name")
            xmlid = f"{module}.{name}"
            if xmlid not in self.xmlids:
                return []
            return [{"res_id": self.xmlids[xmlid][0]}]
        if model == "ir.ui.menu" and method == "read":
            mid = args[0][0]
            for _xmlid, (rid, seq) in self.xmlids.items():
                if rid == mid:
                    return [{"id": mid, "sequence": seq}]
            return []
        raise AssertionError((model, method))


def test_crm_home_state_is_discuss_when_crm_sequence_is_higher():
    spec = importlib.util.spec_from_file_location(
        "crm_preflight_home_discuss",
        Path(__file__).resolve().parents[2] / "scripts" / "preflight.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    rpc = _FakeRpc({
        "crm.crm_menu_root": (10, 25),
        "mail.menu_root_discuss": (11, 5),
    })
    assert mod.crm_home_state(rpc) == "discuss"


def test_crm_home_state_is_first_after_pin():
    spec = importlib.util.spec_from_file_location(
        "crm_preflight_home_first",
        Path(__file__).resolve().parents[2] / "scripts" / "preflight.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    rpc = _FakeRpc({
        "crm.crm_menu_root": (10, 1),
        "mail.menu_root_discuss": (11, 5),
    })
    assert mod.crm_home_state(rpc) == "first"
