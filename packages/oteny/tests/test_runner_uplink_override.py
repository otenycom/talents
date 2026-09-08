"""A1 — ``oteny test`` reaches the client ERP at ``OTENY_UPLINK_URL`` when it is set.

The tenant record carries the bot's address for the ERP (a named tunnel). The author's
own scenario driver must be able to use a different address for the same database —
the local ``:8069`` beside the author — because the tunnel does not pass a plain bearer
through. ``OTENY_TESTER_KEY_FILE`` already does this for the key; this does it for the URL.
"""
from __future__ import annotations

from oteny import runner


class _Client:
    def search_read(self, model, domain, fields=None, limit=None, **kw):
        assert model == "hh.tenant"
        return [{
            "id": 1, "node_id": [7, "node"], "bot_username": False,
            "isolation_tier": "container",
            "uplink_url": "https://lane-b-uplink.example",
            "uplink_db": "crmain", "uplink_env": "staging",
            "discuss_channel_id": 42,
        }]


class _RunScenario:
    def set_live_driver(self, driver):
        self.driver = driver


def _quiet_runner(monkeypatch, tmp_path, seen: dict):
    def fake_driver(**kw):
        seen.update(kw)

        async def post(text, timeout):
            return ""
        return post, None

    monkeypatch.setattr(runner, "build_discuss_driver", fake_driver)
    monkeypatch.setattr(
        runner, "resolve_local_catalog",
        lambda bundle, bundle_dir, shared_dir=None: (str(tmp_path), lambda: None))
    monkeypatch.setattr(runner, "bundle_db_rel", lambda bundle, catalog_dir: None)
    monkeypatch.setattr(runner, "load_run_scenario", lambda catalog_dir: _RunScenario())


def test_discuss_driver_uses_the_tenant_url_by_default(monkeypatch, tmp_path):
    monkeypatch.delenv("OTENY_UPLINK_URL", raising=False)
    seen: dict = {}
    _quiet_runner(monkeypatch, tmp_path, seen)
    out = runner.run_scenarios_for_clone(
        _Client(), "hh00527", "cuneus-hr-talent", bundle_dir=str(tmp_path))
    assert out["ok"] is True
    assert seen["uplink_url"] == "https://lane-b-uplink.example"
    assert seen["uplink_db"] == "crmain"


def test_discuss_driver_uses_the_override_url_when_set(monkeypatch, tmp_path):
    monkeypatch.setenv("OTENY_UPLINK_URL", "http://127.0.0.1:8069")
    seen: dict = {}
    _quiet_runner(monkeypatch, tmp_path, seen)
    runner.run_scenarios_for_clone(
        _Client(), "hh00527", "cuneus-hr-talent", bundle_dir=str(tmp_path))
    assert seen["uplink_url"] == "http://127.0.0.1:8069"
    # The database is the same one the tunnel serves; only the address moves.
    assert seen["uplink_db"] == "crmain"
