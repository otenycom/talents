"""OdooRPC must take uid from the bearer session, not login=admin."""
from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "odoo_rpc.py"


def _load():
    spec = importlib.util.spec_from_file_location("crm_odoo_rpc_under_test", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_constructor_uses_context_get_uid(tmp_path, monkeypatch):
    data = tmp_path / ".hermes" / "data" / "crm-bot"
    data.mkdir(parents=True)
    (data / ".odoo-admin").write_text(
        "login=lab-ref1@oteny.local\npassword=x\napi_key=testkey\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("HH_HOME", str(tmp_path))
    mod = _load()
    calls: list[tuple[str, str]] = []

    def fake_json2(self, model, method, **kwargs):
        calls.append((model, method))
        if method == "context_get":
            return {"uid": 7}
        raise AssertionError(f"unexpected {model}.{method}")

    monkeypatch.setattr(mod.OdooRPC, "_json2", fake_json2)
    rpc = mod.OdooRPC()
    assert rpc.uid == 7
    assert calls == [("res.users", "context_get")]
