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
    assert "trade show" in pitch
    assert "voice" in pitch
    assert "photo" in pitch
    assert "delete lead 42" in pitch  # named as the pit, not as the answer


def test_channel_prompt_answers_tell_me_about_with_the_value_story():
    profile = (_BUNDLE / "agent-profile.yaml").read_text(encoding="utf-8")
    prompt = _flat(profile)
    assert "about this talent" in prompt
    assert "tell me about" in prompt
    assert "trade show" in prompt
    assert "voice" in prompt
    assert "do not recite the command table" in prompt
