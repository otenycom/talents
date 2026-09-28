"""Web chat transport (offline) — ``oteny test`` talks to a web bot over the relay.

A web bot's conversation lane is the web chat relay, the lane its owner uses. These tests
run a fake relay that speaks the relay's frame protocol (ready, resume, send, then the
turn's frames keyed by ``send_id``) and prove the poster asks the chat app for a ticket
with the author's own key, reads exactly its own turn, and fails with the relay's reason.
"""
from __future__ import annotations

import asyncio
import json
from urllib.parse import parse_qs, urlsplit

import pytest
from websockets.asyncio.server import serve

from oteny.web_transport import WebLaneError, WebPoster


class _Relay:
    def __init__(self, reply: str | None = "Welcome back."):
        self.reply = reply
        self.tickets: list[str] = []
        self.features: list[str] = []
        self.user_agents: list[str] = []
        self.sent: list[dict] = []

    async def handler(self, ws):
        query = parse_qs(urlsplit(ws.request.path).query)
        self.tickets.append(query["t"][0])
        self.features.append(query["features"][0])
        self.user_agents.append(ws.request.headers.get("User-Agent", ""))
        await ws.send(json.dumps({"type": "ready", "epoch": "e1"}))
        async for raw in ws:
            frame = json.loads(raw)
            if frame["type"] == "resume":
                await ws.send(json.dumps({"type": "resume.done"}))
            elif frame["type"] == "send":
                self.sent.append(frame)
                await self._answer(ws, frame["id"], frame["ch"])

    async def _answer(self, ws, sid: str, ch: str):
        if self.reply is None:
            await ws.send(json.dumps({"type": "error", "ch": ch, "id": sid,
                                      "code": "upstream_unavailable", "scope": "send"}))
            return
        for frame in (
            {"type": "ack", "ch": ch, "id": sid},
            {"type": "run.started", "ch": ch, "send_id": sid},
            # A neighbour turn on the same chat must not leak into this read.
            {"type": "assistant.delta", "ch": ch, "send_id": "other", "delta": "NOT MINE "},
            {"type": "assistant.delta", "ch": ch, "send_id": sid, "delta": self.reply[:5]},
            {"type": "assistant.completed", "ch": ch, "send_id": sid,
             "content": self.reply},
            {"type": "run.completed", "ch": ch, "send_id": sid},
        ):
            await ws.send(json.dumps(frame))


class _Odoo:
    """The author's account client: the chat app's ticket seam only."""

    def __init__(self, ws_url: str, answer: dict | None = None):
        self.ws_url = ws_url
        self.answer = answer
        self.calls: list = []

    def call(self, model, method, **kw):
        self.calls.append((model, method, kw))
        if self.answer is not None:
            return self.answer
        return {"ok": True, "ticket": f"tkt-{len(self.calls)}", "ws_url": self.ws_url}


def _with_relay(relay: _Relay, body):
    async def main():
        async with serve(relay.handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            return await body(f"ws://127.0.0.1:{port}/v1/webchat/ws")
    return asyncio.run(main())


def test_one_turn_returns_exactly_this_turns_reply():
    relay = _Relay()

    async def body(url):
        odoo = _Odoo(url)
        reply = await WebPoster(odoo, ch=17)("Hello!", 30)
        return reply, odoo.calls

    reply, calls = _with_relay(relay, body)
    assert reply == "Welcome back."
    assert calls == [("oteny.webchat.app", "mint_webchat_ticket", {"channel_id": 17})]
    sent = relay.sent[0]
    assert (sent["ch"], sent["text"], sent["sid"]) == ("17", "Hello!", "")
    assert relay.tickets == ["tkt-1"]
    assert relay.features == ["gateway-frames/1"]
    # The same browser-shaped agent the /json/2/ client sends past the edge.
    assert relay.user_agents[0].startswith("Mozilla/5.0")


def test_each_turn_mints_a_fresh_ticket():
    relay = _Relay()

    async def body(url):
        poster = WebPoster(_Odoo(url), ch=17)
        await poster("one", 30)
        await poster("two", 30)

    _with_relay(relay, body)
    assert relay.tickets == ["tkt-1", "tkt-2"]


def test_a_turn_the_relay_refuses_raises_with_its_code():
    relay = _Relay(reply=None)

    async def body(url):
        await WebPoster(_Odoo(url), ch=17)("Hello!", 30)

    with pytest.raises(WebLaneError, match="upstream_unavailable"):
        _with_relay(relay, body)


def test_a_refused_ticket_is_an_error_before_any_socket():
    relay = _Relay()

    async def body(url):
        await WebPoster(_Odoo(url, answer={"ok": False, "error": "building"}), ch=17)("hi", 30)

    with pytest.raises(WebLaneError, match="building"):
        _with_relay(relay, body)
    assert relay.tickets == []


def test_a_hand_off_step_is_refused_with_a_reason():
    poster = WebPoster(_Odoo("ws://unused"), ch=1)
    with pytest.raises(RuntimeError, match="hand_off"):
        asyncio.run(poster.wait_for_reply(0, 1))
