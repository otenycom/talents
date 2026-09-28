"""Which lane ``oteny test --transport auto`` uses to talk to a bot.

A web bot (a dev branch's dev bot) carries an uplink to Oteny's own record plane for web
chat, and no Discuss channel. That uplink is no lane a test can post into. The bot's
conversation lane is the web chat relay its owner uses, so auto picks the web lane for
it, not Discuss. The platform's own staging runner makes the same choice.
"""
from __future__ import annotations

import pytest

from oteny.runner import _web_poster, transport_for
from oteny.web_transport import WebPoster


@pytest.mark.parametrize("rec, requested, lane", [
    ({"bot_username": "acme_bot"}, "auto", "telegram"),
    ({"discuss_channel_id": 8, "uplink_url": "https://crm.example"}, "auto", "discuss"),
    # A business bot whose channel comes from tests/discuss.yaml on its ERP uplink.
    ({"uplink_url": "https://crm.example", "channel": "telegram"}, "auto", "discuss"),
    # A web dev bot: the uplink is Oteny's record plane, and there is no Discuss channel.
    ({"uplink_url": "https://oteny.odoo.com", "channel": "web"}, "auto", "web"),
    ({}, "auto", "cli"),
    ({"discuss_channel_id": 8}, "cli", "cli"),
    ({"channel": "web"}, "discuss", "discuss"),
    ({"channel": "web"}, "cli", "cli"),
    ({"discuss_channel_id": 8}, "web", "web"),
])
def test_auto_picks_the_lane_the_bot_can_answer_on(rec, requested, lane):
    assert transport_for(rec, requested, uplink_url=rec.get("uplink_url") or "") == lane


def test_the_web_lane_talks_in_the_bots_dm():
    poster = _web_poster(object(), {"ref": "hh00042", "web_dm_channel_id": [18, "dm"]})
    assert isinstance(poster, WebPoster)
    assert poster._ch == "18"


def test_a_web_bot_with_no_dm_is_refused_with_a_reason():
    with pytest.raises(RuntimeError, match="no web chat DM"):
        _web_poster(object(), {"ref": "hh00042", "web_dm_channel_id": False})
