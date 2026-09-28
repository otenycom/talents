"""Which lane ``oteny test --transport auto`` uses to talk to a bot.

A web bot (a dev branch's dev bot) carries an uplink to Oteny's own record plane for web
chat, and no Discuss channel. That uplink is no lane a test can drive, so auto must pick
the CLI lane for it, not Discuss. The platform's own runner makes the same choice.
"""
from __future__ import annotations

import pytest

from oteny.runner import transport_for


@pytest.mark.parametrize("rec, requested, lane", [
    ({"bot_username": "acme_bot"}, "auto", "telegram"),
    ({"discuss_channel_id": 8, "uplink_url": "https://crm.example"}, "auto", "discuss"),
    # A business bot whose channel comes from tests/discuss.yaml on its ERP uplink.
    ({"uplink_url": "https://crm.example", "channel": "telegram"}, "auto", "discuss"),
    # A web dev bot: the uplink is Oteny's record plane, and there is no Discuss channel.
    ({"uplink_url": "https://oteny.odoo.com", "channel": "web"}, "auto", "cli"),
    ({}, "auto", "cli"),
    ({"discuss_channel_id": 8}, "cli", "cli"),
    ({"channel": "web"}, "discuss", "discuss"),
])
def test_auto_picks_the_lane_the_bot_can_answer_on(rec, requested, lane):
    assert transport_for(rec, requested, uplink_url=rec.get("uplink_url") or "") == lane
