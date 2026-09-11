"""WebsiteBot ready copy offers secure intake; chat never collects a secret."""
from __future__ import annotations

import re
from pathlib import Path

_BUNDLE = Path(__file__).resolve().parents[2]
_SKILL = (_BUNDLE / "SKILL.md").read_text(encoding="utf-8")
_FIRST_RUN = (_BUNDLE / "references" / "first-run.md").read_text(encoding="utf-8")
_HANDOFF = (_BUNDLE / "references" / "build-and-host.md").read_text(encoding="utf-8")


def test_ready_sentence_stays_and_offers_secure_intake():
    assert (
        "Postgres and Odoo are up. Your website engine is ready — what should the site say?"
        in _FIRST_RUN
    )
    blob = f"{_FIRST_RUN}\n{_HANDOFF}".lower()
    assert "connect_account" in blob
    assert "credential_status" in blob
    assert "odoo_admin_password" in blob
    assert "don't have a password" in blob
    assert "send it here" not in blob
    assert "paste it in chat" not in blob
    assert "will not repeat it" not in blob
    assert "won't repeat it" not in blob


def test_about_this_talent_sits_above_the_command_table():
    about = _SKILL.index("## About this Talent")
    table = _SKILL.index("## What the owner types")
    assert about < table
    pitch = _SKILL[about:table].lower()
    assert "website" in pitch
    assert "chat" in pitch
    assert "start intake" in pitch


def test_channel_prompt_does_not_route_what_can_you_do_to_intake():
    profile = (_BUNDLE / "agent-profile.yaml").read_text(encoding="utf-8")
    prompt = re.sub(r"\s+", " ", profile).lower()
    assert "about this talent" in prompt
    assert "what can you do" in prompt
    assert "do not start intake" in prompt
    # The old standing instruction sent "what can you do?" into first-run.
    assert 'or "what can you do?": first' not in prompt
