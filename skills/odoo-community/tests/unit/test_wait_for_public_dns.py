"""wait_for_public_dns.py is immediate, then polls; it never sleeps first."""
from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPT = (
    Path(__file__).resolve().parents[2] / "scripts" / "wait_for_public_dns.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("wait_for_public_dns", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_hostname_from_url_and_host():
    mod = _load()
    assert mod.hostname_from("https://oxp-leads.oteny.bot") == "oxp-leads.oteny.bot"
    assert mod.hostname_from("https://oxp-leads.oteny.bot/odoo/crm/1") == (
        "oxp-leads.oteny.bot"
    )
    assert mod.hostname_from("oxp-leads.oteny.bot") == "oxp-leads.oteny.bot"
    assert mod.hostname_from("https://OXO.oteny.bot:443") == "oxo.oteny.bot"
    assert mod.hostname_from("localhost") is None
    assert mod.hostname_from("") is None
    assert mod.hostname_from("not a host") is None


def test_ready_on_first_check_does_not_sleep():
    mod = _load()
    slept = []
    assert mod.wait_until(
        "oxp-leads.oteny.bot",
        resolver=lambda host: True,
        sleep=slept.append,
        timeout_s=60,
        interval_s=2,
    )
    assert slept == []


def test_pending_then_ready_sleeps_once():
    mod = _load()
    calls = {"n": 0}
    slept = []

    def resolver(_host):
        calls["n"] += 1
        return calls["n"] >= 2

    assert mod.wait_until(
        "oxp-leads.oteny.bot",
        resolver=resolver,
        sleep=slept.append,
        timeout_s=60,
        interval_s=2,
    )
    assert slept == [2]
    assert calls["n"] == 2


def test_deadline_returns_false_without_a_first_sleep():
    mod = _load()
    clock = {"t": 0.0}

    def now():
        return clock["t"]

    def sleep(seconds):
        clock["t"] += seconds

    assert not mod.wait_until(
        "oxp-leads.oteny.bot",
        resolver=lambda _host: False,
        sleep=sleep,
        clock=now,
        timeout_s=4,
        interval_s=2,
    )


def test_main_rejects_a_local_name_without_dns():
    mod = _load()
    rc = mod.main(["localhost"])
    assert rc == 0


def test_public_query_treats_answer_as_ready_and_nxdomain_as_not():
    mod = _load()

    def send_ok(_resolver, payload, _timeout):
        # QR=1, rcode=0, ANCOUNT=1. The script only reads the header.
        return payload[:2] + b"\x81\x00\x00\x01\x00\x01\x00\x00\x00\x00"

    def send_nx(_resolver, payload, _timeout):
        return payload[:2] + b"\x81\x03\x00\x01\x00\x00\x00\x00\x00\x00"

    def doh_silent(_host, _qtype, _timeout):
        return {"Status": 3, "Answer": []}

    assert mod.query_public_dns(
        "oxp-leads.oteny.bot", udp_send=send_ok, doh_get=doh_silent)
    assert not mod.query_public_dns(
        "missing.oteny.bot", udp_send=send_nx, doh_get=doh_silent)


def test_doh_fallback_when_udp_is_blocked():
    mod = _load()

    def send_blocked(_resolver, _payload, _timeout):
        raise OSError("udp 53 blocked")

    def doh_ok(_host, _qtype, _timeout):
        return {"Status": 0, "Answer": [{"data": "1.2.3.4"}]}

    assert mod.query_public_dns(
        "oxp-leads.oteny.bot", udp_send=send_blocked, doh_get=doh_ok)
