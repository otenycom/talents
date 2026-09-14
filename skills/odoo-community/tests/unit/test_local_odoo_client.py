"""The shared JSON-2 client (§6a) and the local-odoo-client fallback (§6).

Covers: ``as_id`` unwrap/raise contract, ``admin_candidates`` cross-bot
sibling discovery (both directions), the consumer-side scripts-directory
locator order (env var → catalog sibling → box path), and the on-demand
fallback scripts (``crud.py`` confirm gate + create-unwrap, ``sql.py``
refusals, ``list_models.py`` against ``ir.model``).
"""
from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

_COMMUNITY_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
_CRM_SCRIPTS = Path(__file__).resolve().parents[3] / "crm-bot" / "scripts"
_WEBSITE_SCRIPTS = Path(__file__).resolve().parents[3] / "odoo-website" / "scripts"


def _load(scripts_dir: Path, name: str, modname: str):
    spec = importlib.util.spec_from_file_location(modname, scripts_dir / name)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _load_local_odoo_rpc():
    return _load(_COMMUNITY_SCRIPTS, "local_odoo_rpc.py", "local_odoo_rpc_under_test")


def _load_local_odoo_paths():
    return _load(_COMMUNITY_SCRIPTS, "local_odoo_paths.py", "local_odoo_paths_under_test")


def _load_crm_paths():
    return _load(_CRM_SCRIPTS, "crm_paths.py", "crm_paths_local_client_under_test")


def _load_website_paths():
    return _load(_WEBSITE_SCRIPTS, "website_paths.py", "website_paths_local_client_under_test")


# --------------------------------------------------------------------------
# as_id
# --------------------------------------------------------------------------


def test_as_id_unwraps_list_dict_and_int():
    mod = _load_local_odoo_rpc()
    assert mod.as_id([41]) == 41
    assert mod.as_id(41) == 41
    assert mod.as_id({"id": 41}) == 41


def test_as_id_raises_on_empty():
    mod = _load_local_odoo_rpc()
    with pytest.raises(RuntimeError, match="empty_id"):
        mod.as_id(None)
    with pytest.raises(RuntimeError, match="empty_id_list"):
        mod.as_id([])


# --------------------------------------------------------------------------
# OdooRPC construction — missing admin / missing key
# --------------------------------------------------------------------------


def test_missing_admin_raises_odoo_rpc_failed(tmp_path, monkeypatch):
    monkeypatch.setenv("HH_HOME", str(tmp_path))
    mod = _load_local_odoo_rpc()
    with pytest.raises(RuntimeError, match="no_admin"):
        mod.OdooRPC()


def test_missing_api_key_raises_odoo_rpc_failed(tmp_path, monkeypatch):
    data = tmp_path / ".hermes" / "data" / "odoo-community"
    data.mkdir(parents=True)
    (data / ".odoo-admin").write_text("login=a@b.c\npassword=x\n", encoding="utf-8")
    monkeypatch.setenv("HH_HOME", str(tmp_path))
    mod = _load_local_odoo_rpc()
    with pytest.raises(RuntimeError, match="no_api_key"):
        mod.OdooRPC()


# --------------------------------------------------------------------------
# admin_candidates — cross-bot sibling discovery, both directions
# --------------------------------------------------------------------------


def test_community_admin_candidates_lists_all_three_bots(tmp_path, monkeypatch):
    monkeypatch.setenv("HH_HOME", str(tmp_path))
    mod = _load_local_odoo_paths()
    candidates = mod.admin_candidates()
    names = {p.parent.name for p in candidates}
    assert names == {"crm-bot", "odoo-website", "odoo-community"}


def test_crmbot_admin_candidates_finds_websitebot_only_sibling(tmp_path, monkeypatch):
    """A box where only WebsiteBot ever minted ``.odoo-admin`` — CrmBot's own
    locator must still see that key through the community fallback."""
    website = tmp_path / ".hermes" / "data" / "odoo-website"
    website.mkdir(parents=True)
    (website / ".odoo-admin").write_text(
        "login=a@b.c\npassword=x\napi_key=k\n", encoding="utf-8",
    )
    monkeypatch.delenv("CRM_BOT_DATA_DIR", raising=False)
    monkeypatch.setenv("HH_HOME", str(tmp_path))
    mod = _load_crm_paths()
    found = [p for p in mod.admin_candidates() if p.is_file()]
    assert found == [website / ".odoo-admin"]


