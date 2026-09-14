#!/usr/bin/env python3
"""Wait until a public hostname exists on a public resolver.

``host_website`` returns a URL while the name is still being set up. A
laptop that looks the name up then caches NXDOMAIN for minutes. This
script asks 1.1.1.1 (then 8.8.8.8) for A or AAAA. The first check is
immediate. It prints ``PUBLIC_URL_READY`` as soon as a record appears,
or ``PUBLIC_URL_PENDING`` when the deadline passes. Always exit 0 so a
timeout is a result, not a failed command.

Usage:
    python3 wait_for_public_dns.py https://oxp-leads.oteny.bot
    python3 wait_for_public_dns.py oxp-leads.oteny.bot
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import struct
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

RESOLVERS = ("1.1.1.1", "8.8.8.8")
_QTYPE_A = 1
_QTYPE_AAAA = 28


def hostname_from(arg: str) -> str | None:
    """Take a URL or a host. Reject an empty or local name."""
    text = (arg or "").strip()
    if "://" in text:
        text = text.split("://", 1)[1]
    text = text.split("/", 1)[0]
    text = text.split("?", 1)[0]
    text = text.split("#", 1)[0]
    text = text.split("@")[-1]
    text = text.rsplit("%", 1)[0]
    if text.startswith("["):
        end = text.find("]")
        text = text[1:end] if end > 0 else ""
    else:
        text = text.split(":", 1)[0]
    host = text.strip(".").lower()
    if not host or "." not in host:
        return None
    if any(ch for ch in host if not (ch.isalnum() or ch in "-.")):
        return None
    return host


def _encode_qname(host: str) -> bytes:
    out = bytearray()
    for label in host.rstrip(".").split("."):
        raw = label.encode("ascii")
        if not raw or len(raw) > 63:
            raise ValueError(host)
        out.append(len(raw))
        out.extend(raw)
    out.append(0)
    return bytes(out)


def _build_query(host: str, qtype: int) -> bytes:
    header = os.urandom(2) + struct.pack("!HHHHH", 0x0100, 1, 0, 0, 0)
    return header + _encode_qname(host) + struct.pack("!HH", qtype, 1)


def _rcode_and_answers(packet: bytes) -> tuple[int, int]:
    if len(packet) < 12:
        return 2, 0
    rcode = packet[3] & 0x0F
    ancount = struct.unpack("!H", packet[6:8])[0]
    return rcode, ancount


def query_public_dns(
    host: str,
    *,
    resolvers: tuple[str, ...] = RESOLVERS,
    per_try_s: float = 2.0,
    udp_send=None,
    doh_get=None,
) -> bool:
    """True when a public resolver returns at least one A or AAAA.

    UDP to 1.1.1.1 / 8.8.8.8 first. If a tenant box blocks port 53,
    HTTPS DNS (DoH) is the fallback so a blocked UDP does not stall
    a live name.
    """
    send = udp_send or _udp_query
    for resolver in resolvers:
        for qtype in (_QTYPE_A, _QTYPE_AAAA):
            try:
                packet = send(resolver, _build_query(host, qtype), per_try_s)
            except OSError:
                continue
            rcode, answers = _rcode_and_answers(packet)
            if rcode == 0 and answers > 0:
                return True
    return _doh_lookup(host, timeout_s=per_try_s, getter=doh_get)


def _doh_lookup(host: str, *, timeout_s: float, getter=None) -> bool:
    get = getter or _doh_json
    for qtype in ("A", "AAAA"):
        try:
            data = get(host, qtype, timeout_s)
        except (OSError, urllib.error.URLError, ValueError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        if data.get("Status") == 0 and data.get("Answer"):
            return True
    return False


def _doh_json(host: str, qtype: str, timeout_s: float) -> dict:
    url = (
        "https://cloudflare-dns.com/dns-query?"
        + urllib.parse.urlencode({"name": host, "type": qtype})
    )
    req = urllib.request.Request(url, headers={"Accept": "application/dns-json"})
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _udp_query(resolver: str, payload: bytes, timeout_s: float) -> bytes:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.settimeout(timeout_s)
        sock.sendto(payload, (resolver, 53))
        data, _addr = sock.recvfrom(512)
        return data
    finally:
        sock.close()


def wait_until(
    host: str,
    *,
    resolver=query_public_dns,
    sleep=time.sleep,
    clock=time.monotonic,
    timeout_s: float = 60.0,
    interval_s: float = 2.0,
) -> bool:
    """Poll ``resolver`` at once, then every ``interval_s`` until ready."""
    deadline = clock() + timeout_s
    while True:
        if resolver(host):
            return True
        remaining = deadline - clock()
        if remaining <= 0:
            return False
        sleep(min(interval_s, remaining))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Wait until a public hostname resolves on 1.1.1.1")
    ap.add_argument("url", help="https://name.oteny.bot or the hostname")
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--interval", type=float, default=2.0)
    args = ap.parse_args(argv)

    host = hostname_from(args.url)
    if host is None:
        print("PUBLIC_URL_BAD_HOST")
        return 0
    if wait_until(host, timeout_s=args.timeout, interval_s=args.interval):
        print(f"PUBLIC_URL_READY host={host}")
    else:
        print(f"PUBLIC_URL_PENDING host={host}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
