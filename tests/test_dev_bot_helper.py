"""The durable dev-bot singleton launcher helper (D210) — the shared MECHANISM.

Proves the offline-provable half of skills/_shared/scripts/dev_bot.py with a fake Oteny client
(no network): the request shaping (dev_slot + bundle passed through), ensure's poll-to-terminal +
``reused`` surfacing + the failed-reuse AUTO-REBUILD, touch/down selectors, and hold's
detach-not-teardown + heartbeat-rebuild. The reuse DECISION is the platform's (§4) — this helper
carries the mechanism only, so no reuse ``if`` is under test.
"""

from __future__ import annotations

import signal
import time

from _talents import SHARED, load

db = load(SHARED / "dev_bot.py", "dev_bot_helper")


class FakeOteny:
    """Records every /json/2/ call; returns scripted responses queued per method."""

    def __init__(self, responses=None):
        self.calls: list[tuple] = []
        self._responses = responses or {}

    def call(self, model, method, **kw):
        self.calls.append((model, method, kw))
        r = self._responses.get(method)
        if callable(r):
            return r(kw)
        if isinstance(r, list):
            return r.pop(0) if r else {}
        return r if r is not None else {}

    def methods(self):
        return [m for _model, m, _kw in self.calls]


# ── the pure payload/parse helpers ──────────────────────────────────────────────────────── #
def test_dev_slot_slug_prefixes_user_and_sanitizes():
    assert db.dev_slot_slug("barney", user="ries") == "ries-barney"
    assert db.dev_slot_slug("MFNL Bot!", user="ries") == "ries-mfnl-bot"


def test_request_kwargs_passes_dev_slot_and_drops_none():
    kw = db.request_kwargs(dev_slot="ries-barney", bundle="cuneus-barney",
                           uplink_key="k", discuss_channel="8", uplink_url=None)
    assert kw["dev_slot"] == "ries-barney" and kw["bundle"] == "cuneus-barney"
    assert kw["uplink_key"] == "k" and kw["discuss_channel"] == "8"
    assert "uplink_url" not in kw                      # None is dropped, never sent as False


def test_parse_status_defaults_delivered_false_on_old_platform():
    terminal, state, ref, err, delivered, derr = db.parse_status(
        {"ok": True, "terminal": True, "state": "active", "ref": "hh0x"})
    assert terminal and state == "active" and ref == "hh0x"
    assert delivered is False                          # absent → False (belt-wait fallback)


# ── ensure: reuse-hit, create, and the failed-reuse auto-rebuild ───────────────────────── #
def test_ensure_surfaces_the_reused_flag_and_polls_to_active(monkeypatch):
    monkeypatch.setattr(db.time, "sleep", lambda *_a: None)
    oteny = FakeOteny({
        "request_dev_bot": {"accepted": True, "http": 202, "reused": True,
                            "ref": "hh0dev", "request_id": 5},
        "dev_bot_request_status": {"ok": True, "terminal": True, "state": "active",
                                   "ref": "hh0dev", "talent_delivered": True},
    })
    out = db.ensure(oteny, dev_slot="ries-barney", bundle="cuneus-barney", uplink_key="k", log=_no)
    assert out == {"ref": "hh0dev", "reused": True, "request_id": 5,
                   "delivered": True, "rebuilt": False}
    # the platform got dev_slot — reuse is ITS decision, not the launcher's
    assert oteny.calls[0][2]["dev_slot"] == "ries-barney"


def test_ensure_create_path_reports_not_reused(monkeypatch):
    monkeypatch.setattr(db.time, "sleep", lambda *_a: None)
    oteny = FakeOteny({
        "request_dev_bot": {"accepted": True, "request_id": 9},   # no `reused` → a fresh create
        "dev_bot_request_status": {"ok": True, "terminal": True, "state": "active",
                                   "ref": "hh0new", "talent_delivered": True},
    })
    out = db.ensure(oteny, dev_slot="ries-barney", bundle="b", log=_no)
    assert out["reused"] is False and out["ref"] == "hh0new" and out["rebuilt"] is False


def test_ensure_failed_reuse_target_auto_rebuilds(monkeypatch):
    monkeypatch.setattr(db.time, "sleep", lambda *_a: None)
    # 1st request: a reuse that FAILS (the incumbent's clone vanished). 2nd: the auto-rebuild
    # (dev_slot dropped) which misses → creates fresh → active.
    reqs = [
        {"accepted": True, "reused": True, "ref": "hh0dead", "request_id": 1},
        {"accepted": True, "request_id": 2},
    ]
    stats = [
        {"ok": True, "terminal": True, "state": "failed", "ref": "hh0dead",
         "error": "reuse converge failed"},
        {"ok": True, "terminal": True, "state": "active", "ref": "hh0fresh",
         "talent_delivered": True},
    ]
    oteny = FakeOteny({"request_dev_bot": reqs, "dev_bot_request_status": stats})
    out = db.ensure(oteny, dev_slot="ries-barney", bundle="b", uplink_key="k", log=_no)
    assert out["ref"] == "hh0fresh" and out["reused"] is False and out["rebuilt"] is True
    # the rebuild request dropped dev_slot (forces a create/miss), keeping the fresh key
    rebuild_kw = oteny.calls[2][2]
    assert "dev_slot" not in rebuild_kw and rebuild_kw["uplink_key"] == "k"