def test_websitebot_admin_candidates_finds_crmbot_only_sibling(tmp_path, monkeypatch):
    """The reverse of the above — before this rewrite WebsiteBot only ever
    saw its own admin file; it must now see a CrmBot-only sibling too."""
    crm = tmp_path / ".hermes" / "data" / "crm-bot"
    crm.mkdir(parents=True)
    (crm / ".odoo-admin").write_text(
        "login=a@b.c\npassword=x\napi_key=k\n", encoding="utf-8",
    )
    monkeypatch.delenv("ODOO_WEBSITE_DATA_DIR", raising=False)
    monkeypatch.setenv("HH_HOME", str(tmp_path))
    mod = _load_website_paths()
    found = [p for p in mod.admin_candidates() if p.is_file()]
    assert found == [crm / ".odoo-admin"]


# --------------------------------------------------------------------------
# consumer-side scripts-directory locator: env var -> catalog sibling -> box
# --------------------------------------------------------------------------


def test_find_community_scripts_prefers_env_var(tmp_path, monkeypatch):
    marker = tmp_path / "env-community-scripts"
    marker.mkdir()
    monkeypatch.setenv("ODOO_COMMUNITY_SCRIPTS", str(marker))
    mod = _load_crm_paths()
    assert mod._find_community_scripts() == marker


def test_find_community_scripts_falls_back_to_catalog_sibling(monkeypatch):
    monkeypatch.delenv("ODOO_COMMUNITY_SCRIPTS", raising=False)
    mod = _load_crm_paths()
    assert mod._find_community_scripts() == _COMMUNITY_SCRIPTS


def test_find_community_scripts_falls_back_to_box_path_when_catalog_missing(
    tmp_path, monkeypatch,
):
    monkeypatch.delenv("ODOO_COMMUNITY_SCRIPTS", raising=False)
    monkeypatch.setenv("HH_HOME", str(tmp_path))
    box = tmp_path / ".hermes" / "skills" / "talents" / "odoo-community" / "scripts"
    box.mkdir(parents=True)
    mod = _load_crm_paths()
    real_catalog_sibling = _COMMUNITY_SCRIPTS
    original_is_dir = Path.is_dir

    def fake_is_dir(self):
        if self == real_catalog_sibling:
            return False
        return original_is_dir(self)

    monkeypatch.setattr(Path, "is_dir", fake_is_dir)
    assert mod._find_community_scripts() == box


# --------------------------------------------------------------------------
# crud.py — confirm gate + create-unwrap
# --------------------------------------------------------------------------


def _admin_file(tmp_path) -> None:
    data = tmp_path / ".hermes" / "data" / "odoo-community"
    data.mkdir(parents=True)
    (data / ".odoo-admin").write_text(
        "login=a@b.c\npassword=x\napi_key=k\n", encoding="utf-8",
    )


def _load_crud(monkeypatch, tmp_path):
    monkeypatch.setenv("HH_HOME", str(tmp_path))
    _admin_file(tmp_path)
    return _load(_COMMUNITY_SCRIPTS, "crud.py", "crud_under_test")


def test_crud_create_without_confirm_reports_confirm_required(
    tmp_path, monkeypatch, capsys,
):
    mod = _load_crud(monkeypatch, tmp_path)
    monkeypatch.setattr(mod.OdooRPC, "_json2", lambda self, m, meth, **kw: {"uid": 7})
    monkeypatch.setattr(sys, "argv", ["crud.py", "create", "--model", "res.partner"])
    monkeypatch.setattr(sys, "stdin", io.StringIO('{"vals": {"name": "Acme"}}'))
    assert mod.main() == 0
    out = json.loads(capsys.readouterr().out.strip())
    assert out == {"ok": False, "error": "confirm_required"}


def test_crud_write_without_confirm_reports_confirm_required(
    tmp_path, monkeypatch, capsys,
):
    mod = _load_crud(monkeypatch, tmp_path)
    monkeypatch.setattr(mod.OdooRPC, "_json2", lambda self, m, meth, **kw: {"uid": 7})
    monkeypatch.setattr(
        sys, "argv", ["crud.py", "write", "--model", "res.partner", "--ids", "1"],
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO('{"vals": {"name": "Acme"}}'))
    assert mod.main() == 0
    out = json.loads(capsys.readouterr().out.strip())
    assert out == {"ok": False, "error": "confirm_required"}


