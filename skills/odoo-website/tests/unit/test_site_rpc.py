"""site_rpc.py — admin file + JSON-2 helpers (offline)."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from unittest import mock

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "site_rpc.py"


def _load():
    spec = importlib.util.spec_from_file_location("site_rpc_under_test", _SCRIPT)
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


def test_load_admin_requires_api_key(home):
    _, data = home
    (data / ".odoo-admin").write_text(
        "login=a@b.c\npassword=secret\n", encoding="utf-8",
    )
    mod = _load()
    with pytest.raises(SystemExit, match="no_api_key"):
        mod._load_admin()


def test_load_admin_ok(home):
    _, data = home
    (data / ".odoo-admin").write_text(
        "login=a@b.c\npassword=secret\n" + "api_key=" + "k123\n", encoding="utf-8",
    )
    mod = _load()
    assert mod._load_admin() == ("a@b.c", "k123")


def test_json2_sends_bearer(home, monkeypatch):
    _, data = home
    (data / ".odoo-admin").write_text(
        "login=a@b.c\npassword=secret\n" + "api_key=" + "k123\n", encoding="utf-8",
    )
    mod = _load()
    captured: dict = {}

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"3"

    def fake_urlopen(req, timeout=60):
        captured["url"] = req.full_url
        captured["auth"] = req.get_header("Authorization")
        captured["body"] = json.loads(req.data.decode())
        return _Resp()

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    out = mod._json2("website.page", "search_count", "k123", domain=[])
    assert out == 3
    assert captured["url"].endswith("/json/2/website.page/search_count")
    assert captured["auth"] == "bearer k123"
    assert captured["body"] == {"domain": []}