def test_ensure_raises_on_a_failed_create(monkeypatch):
    monkeypatch.setattr(db.time, "sleep", lambda *_a: None)
    oteny = FakeOteny({
        "request_dev_bot": {"accepted": True, "request_id": 3},    # a create, not a reuse
        "dev_bot_request_status": {"ok": True, "terminal": True, "state": "failed",
                                   "error": "cloud-init wedged"},
    })
    try:
        db.ensure(oteny, dev_slot="ries-barney", bundle="b", log=_no)
        raise AssertionError("expected RuntimeError")
    except RuntimeError as exc:
        assert "cloud-init wedged" in str(exc)


def test_ensure_falls_back_when_platform_predates_dev_slot(monkeypatch):
    # Forward/backward compat: a launcher passing dev_slot against a pre-D210 Oteny (no dev_slot
    # param) must degrade to a plain create, not error — so the platform-vs-launcher deploy order
    # never breaks a run. The first call (with dev_slot) is rejected; the retry drops it.
    monkeypatch.setattr(db.time, "sleep", lambda *_a: None)

    class _OldPlatform:
        def __init__(self):
            self.calls = []

        def call(self, model, method, **kw):
            self.calls.append((method, kw))
            if method == "request_dev_bot":
                if "dev_slot" in kw:
                    raise RuntimeError("Odoo error: TypeError: request_dev_bot() got an "
                                       "unexpected keyword argument 'dev_slot'")
                return {"accepted": True, "request_id": 1}           # a plain create, no reuse
            return {"ok": True, "terminal": True, "state": "active", "ref": "hh0old",
                    "talent_delivered": True}

    oteny = _OldPlatform()
    out = db.ensure(oteny, dev_slot="ries-barney", bundle="b", uplink_key="k", log=_no)
    assert out["ref"] == "hh0old" and out["reused"] is False
    reqs = [kw for m, kw in oteny.calls if m == "request_dev_bot"]
    assert "dev_slot" in reqs[0] and "dev_slot" not in reqs[1]       # retried without dev_slot
    assert reqs[1]["uplink_key"] == "k"                              # kept the rest of the payload


def test_ensure_raises_on_a_refused_request():
    oteny = FakeOteny({"request_dev_bot": {"accepted": False, "http": 429, "reason": "queue_full"}})
    try:
        db.ensure(oteny, dev_slot="s", bundle="b", log=_no)
        raise AssertionError("expected RuntimeError")
    except RuntimeError as exc:
        assert "refused" in str(exc)


# ── touch / down selectors ──────────────────────────────────────────────────────────────── #
def test_touch_by_ref_surfaces_live():
    oteny = FakeOteny({"touch_dev_bot": {"ok": True, "live": True, "ref": "hh0x"}})
    assert db.touch(oteny, ref="hh0x")["live"] is True
    assert oteny.calls[0][:2] == ("hh.dev_bot_request", "touch_dev_bot")
    assert oteny.calls[0][2] == {"ref": "hh0x"}


def test_touch_by_slot():
    oteny = FakeOteny({"touch_dev_bot": {"ok": True, "live": True}})
    db.touch(oteny, dev_slot="ries-b2c")
    assert oteny.calls[0][2] == {"dev_slot": "ries-b2c"}


def test_down_wraps_teardown():
    oteny = FakeOteny({"teardown_dev_bot": {"ok": True, "ref": "hh0x",
                                            "state": "teardown_scheduled"}})
    assert db.down(oteny, ref="hh0x")["ok"] is True
    assert oteny.methods() == ["teardown_dev_bot"]


# ── hold: detach-not-teardown + the keep-alive heartbeat ──────────────────────────────────── #
class FakeTunnel:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def test_hold_closes_tunnels_and_never_tears_down_on_normal_exit():
    oteny = FakeOteny()
    tun = FakeTunnel()
    with db.hold(oteny, "hh0x", [tun], heartbeat_s=999, log=_no):
        pass
    assert tun.closed is True
    assert "teardown_dev_bot" not in oteny.methods()   # the durable singleton survives


def test_hold_detaches_on_keyboardinterrupt_without_teardown():
    oteny = FakeOteny()
    tun = FakeTunnel()
    with db.hold(oteny, "hh0x", [tun], heartbeat_s=999, log=_no):
        raise KeyboardInterrupt      # "stop debugging" / Ctrl-C
    assert tun.closed is True
    assert "teardown_dev_bot" not in oteny.methods()


def test_hold_routes_sigterm_to_detach_not_teardown():
    # The load-bearing D210 fix: a SIGTERM (VS Code stop) closes tunnels but LEAVES the bot up.
    oteny = FakeOteny()
    tun = FakeTunnel()
    with db.hold(oteny, "hh0x", [tun], heartbeat_s=999, log=_no):
        signal.raise_signal(signal.SIGTERM)
        time.sleep(0.05)             # let the handler fire (it raises inside the with-body)
    assert tun.closed is True
    assert "teardown_dev_bot" not in oteny.methods()


def test_hold_heartbeat_touches_and_rebuilds_on_reap():
    # A short heartbeat: touch is called; when it returns live=False the bot was reaped → on_reaped.
    reaped = {"n": 0}
    oteny = FakeOteny({"touch_dev_bot": {"ok": True, "live": False}})
    tun = FakeTunnel()
    with db.hold(oteny, "hh0x", [tun], heartbeat_s=0.02, on_reaped=lambda: reaped.__setitem__("n", 1),
                 log=_no):
        for _ in range(50):
            if reaped["n"]:
                break
            time.sleep(0.02)
    assert reaped["n"] == 1
    assert "touch_dev_bot" in oteny.methods()
    assert "teardown_dev_bot" not in oteny.methods()


def _no(*_a, **_k):
    return None
