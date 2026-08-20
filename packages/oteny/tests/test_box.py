"""Offline tests for the account-scoped box-access client (``oteny.box``).

Pins the inspect/shell lanes, the rc=128 / 429 open retry, and the close-wait
so a second ``oteny shell --cmd`` does not race the reap's gateway restart.
"""
from __future__ import annotations

import subprocess

import pytest

from oteny.box import (
    AuthorBoxAccess,
    BoxAccessError,
    _is_transient_shell_error,
)


class FakeClient:
    """Records ``call(model, method, **kw)`` and replays a scripted queue per method."""

    def __init__(self, scripts: dict[str, list]):
        self._scripts = {k: list(v) for k, v in scripts.items()}
        self.calls: list[tuple] = []

    def call(self, model, method, **kw):
        self.calls.append((model, method, kw))
        q = self._scripts.get(method)
        if not q:
            raise AssertionError(f"unexpected call {method}({kw})")
        return q.pop(0) if len(q) > 1 else q[0]


def _fake_run_factory():
    """A fake ``subprocess.run``: ssh-keygen writes a .pub file; ssh succeeds."""

    def _run(cmd, **kw):
        if cmd and cmd[0].endswith("ssh-keygen"):
            key_path = cmd[cmd.index("-f") + 1]
            with open(key_path + ".pub", "w", encoding="utf-8") as fh:
                fh.write("ssh-ed25519 AAAAdummy test\n")
            return subprocess.CompletedProcess(cmd, 0, "", "")
        if cmd and cmd[0] == "dig":
            return subprocess.CompletedProcess(cmd, 0, "1.1.1.1\n", "")
        stdout = "ok\n" if cmd[-1] != "true" else ""
        return subprocess.CompletedProcess(cmd, 0, stdout, "")

    return _run


class _FakeProc:
    def terminate(self):
        self.terminated = True

    def wait(self, timeout=None):
        return 0


def _fake_clock():
    t = {"v": 0.0}

    def _clock():
        t["v"] += 1.0
        return t["v"]

    return _clock


def _incident_128_error() -> str:
    return "ProcessError('Process exited with non-zero exit status 128')"


# ── transient classifier (the 2026-08-20 incident string) ─────────────────────── #

def test_incident_128_is_transient():
    err = BoxAccessError(f"shell 44 ended before active: {_incident_128_error()}")
    assert _is_transient_shell_error(err)


def test_worker_timeout_is_transient():
    err = BoxAccessError("shell 176 ended before active: TimeoutError()")
    assert _is_transient_shell_error(err)


def test_inflight_429_is_transient():
    err = BoxAccessError(
        "box-access shell refused for 'hh00458': too_many_inflight")
    assert _is_transient_shell_error(err)


def test_not_found_is_permanent():
    err = BoxAccessError("box-access shell refused for 'hhX': not_found")
    assert not _is_transient_shell_error(err)


# ── inspect ───────────────────────────────────────────────────────────────────── #

def test_inspect_polls_to_done():
    snap = {"ref": "hh1", "log_tails": {"gateway.log": "hello"}}
    client = FakeClient({
        "request_box_access": [{"accepted": True, "request_id": 7, "state": "queued"}],
        "box_access_status": [
            {"ok": True, "state": "queued", "terminal": False},
            {"ok": True, "state": "done", "terminal": True, "snapshot": snap},
        ],
    })
    box = AuthorBoxAccess(client, sleep=lambda s: None, clock=_fake_clock())
    assert box.inspect("hh1") == snap
    assert box.gateway_log_tail("hh1") == "hello"


# ── shell happy path + close-wait ─────────────────────────────────────────────── #

def test_shell_opens_execs_and_waits_until_closed(monkeypatch):
    monkeypatch.setattr("oteny.box._free_local_port", lambda: 45678)
    connect = {"hostname": "box-9.oteny.bot", "user": "hermes", "port": 2222}
    client = FakeClient({
        "request_box_access": [{"accepted": True, "request_id": 9, "state": "queued"}],
        "box_access_status": [
            {"ok": True, "state": "running", "terminal": False},
            {"ok": True, "state": "active", "terminal": False, "connect_info": connect},
            {"ok": True, "state": "active", "terminal": False, "connect_info": connect},
            {"ok": True, "state": "done", "terminal": True},
        ],
        "close_box_access": [{"ok": True}],
    })
    box = AuthorBoxAccess(
        client, sleep=lambda s: None, clock=_fake_clock(),
        run=_fake_run_factory(), popen=lambda *a, **k: _FakeProc())
    with box.shell("hh1") as sh:
        out = sh("echo ok")
        assert "ok" in out
    methods = [m for _, m, _ in client.calls]
    assert methods.count("close_box_access") == 1
    assert methods.count("request_box_access") == 1
    # open poll (running+active) + close-wait (active then done)
    assert methods.count("box_access_status") >= 4
    req = next(kw for _, m, kw in client.calls if m == "request_box_access")
    assert req["kind"] == "shell" and req.get("ssh_pubkey", "").startswith("ssh-ed25519")


def test_shell_closes_even_when_the_body_raises(monkeypatch):
    monkeypatch.setattr("oteny.box._free_local_port", lambda: 45999)
    connect = {"hostname": "box-3.oteny.bot", "user": "hermes"}
    client = FakeClient({
        "request_box_access": [{"accepted": True, "request_id": 3, "state": "queued"}],
        "box_access_status": [
            {"ok": True, "state": "active", "terminal": False, "connect_info": connect},
            {"ok": True, "state": "done", "terminal": True},
        ],
        "close_box_access": [{"ok": True}],
    })
    box = AuthorBoxAccess(
        client, sleep=lambda s: None, clock=_fake_clock(),
        run=_fake_run_factory(), popen=lambda *a, **k: _FakeProc())
    with pytest.raises(ValueError):
        with box.shell("hh1"):
            raise ValueError("body blew up")
    assert [m for _, m, _ in client.calls].count("close_box_access") == 1


