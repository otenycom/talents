"""``hand_off`` waits on ground truth and ends early on ``fail_when``.

A business-bot scenario hands a record to the bot and waits for its terminal state
(``done_when``). When the record goes back to the human queue first (a hand-back:
the adapter's stream watchdog, the reaper, or the Talent's own claim-fence
decision), ``fail_when`` ends the wait now and names the reason in the reply,
instead of burning the whole ``reply_timeout``.
"""

import asyncio
import time

import pytest

from oteny import discuss
from oteny.live import LiveDriver


class FakePoster:
    """Duck-typed like the Discuss poster: a coroutine to post, plus the two waits."""

    def __init__(self, narration="Bot: I handed the record back."):
        self.narration = narration

    async def __call__(self, text, timeout):  # pragma: no cover - not used by hand_off
        return ""

    async def latest_message_id(self):
        return 41

    async def wait_for_reply(self, after, timeout):
        return self.narration


def _uplink(state_sequence, claim_sequence):
    """An async ``(model, method, **kw)`` over a scripted record: ``state_sequence``
    is what ``state_id`` reads on successive polls; ``claim_sequence`` how many rows
    the ``fail_when`` count query returns on successive polls."""
    polls = {"state": 0, "claim": 0}
    calls = []

    async def call(model, method, **kw):
        calls.append((model, method, kw))
        if model == "acme.state" and method == "search_read":
            return [{"id": 163}]                                   # the resolve step
        if method == "write":
            return True
        if model == "acme.permit" and method == "search_read":
            if kw.get("fields") == ["id"]:
                return [{"id": 7}]                                # the call step's ids
            i = min(polls["state"], len(state_sequence) - 1)
            polls["state"] += 1
            return [{"id": 7, "state_id": [0, state_sequence[i]]}]
        if method == "search_count":
            i = min(polls["claim"], len(claim_sequence) - 1)
            polls["claim"] += 1
            return claim_sequence[i]
        raise AssertionError(f"unexpected uplink call {model}.{method}")

    call.calls = calls
    return call


def _talent(uplink):
    return LiveDriver(ref="lab00003", bot_username=None, db_rel=None, exec_on_node=None,
                      dm=None, dm_timeout=30.0, post_message=FakePoster(), uplink_call=uplink,
                      uplink_poll_s=0.01)


_SPEC = {
    "steps": [
        {"resolve": {"model": "acme.state",
                     "domain": [["name", "=", "With Bot"], ["workflow_id.name", "=", "Arrange permit"]],
                     "as": {"state_id": "id"}}},
        {"call": {"model": "acme.permit", "method": "write",
                  "domain": [["res_name", "ilike", "Happypath"]],
                  "kwargs": {"vals": {"state_id": "$state_id", "permit_dispatch_mode": "fill_to_draft"}}}},
    ],
    "done_when": {"model": "acme.permit", "domain": [["res_name", "ilike", "Happypath"]],
                  "contains": {"field": "state_id", "value": "Draft ready for review"}},
    "fail_when": [{"model": "acme.permit", "reason": "handback",
                   "domain": [["res_name", "ilike", "Happypath"], ["state_id.name", "=", "Not Started"],
                              ["bot_claim_token", "=", False]],
                   "count": 1}],
}


def test_hand_off_ends_early_when_fail_when_matches():
    uplink = _uplink(["With Bot", "Barney is filling", "Not Started", "Not Started"], [0, 0, 1])
    t0 = time.monotonic()
    reply = _talent(uplink).hand_off(_SPEC, timeout=20.0)
    assert time.monotonic() - t0 < 5.0, "the wait must end on the hand-back, not on reply_timeout"
    assert reply.endswith("[hand_off ended early: handback]")
    assert "I handed the record back" in reply
    assert any(m == "write" for _, m, _ in uplink.calls), "the real hand-off write happened first"


def test_hand_off_reaches_done_when_without_the_marker():
    uplink = _uplink(["With Bot", "Draft ready for review"], [0, 0, 0, 0])
    reply = _talent(uplink).hand_off(_SPEC, timeout=20.0)
    assert reply == "Bot: I handed the record back."
    assert "ended early" not in reply


def test_await_done_reports_timeout():
    uplink = _uplink(["With Bot"], [0])
    talent = _talent(uplink)
    outcome = asyncio.run(talent._await_done(_SPEC["done_when"], time.monotonic() + 0.05, _SPEC["fail_when"]))
    assert outcome == "timeout"


