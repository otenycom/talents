"""CLI / terminal transport — hermes chat oneshot over AuthorBoxAccess.shell."""
from __future__ import annotations

import asyncio
import shlex
import time


def hermes_oneshot_cmd(text: str) -> str:
    """Non-interactive one-shot chat on the bot box (hermes chat -z)."""
    # -z/--oneshot: single turn, print reply, exit (hermes-agent CLI).
    return (
        f"cd ~ && hermes chat -z -- {shlex.quote(text)} 2>/dev/null "
        f"|| hermes --oneshot {shlex.quote(text)} 2>/dev/null"
    )


class CliPoster:
    """Duck-typed like DiscussPoster for plain ``user:`` turns (not hand_off)."""

    def __init__(self, exec_fn, *, timeout_s: float = 180.0):
        self._exec = exec_fn
        self._timeout = timeout_s

    async def __call__(self, text: str, timeout: float) -> str:
        wait = timeout or self._timeout
        cmd = hermes_oneshot_cmd(text)
        out = await asyncio.wait_for(
            asyncio.to_thread(self._exec, cmd), timeout=wait)
        return (out or "").strip()

    async def latest_message_id(self) -> int:
        return int(time.time())

    async def wait_for_reply(self, after_id: int, timeout: float) -> str:
        raise RuntimeError(
            "CLI transport has no channel wait — hand_off needs Discuss")
