"""site_rpc.py — admin file + JSON-2 helpers (offline).

``site_rpc.OdooRPC`` is a thin subclass of odoo-community's shared
``local_odoo_rpc.OdooRPC`` (see that module and the plan's §6a "One JSON-2
client"). The wire — reading ``api_key=``, the bearer POST, the ``call``
kwargs map — lives on the community base and is exercised here through the
subclass, not through a private ``site_rpc._load_admin`` / ``_json2`` that no
longer exist.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

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


class _Resp:
    """A ``urlopen`` context-manager stub returning one JSON payload."""

    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return json.dumps(self._payload).encode()


def _fake_urlopen(calls: list[dict], *, uid: int = 2, other=3):
    """A stub good for both the constructor's ``context_get`` call and one
    caller-issued ``call()`` — the same shape every OdooRPC construction
    needs, so each test below only supplies the ``other`` return value."""

    def fake_urlopen(req, timeout=60):
        body = json.loads(req.data.decode())
        calls.append({
            "url": req.full_url,
            "auth": req.get_header("Authorization"),
            "body": body,
        })
        if req.full_url.endswith("/json/2/res.users/context_get"):
            return _Resp({"uid": uid})
        return _Resp(other)

    return fake_urlopen


def test_odoo_rpc_requires_api_key(home):
    _, data = home
    (data / ".odoo-admin").write_text(
        "login=a@b.c\npassword=secret\n", encoding="utf-8",
    )
    mod = _load()
    with pytest.raises(RuntimeError, match="no_api_key"):
        mod.OdooRPC()


def test_odoo_rpc_reads_api_key_and_db(home, monkeypatch):
    _, data = home
    (data / ".odoo-admin").write_text(
        "login=a@b.c\npassword=secret\n" + "api_key=" + "k123\n", encoding="utf-8",
    )
    mod = _load()
    calls: list[dict] = []
    monkeypatch.setattr(
        mod.urllib.request, "urlopen", _fake_urlopen(calls),
    )
    rpc = mod.OdooRPC()
    assert rpc.apikey == "k123"
    assert rpc.db == "website"
    assert rpc.uid == 2


def test_odoo_rpc_sends_bearer_on_the_community_client(home, monkeypatch):
    _, data = home
    (data / ".odoo-admin").write_text(
        "login=a@b.c\npassword=secret\n" + "api_key=" + "k123\n", encoding="utf-8",
    )
    mod = _load()
    calls: list[dict] = []
    monkeypatch.setattr(
        mod.urllib.request, "urlopen", _fake_urlopen(calls, other=3),
    )
    rpc = mod.OdooRPC()
    out = rpc.call("website.page", "search_count", kwargs={"domain": []})
    assert out == 3
    last = calls[-1]
    assert last["url"].endswith("/json/2/website.page/search_count")
    assert last["auth"] == "bearer k123"
    assert last["body"] == {"domain": []}
