"""``trace()`` waits for the harvest to catch up with the reply, bounded.

The control plane's logs-pull sweep mirrors a session into Odoo after the fact. A
scenario's trace markers name the turn's last tool calls, so a trace read the
instant the record settles misses them (2026-09-17 lab: ``odoo_client`` "missing"
while the harvested session ended seven minutes before the reply).
"""

from oteny.live import LiveDriver, _reply_needle


class Poster:
    def __init__(self, reply):
        self.reply = reply

    async def __call__(self, text, timeout):
        return self.reply


def _driver(reads, reply, **kw):
    calls = {"reads": 0, "sleeps": []}
    seq = list(reads)

    def read_trace(after_session_id):
        calls["reads"] += 1
        return seq.pop(0) if len(seq) > 1 else seq[0]

    d = LiveDriver(ref="lab00003", bot_username=None, db_rel=None, exec_on_node=None,
                   dm=None, dm_timeout=30.0, post_message=Poster(reply),
                   read_trace=read_trace, sleep=calls["sleeps"].append,
                   harvest_wait_s=kw.get("wait", 60.0), harvest_poll_s=10.0)
    return d, calls


REPLY = "**Permit draft saved** for Fixture Case on Vessel Example. Reference 8f26e8df."
STALE = "# session x\n[tool] tool=browser_click landed\n"
FRESH = STALE + "[tool] tool=odoo_client {...}\n[assistant] Permit draft saved for Fixture Case on Vessel Example. Reference 8f26e8df. The desk reviews.\n"


def test_trace_waits_until_the_harvest_carries_the_reply():
    d, calls = _driver([STALE, STALE, FRESH], REPLY)
    assert d.send("go") == REPLY
    text = d.trace()
    assert text.startswith("# harvest caught up after 20 s\n")
    assert "tool=odoo_client" in text
    assert calls["reads"] == 3 and calls["sleeps"] == [10.0, 10.0]


def test_trace_names_the_lag_when_the_harvest_never_catches_up():
    d, calls = _driver([STALE], REPLY, wait=30.0)
    d.send("go")
    text = d.trace()
    assert text.startswith("# harvest lag: the reply is not in the harvested trace after 30 s\n")
    assert calls["sleeps"] == [10.0, 10.0, 10.0] and calls["reads"] == 4


def test_trace_reads_once_without_a_reply_to_wait_for():
    d, calls = _driver([STALE], "")
    assert d.trace() == STALE
    assert calls["reads"] == 1 and calls["sleeps"] == []


def test_reply_needle_skips_the_early_end_note_and_markdown():
    assert _reply_needle("\n[hand_off ended early: handback]\n**Bot:** I handed it back to the desk.") == "bot: i handed it back to the des"  # 32 chars
    assert _reply_needle("ok") == ""