def test_tester_key_file_env_override(monkeypatch):
    cfg = {"tester_key_file": "~/.oteny/secrets/lane-a-key"}
    monkeypatch.delenv("OTENY_TESTER_KEY_FILE", raising=False)
    assert discuss.tester_key_file(cfg) == "~/.oteny/secrets/lane-a-key"
    monkeypatch.setenv("OTENY_TESTER_KEY_FILE", "/tmp/lane-b-key")
    assert discuss.tester_key_file(cfg) == "/tmp/lane-b-key"
    assert discuss.tester_key_file({}) == "/tmp/lane-b-key"


@pytest.mark.parametrize("fail_when", [None, [], {}])
def test_fail_when_absent_keeps_the_plain_wait(fail_when):
    uplink = _uplink(["With Bot", "Draft ready for review"], [1])
    spec = dict(_SPEC, fail_when=fail_when)
    reply = _talent(uplink).hand_off(spec, timeout=20.0)
    assert "ended early" not in reply


def test_uplink_url_env_override(monkeypatch):
    """A1: an author whose laptop sits beside the client ERP drives the scenario at
    ``http://127.0.0.1:8069`` while the bot keeps its tunnel address. Without the
    override the tunnel refuses a plain bearer, so the author cannot reach it."""
    monkeypatch.delenv("OTENY_UPLINK_URL", raising=False)
    assert discuss.uplink_url_for_driver("https://lane-b-uplink.example") == (
        "https://lane-b-uplink.example")
    monkeypatch.setenv("OTENY_UPLINK_URL", "http://127.0.0.1:8069")
    assert discuss.uplink_url_for_driver("https://lane-b-uplink.example") == (
        "http://127.0.0.1:8069")
    assert discuss.uplink_url_for_driver("") == "http://127.0.0.1:8069"


def test_hand_off_binds_the_resolved_id_into_the_call():
    uplink = _uplink(["Draft ready for review | Arrange permit"], [0])
    _talent(uplink).hand_off(_SPEC, timeout=5)
    write = next(c for c in uplink.calls if c[1] == "write")
    assert write == ("acme.permit", "write",
                     {"ids": [7], "vals": {"state_id": 163, "permit_dispatch_mode": "fill_to_draft"}})
    resolve = next(c for c in uplink.calls if c[0] == "acme.state")
    assert resolve[2]["fields"] == ["id"]


def test_hand_off_refuses_a_state_name_and_an_unknown_step():
    uplink = _uplink(["x"], [0])
    with pytest.raises(RuntimeError, match="a state name is one engine's word"):
        _talent(uplink).hand_off({"model": "acme.permit", "domain": [], "to_state": "With Bot"})
    with pytest.raises(RuntimeError, match="must be one of"):
        _talent(uplink).hand_off({"steps": [{"poke": {"model": "acme.permit"}}]})
    with pytest.raises(RuntimeError, match="before any step bound it"):
        _talent(uplink).hand_off({"steps": [{"call": {"model": "acme.permit", "method": "write",
                                                       "domain": [], "kwargs": {"vals": {"state_id": "$nope"}}}}]})


def test_a_call_without_a_domain_is_a_model_method():
    calls = []

    async def uplink(model, method, **kw):
        calls.append((model, method, kw))
        return True

    _talent(uplink).hand_off({"steps": [{"call": {"model": "acme.permit", "method": "bot_hand_off",
                                                   "kwargs": {"name": "Happypath"}}}]}, timeout=1)
    assert calls == [("acme.permit", "bot_hand_off", {"name": "Happypath"})]


def test_done_when_contains_matches_a_composite_display_and_equals_is_exact():
    uplink = _uplink(["Draft ready for review | Arrange permit"], [0])
    d = _talent(uplink)
    spec = dict(_SPEC, done_when={"model": "acme.permit", "domain": [],
                                  "equals": {"field": "state_id", "value": "Draft ready for review"}})
    # equals on the bare name never matches the composite display: the wait runs out
    assert asyncio.run(d._await_done(spec["done_when"], time.monotonic() + 0.05)) == "timeout"
    assert asyncio.run(d._await_done(_SPEC["done_when"], time.monotonic() + 0.5)) == "done"
