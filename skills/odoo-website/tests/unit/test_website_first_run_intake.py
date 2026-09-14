"""WebsiteBot ready copy offers secure intake; chat never collects a secret."""
from __future__ import annotations

import re
from pathlib import Path

_BUNDLE = Path(__file__).resolve().parents[2]
_SKILL = (_BUNDLE / "SKILL.md").read_text(encoding="utf-8")
_FIRST_RUN = (_BUNDLE / "references" / "first-run.md").read_text(encoding="utf-8")
_HANDOFF = (_BUNDLE / "references" / "build-and-host.md").read_text(encoding="utf-8")
_COMMUNITY_SETUP = (
    Path(__file__).resolve().parents[3]
    / "odoo-community"
    / "references"
    / "setup.md"
).read_text(encoding="utf-8")


def test_ready_sentence_stays_and_offers_secure_intake():
    assert (
        "Postgres and Odoo are up. Your website engine is ready — what should the site say?"
        in _FIRST_RUN
    )
    blob = f"{_FIRST_RUN}\n{_HANDOFF}\n{_COMMUNITY_SETUP}".lower()
    assert "connect_account" in blob
    assert "credential_status" in blob
    assert "odoo_admin_password" in blob
    assert "don't have a password" in blob
    assert "send it here" not in blob
    assert "paste it in chat" not in blob
    assert "will not repeat it" not in blob
    assert "won't repeat it" not in blob


def test_host_waits_for_public_url_live():
    blob = re.sub(r"\s+", " ", f"{_SKILL}\n{_HANDOFF}\n{_COMMUNITY_SETUP}".lower())
    assert "public url is live" in blob
    assert "wait_for_public_dns.py" in blob
    assert "edge_reachable" in blob
    assert "do not give the url yet" in blob


def test_first_run_loads_community_owner_setup():
    text = _FIRST_RUN.lower()
    assert "odoo-community" in text
    assert "references/setup.md" in text
    assert "skill_view" in text
    assert "do **not** ask admin email" in text
    assert "an email** for the site's admin login" not in text
    assert "language** and **timezone" not in text


def test_about_this_talent_sits_above_the_command_table():
    about = _SKILL.index("## About this Talent")
    table = _SKILL.index("## What the owner types")
    assert about < table
    pitch = _SKILL[about:table].lower()
    assert "tell me about" not in pitch
    assert "you are the owner" not in pitch


def test_channel_prompt_does_not_stamp_how_to_answer_about():
    profile = (_BUNDLE / "agent-profile.yaml").read_text(encoding="utf-8")
    start = profile.index("channel_prompt:")
    end = profile.index("signature:", start)
    prompt = re.sub(r"\s+", " ", profile[start:end]).lower()
    assert "tell me about" not in prompt
    assert "do not start intake" not in prompt
    assert "about this talent" not in prompt
    # The old standing instruction sent "what can you do?" into first-run.
    assert 'or "what can you do?": first' not in prompt
    assert "odoo-community references/setup.md" in prompt
