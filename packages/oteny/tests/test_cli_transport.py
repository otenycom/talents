"""CLI oneshot transport (offline)."""
from __future__ import annotations

import asyncio

from oteny.cli_transport import CliPoster, hermes_oneshot_cmd


def test_hermes_oneshot_cmd_quotes():
    cmd = hermes_oneshot_cmd('hello "world"')
    assert "hermes chat -z" in cmd
    assert "hello" in cmd


def test_cli_poster_send():
    def fake_exec(cmd: str) -> str:
        assert "hermes" in cmd
        return "bot says hi\n"

    poster = CliPoster(fake_exec)
    reply = asyncio.run(poster("ping", 30))
    assert reply == "bot says hi"


def test_cli_poster_no_hand_off_wait():
    poster = CliPoster(lambda c: "")
    try:
        asyncio.run(poster.wait_for_reply(0, 1))
        raise AssertionError("expected error")
    except RuntimeError as e:
        assert "hand_off" in str(e)