def test_crud_unlink_without_confirm_reports_confirm_required(
    tmp_path, monkeypatch, capsys,
):
    mod = _load_crud(monkeypatch, tmp_path)
    monkeypatch.setattr(mod.OdooRPC, "_json2", lambda self, m, meth, **kw: {"uid": 7})
    monkeypatch.setattr(
        sys, "argv", ["crud.py", "unlink", "--model", "res.partner", "--ids", "1"],
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    assert mod.main() == 0
    out = json.loads(capsys.readouterr().out.strip())
    assert out == {"ok": False, "error": "confirm_required"}


def test_crud_create_with_confirm_unwraps_json2_id(tmp_path, monkeypatch, capsys):
    mod = _load_crud(monkeypatch, tmp_path)

    def fake_json2(self, model, method, **kwargs):
        if method == "context_get":
            return {"uid": 7}
        if method == "create":
            return [55]
        raise AssertionError(f"unexpected {model}.{method}")

    monkeypatch.setattr(mod.OdooRPC, "_json2", fake_json2)
    monkeypatch.setattr(
        sys, "argv",
        ["crud.py", "create", "--model", "res.partner", "--confirm"],
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO('{"vals": {"name": "Acme"}}'))
    assert mod.main() == 0
    out = json.loads(capsys.readouterr().out.strip())
    assert out == {"ok": True, "model": "res.partner", "method": "create", "id": 55}


# --------------------------------------------------------------------------
# sql.py — refusals (no psql needed: both refusals return before subprocess)
# --------------------------------------------------------------------------


def _load_sql(monkeypatch, tmp_path):
    monkeypatch.setenv("HH_HOME", str(tmp_path))
    return _load(_COMMUNITY_SCRIPTS, "sql.py", "sql_under_test")


def test_sql_refuses_password_column(tmp_path, monkeypatch, capsys):
    mod = _load_sql(monkeypatch, tmp_path)
    monkeypatch.setattr(
        sys, "stdin",
        io.StringIO(json.dumps({"sql": "SELECT password FROM res_users", "confirm": False})),
    )
    assert mod.main() == 0
    out = json.loads(capsys.readouterr().out.strip())
    assert out == {"ok": False, "error": "secret_column_refused"}


def test_sql_refuses_drop_database(tmp_path, monkeypatch, capsys):
    mod = _load_sql(monkeypatch, tmp_path)
    monkeypatch.setattr(
        sys, "stdin",
        io.StringIO(json.dumps({"sql": "DROP DATABASE website", "confirm": True})),
    )
    assert mod.main() == 0
    out = json.loads(capsys.readouterr().out.strip())
    assert out == {"ok": False, "error": "drop_database_refused"}


def test_sql_mutating_without_confirm_reports_confirm_required(
    tmp_path, monkeypatch, capsys,
):
    mod = _load_sql(monkeypatch, tmp_path)
    monkeypatch.setattr(
        sys, "stdin",
        io.StringIO(json.dumps({"sql": "UPDATE res_partner SET name = 'x'", "confirm": False})),
    )
    assert mod.main() == 0
    out = json.loads(capsys.readouterr().out.strip())
    assert out == {"ok": False, "error": "confirm_required", "mutating": True}


# --------------------------------------------------------------------------
# list_models.py — talks ir.model, not a lead/site script
# --------------------------------------------------------------------------


def test_list_models_match_talks_ir_model(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HH_HOME", str(tmp_path))
    _admin_file(tmp_path)
    mod = _load(_COMMUNITY_SCRIPTS, "list_models.py", "list_models_under_test")
    calls: list[tuple[str, str]] = []

    def fake_json2(self, model, method, **kwargs):
        calls.append((model, method))
        if method == "context_get":
            return {"uid": 7}
        if model == "ir.model" and method == "search_read":
            return [{"id": 1, "model": "res.partner", "name": "Contact",
                      "transient": False, "state": "base"}]
        raise AssertionError(f"unexpected {model}.{method}")

    monkeypatch.setattr(mod.OdooRPC, "_json2", fake_json2)
    monkeypatch.setattr(sys, "argv", ["list_models.py", "--match", "partner"])
    assert mod.main() == 0
    out = json.loads(capsys.readouterr().out.strip())
    assert out["ok"] is True
    assert out["count"] == 1
    assert out["models"][0]["model"] == "res.partner"
    assert ("ir.model", "search_read") in calls
