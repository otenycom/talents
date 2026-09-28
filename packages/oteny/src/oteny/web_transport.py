"""Web chat transport — one scenario turn over Oteny's web chat relay, as the bot's owner.

A web bot (a dev branch's dev bot) has no Telegram name and no Discuss channel. Its
conversation lane is the web chat relay, the same lane its owner uses in the chat app,
so ``oteny test`` talks to it there. Each turn asks the chat app for a fresh ticket with
the author's own account key (``oteny.webchat.app.mint_webchat_ticket``), opens one relay
socket, binds the bot's DM, sends the turn, and reads the frames of that turn alone (the
relay keys a gateway-lane turn by ``send_id``) until ``run.completed``.

The platform's staging runner speaks the same protocol from
``hermeshost.webchat_lane``. The two stay in step by behaviour, not by import: this
package never imports the platform.
"""
from __future__ import annotations

import asyncio
import json
import time

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from .client import _BROWSER_UA

GATEWAY_FRAMES_FEATURE = "gateway-frames/1"
# Turn-scoped frame types carry the turn's send_id (``id`` for ack and error); every other
# type belongs to every turn of the chat (the relay's wire contract, W.3.1).
_TURN_SCOPED = frozenset({
    "run.started", "run.completed", "assistant.delta", "assistant.replace",
    "assistant.completed", "tool.started", "tool.completed", "tool.failed", "thinking",
    "message", "prompt", "prompt.resolved", "card", "media", "control.ack",
    "user.message", "ack", "error",
})
_SETUP_TIMEOUT_S = 15.0


class WebLaneError(RuntimeError):
    """The chat app or the relay refused the turn; the message carries the reason code."""


def _ours(frame: dict, ch: str, send_id: str) -> bool:
    if frame.get("ch") not in (None, ch):
        return False
    if str(frame.get("type") or "") not in _TURN_SCOPED:
        return True
    marker = frame.get("send_id")
    if marker is None:
        marker = frame.get("id")
    return str(marker or "") == send_id


class WebPoster:
    """Duck-typed like DiscussPoster: one plain ``user:`` turn per call (not hand_off)."""

    def __init__(self, client, *, ch: int | str, sid: str = ""):
        self._client = client
        self._ch = str(ch)
        self._sid = sid
        self._turns = 0

    def _mint(self) -> tuple[str, str]:
        out = self._client.call("oteny.webchat.app", "mint_webchat_ticket",
                                channel_id=int(self._ch))
        if not out or not out.get("ok"):
            raise WebLaneError(f"ticket refused: {(out or {}).get('error') or 'no answer'}")
        return out["ticket"], out["ws_url"]

    async def __call__(self, text: str, timeout: float) -> str:
        # A ticket upgrades one socket within 45 s, and a scenario's turns can be minutes
        # apart, so every turn mints its own.
        ticket, ws_url = await asyncio.to_thread(self._mint)
        self._turns += 1
        send_id = f"s{int(time.time() * 1000)}-oteny{self._turns:03d}"
        deadline = time.monotonic() + (timeout or 180.0)
        url = f"{ws_url}?t={ticket}&features={GATEWAY_FRAMES_FEATURE}"
        async with connect(url, user_agent_header=_BROWSER_UA,
                           open_timeout=_SETUP_TIMEOUT_S, ping_interval=20) as ws:
            await self._expect(ws, "ready", _SETUP_TIMEOUT_S)
            await ws.send(json.dumps({"type": "resume", "cursors": [
                {"ch": self._ch, "sid": self._sid, "last_seq": 0}]}))
            await self._expect(ws, "resume.done", _SETUP_TIMEOUT_S)
            await ws.send(json.dumps({"type": "send", "id": send_id, "text": text,
                                      "ch": self._ch, "sid": self._sid}))
            return await self._read_turn(ws, send_id, deadline)

    async def _expect(self, ws, kind: str, timeout: float) -> dict:
        end = time.monotonic() + timeout
        while True:
            frame = await self._next(ws, end - time.monotonic())
            if frame.get("type") == kind:
                return frame

    @staticmethod
    async def _next(ws, wait: float) -> dict:
        if wait <= 0:
            raise WebLaneError("deadline: the relay sent no frame in time")
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=wait)
        except asyncio.TimeoutError as exc:
            raise WebLaneError("deadline: the relay sent no frame in time") from exc
        except ConnectionClosed as exc:
            code = exc.rcvd.code if exc.rcvd else "no close frame"
            raise WebLaneError(f"socket_closed: {code}") from exc
        try:
            frame = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return {}
        return frame if isinstance(frame, dict) else {}

    async def _read_turn(self, ws, send_id: str, deadline: float) -> str:
        content = ""
        while True:
            frame = await self._next(ws, deadline - time.monotonic())
            if not _ours(frame, self._ch, send_id):
                continue
            kind = frame.get("type")
            if kind == "assistant.delta":
                content += str(frame.get("delta") or "")
            elif kind in ("assistant.replace", "assistant.completed"):
                content = str(frame.get("content") or content)
            elif kind == "error" and frame.get("scope") in (None, "send"):
                raise WebLaneError(str(frame.get("code") or "error"))
            elif kind == "run.completed":
                return content.strip()

    async def latest_message_id(self) -> int:
        return int(time.time())

    async def wait_for_reply(self, after_id: int, timeout: float) -> str:
        raise RuntimeError("the web lane has no channel wait for a later reply; a "
                           "hand_off step needs Discuss")
