"""First-run ready copy offers secure intake; chat never collects a secret."""
from __future__ import annotations

import re
from pathlib import Path

_BUNDLE = Path(__file__).resolve().parents[2]
_FIRST_RUN = (_BUNDLE / "references" / "first-run.md").read_text(encoding="utf-8")
_SKILL = (_BUNDLE / "SKILL.md").read_text(encoding="utf-8")


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text).lower()


def test_ready_path_names_secure_intake_and_rejects_chat_paste():
    blob = f"{_FIRST_RUN}\n{_SKILL}".lower()
    assert "connect_account" in blob
    assert "credential_status" in blob
    assert "odoo_admin_password" in blob
    assert "setup_admin.py" in blob
    assert "--from-env" in blob
    assert "don't have a password" in blob
    assert "send it here" not in blob
    assert "paste it in chat" not in blob
    assert "will not repeat it" not in blob
    assert "won't repeat it" not in blob


def test_first_run_ready_sentence_offers_the_link_in_the_same_turn():
    text = _FIRST_RUN.lower()
    assert "same message" in text or "same turn" in text
    assert "secure password link" in text
    assert "optional" in text  # first-lead walk-through stays optional


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
    prompt = _flat(profile[start:end])
    assert "tell me about" not in prompt
    assert "do not recite the command table" not in prompt
    assert "about this talent" not in prompt
