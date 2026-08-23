"""The `connection` artifact class — the box's own readiness judge for Oteny Connections.

A Talent may declare that it needs a third-party account (`kind: saas` under
`connections:` in agent-profile.yaml). This belt answers whether that account has
actually reached THIS box, and it answers from files alone — no network. That is the
point rather than a limitation: the authoritative judge IS a network call, so a box
that could only ask the network would go blind in exactly the outage during which an
honest answer matters most.

It reads two facts, and needs both:

  * `~/.hermes/config.yaml` `secrets.oteny.env` — the map the last converge RENDERED;
  * `~/.hermes/state/delivered/<VAR>.ready` — the receipt written when a value ARRIVES,
    and cleared when the control plane authoritatively denies one.

Either fact alone leaves a window open. The render still names a variable between a
revoke and the converge that drops it; the receipt still sits on disk if nothing
fetched again after the render dropped the variable. Requiring both closes each window
with the other, so a revoked account reads NOT-READY whichever fact moved first.

The two facts also SPLIT the failure. Nothing rendered means the owner has not granted
the account, which is ordinary first-run state (NOT-READY). Rendered with no receipt
means the grant exists and nothing on this box delivered it, which the owner cannot fix
(UNKNOWN).
"""
from __future__ import annotations

import json

from _talents import SHARED, load, sandbox_env

sc = load(SHARED / "selfcheck.py", "sc_conn")

_MANIFEST = """
bot: connbot
artifacts:
  - kind: connection
    name: basecamp
    env_vars: [BASECAMP_TOKEN]
"""


def _box(root, *, plugin=True, rendered="basecamp", receipt=True):
    hermes = root / ".hermes"
    if plugin:
        (hermes / "plugins" / "hh-connections").mkdir(parents=True, exist_ok=True)
    hermes.mkdir(parents=True, exist_ok=True)
    if rendered:
        (hermes / "config.yaml").write_text(
            "secrets:\n  oteny:\n    enabled: true\n    env:\n"
            f'      BASECAMP_TOKEN: "oteny://{rendered}/access_token"\n')
    else:
        (hermes / "config.yaml").write_text("telegram:\n  channel_prompts: {}\n")
    delivered = hermes / "state" / "delivered"
    delivered.mkdir(parents=True, exist_ok=True)
    if receipt:
        (delivered / "BASECAMP_TOKEN.ready").write_text(json.dumps({
            "env_var": "BASECAMP_TOKEN", "connection": "basecamp", "sha256": "0" * 64}))
    man = root / "conn.yaml"
    man.write_text(_MANIFEST)
    return man


def test_granted_and_delivered_is_ready(tmp_path, monkeypatch):
    sandbox_env(monkeypatch, tmp_path)
    assert sc.run(_box(tmp_path))["ready"] is True


def test_no_grant_in_the_render_is_not_ready(tmp_path, monkeypatch):
    sandbox_env(monkeypatch, tmp_path)
    rep = sc.run(_box(tmp_path, rendered="", receipt=False))
    assert rep["ready"] is False and not rep["unknown"]
    assert "not granted" in rep["missing"][0]["reason"]


def test_a_grant_with_no_delivered_value_is_an_environment_fault(tmp_path, monkeypatch):
    """The grant EXISTS and nothing here delivered it. The owner cannot fix that."""
    sandbox_env(monkeypatch, tmp_path)
    rep = sc.run(_box(tmp_path, receipt=False))
    assert rep["ready"] is False and rep["missing"] == []
    assert "undelivered" in rep["unknown"][0]["reason"]


def test_a_stale_receipt_does_not_survive_the_render_dropping_it(tmp_path, monkeypatch):
    sandbox_env(monkeypatch, tmp_path)
    assert sc.run(_box(tmp_path, rendered="", receipt=True))["ready"] is False


def test_another_grant_holding_the_variable_says_so(tmp_path, monkeypatch):
    sandbox_env(monkeypatch, tmp_path)
    rep = sc.run(_box(tmp_path, rendered="otherboard"))
    assert "another grant binds it" in rep["missing"][0]["reason"]


def test_no_plugin_before_a_grant_exists_is_ordinary_first_run(tmp_path, monkeypatch):
    """The plugin ships only once a grant exists, so its absence before one is NORMAL.
    Reading UNKNOWN here would tell every un-connected owner to report a fault."""
    sandbox_env(monkeypatch, tmp_path)
    rep = sc.run(_box(tmp_path, plugin=False, rendered="", receipt=False))
    assert rep["unknown"] == [] and "not granted" in rep["missing"][0]["reason"]


def test_a_grant_with_no_plugin_to_fetch_it_names_the_plugin(tmp_path, monkeypatch):
    sandbox_env(monkeypatch, tmp_path)
    rep = sc.run(_box(tmp_path, plugin=False, receipt=False))
    assert "no hh-connections plugin" in rep["unknown"][0]["reason"]


def test_an_unreadable_config_is_an_environment_fault(tmp_path, monkeypatch):
    sandbox_env(monkeypatch, tmp_path)
    man = _box(tmp_path)
    (tmp_path / ".hermes" / "config.yaml").write_text("secrets: [oh, dear\n")
    assert [u["kind"] for u in sc.run(man)["unknown"]] == ["connection"]


def test_the_running_value_is_fingerprinted_and_never_gated(tmp_path, monkeypatch):
    sandbox_env(monkeypatch, tmp_path)
    monkeypatch.setenv("BASECAMP_TOKEN", "not-the-delivered-value")
    rep = sc.run(_box(tmp_path))
    assert rep["ready"] is True
    assert rep["artifacts"][0]["fingerprints"] == {"BASECAMP_TOKEN": "differs"}
