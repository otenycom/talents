"""D210 regression guard — the dev-bot helper tolerates an omitted/empty ``dev_slot``.

Before this guard ``ensure``/``request_kwargs`` declared ``dev_slot`` as a keyword-only arg with
NO default, so a caller that omitted it crashed with a ``TypeError`` before any request was sent.
That is exactly radar's ``--verify`` CI one-shot: it sets ``dev_slot=""``, ``build_request_kwargs``
drops the key when empty, and forwards ``**kwargs`` into ``ensure`` — which then blew up on the
missing required kwarg (uncaught by the launcher's ``except RuntimeError``). The fix defaults
``dev_slot=""`` and the platform treats a falsy slot as no-opt-in (always-create, never reuse).
"""
from __future__ import annotations

from _talents import SHARED, load

db = load(SHARED / "dev_bot.py", "dev_bot_helper")


class _FakeOteny:
    """Records every /json/2/ call; returns scripted per-method responses."""

    def __init__(self, responses):
        self.calls: list[tuple] = []
        self._responses = responses

    def call(self, model, method, **kw):
        self.calls.append((model, method, kw))
        r = self._responses.get(method)
        if isinstance(r, list):
            return r.pop(0) if r else {}
        return r if r is not None else {}


def test_request_kwargs_omitted_dev_slot_defaults_to_empty():
    # A channel-less / CI caller may omit dev_slot entirely — no TypeError, and it reaches the
    # platform as a falsy slot, which request_dev_bot treats as always-create (never reuse).
    kw = db.request_kwargs(bundle="cuneus-barney", uplink_key="k")
    assert kw["dev_slot"] == ""            # present but falsy → the platform's always-create path
    assert kw["bundle"] == "cuneus-barney"


def test_ensure_without_dev_slot_takes_always_create_path():
    # The exact radar --verify shape: no dev_slot in the forwarded kwargs. It must NOT raise a
    # TypeError; it must issue request_dev_bot with a falsy slot and poll to a fresh (non-reused) box.
    oteny = _FakeOteny({
        "request_dev_bot": {"accepted": True, "http": 202, "request_id": 7},   # note: no `reused`
        "dev_bot_request_status": {"ok": True, "terminal": True, "state": "active",
                                   "ref": "hh0new", "talent_delivered": True},
    })
    res = db.ensure(oteny, bundle="cuneus-barney", timeout_s=5, poll_s=0, log=lambda *a, **k: None)
    assert res["ref"] == "hh0new"
    assert res["reused"] is False          # a falsy slot never reuses — always a fresh create
    # The platform saw dev_slot="" (present, falsy), never a MISSING kwarg — proof there is no crash.
    req = next(kw for _m, m, kw in oteny.calls if m == "request_dev_bot")
    assert req.get("dev_slot", "__missing__") == ""