# ── the rc=128 race (same-tick reap then open) ────────────────────────────────── #

def test_shell_retries_after_worker_128(monkeypatch):
    """A failed-before-active window is dead. The next open is a new request."""
    monkeypatch.setattr("oteny.box._free_local_port", lambda: 45700)
    connect = {"hostname": "box-21.oteny.bot", "user": "hermes"}
    boom = _incident_128_error()
    client = FakeClient({
        "request_box_access": [
            {"accepted": True, "request_id": 21, "state": "queued"},
            {"accepted": True, "request_id": 22, "state": "queued"},
            {"accepted": True, "request_id": 23, "state": "queued"},
        ],
        "box_access_status": [
            {"ok": True, "state": "failed", "terminal": True, "error": boom},
            {"ok": True, "state": "failed", "terminal": True, "error": boom},
            {"ok": True, "state": "failed", "terminal": True, "error": boom},
            {"ok": True, "state": "failed", "terminal": True, "error": boom},
            {"ok": True, "state": "failed", "terminal": True, "error": boom},
            {"ok": True, "state": "failed", "terminal": True, "error": boom},
            {"ok": True, "state": "active", "terminal": False, "connect_info": connect},
            {"ok": True, "state": "done", "terminal": True},
        ],
        "close_box_access": [{"ok": True}],
    })
    sleeps: list[float] = []
    box = AuthorBoxAccess(
        client, sleep=sleeps.append, clock=_fake_clock(),
        shell_open_attempts=6, shell_retry_s=8.0,
        run=_fake_run_factory(), popen=lambda *a, **k: _FakeProc())
    with box.shell("hh00458") as sh:
        sh("true")
    opens = [kw for _, m, kw in client.calls if m == "request_box_access"]
    assert len(opens) == 3
    assert sleeps[:2] == [8.0, 16.0]


def test_shell_retries_429_inflight_then_opens(monkeypatch):
    monkeypatch.setattr("oteny.box._free_local_port", lambda: 45701)
    connect = {"hostname": "box-30.oteny.bot", "user": "hermes"}
    client = FakeClient({
        "request_box_access": [
            {"accepted": False, "http": 429, "reason": "too_many_inflight"},
            {"accepted": True, "request_id": 30, "state": "queued"},
        ],
        "box_access_status": [
            {"ok": True, "state": "active", "terminal": False, "connect_info": connect},
            {"ok": True, "state": "done", "terminal": True},
        ],
        "close_box_access": [{"ok": True}],
    })
    sleeps: list[float] = []
    box = AuthorBoxAccess(
        client, sleep=sleeps.append, clock=_fake_clock(),
        run=_fake_run_factory(), popen=lambda *a, **k: _FakeProc())
    with box.shell("hh00458") as sh:
        sh("true")
    assert [m for _, m, _ in client.calls].count("request_box_access") == 2
    assert sleeps[0] >= 60.0


def test_shell_does_not_retry_a_permanent_refuse():
    client = FakeClient({
        "request_box_access": [{"accepted": False, "reason": "not_found"}],
    })
    box = AuthorBoxAccess(client, sleep=lambda s: None, clock=_fake_clock())
    with pytest.raises(BoxAccessError, match="not_found"):
        with box.shell("hhX"):
            pass
    assert [m for _, m, _ in client.calls].count("request_box_access") == 1


def test_shell_gives_up_after_open_attempts(monkeypatch):
    monkeypatch.setattr("oteny.box._free_local_port", lambda: 45702)
    boom = _incident_128_error()
    failed = {"ok": True, "state": "failed", "terminal": True, "error": boom}
    client = FakeClient({
        "request_box_access": [
            {"accepted": True, "request_id": n, "state": "queued"} for n in (1, 2, 3)
        ],
        "box_access_status": [failed],
        "close_box_access": [{"ok": True}],
    })
    box = AuthorBoxAccess(
        client, sleep=lambda s: None, clock=_fake_clock(),
        shell_open_attempts=3,
        run=_fake_run_factory(), popen=lambda *a, **k: _FakeProc())
    with pytest.raises(BoxAccessError, match="ended before active"):
        with box.shell("hh00458"):
            pass
    assert [m for _, m, _ in client.calls].count("request_box_access") == 3


def test_shell_does_not_open_a_second_window_while_first_is_queued(monkeypatch):
    """A queued rid cannot be dequeued by close. A second open would 429 the cap."""
    monkeypatch.setattr("oteny.box._free_local_port", lambda: 45703)
    running = {"ok": True, "state": "queued", "terminal": False}
    client = FakeClient({
        "request_box_access": [{"accepted": True, "request_id": 40, "state": "queued"}],
        "box_access_status": [running],
        "close_box_access": [{"ok": True}],
    })
    box = AuthorBoxAccess(
        client, sleep=lambda s: None, clock=_fake_clock(),
        shell_timeout_s=3, shell_close_timeout_s=3,
        run=_fake_run_factory(), popen=lambda *a, **k: _FakeProc())
    with pytest.raises(BoxAccessError, match="still in flight after close"):
        with box.shell("hh00458"):
            pass
    assert [m for _, m, _ in client.calls].count("request_box_access") == 1


def test_the_client_never_holds_a_mgmt_key_or_settings():
    box = AuthorBoxAccess(FakeClient({}))
    for attr in vars(box):
        assert "mgmt" not in attr and "settings" not in attr.lower()
