"""WebsiteBot ready copy offers secure intake; chat never collects a secret."""
from __future__ import annotations

import re
from pathlib import Path

_BUNDLE = Path(__file__).resolve().parents[2]
_SKILL = (_BUNDLE / "SKILL.md").read_text(encoding="utf-8")
_FIRST_RUN = (_BUNDLE / "references" / "first-run.md").read_text(encoding="utf-8")
_HANDOFF = (_BUNDLE / "references" / "build-and-host.md").read_text(encoding="utf-8")


def _about_stamp(text: str) -> str:
    start = text.index("## About this Talent")
    rest = text[start:]
    end = len(rest)
    for marker in ("\nYou are the owner's", "\n## "):
        idx = rest.find(marker, 1)
        if idx != -1:
            end = min(end, idx)
    return rest[:end]


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


def test_about_this_talent_is_one_short_value_paragraph():
    about = _SKILL.index("## About this Talent")
    table = _SKILL.index("## What the owner types")
    assert about < table
    pitch = _about_stamp(_SKILL).lower()
    assert "website" in pitch
    assert "chat" in pitch
    assert "start intake" not in pitch
    assert "tell me about" not in pitch
    assert "do not recite" not in pitch
    assert "pit of failure" not in pitch


def test_channel_prompt_does_not_route_what_can_you_do_to_intake():
    profile = (_BUNDLE / "agent-profile.yaml").read_text(encoding="utf-8")
    prompt = re.sub(r"\s+", " ", profile).lower()
    assert "do not recite the command table" not in prompt
    assert "about this talent:" not in prompt
    assert "tell me about" not in prompt
    # The old standing instruction sent "what can you do?" into first-run.
    assert 'or "what can you do?": first' not in prompt
