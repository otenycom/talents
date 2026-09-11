"""First-run ready copy offers secure intake; chat never collects a secret."""
from __future__ import annotations

import re
from pathlib import Path

_BUNDLE = Path(__file__).resolve().parents[2]
_FIRST_RUN = (_BUNDLE / "references" / "first-run.md").read_text(encoding="utf-8")
_SKILL = (_BUNDLE / "SKILL.md").read_text(encoding="utf-8")


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text).lower()


def _about_stamp(text: str) -> str:
    start = text.index("## About this Talent")
    rest = text[start:]
    end = len(rest)
    for marker in ("\nYou are the owner's", "\nDetail:", "\n## "):
        idx = rest.find(marker, 1)
        if idx != -1:
            end = min(end, idx)
    return rest[:end]


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


def test_about_this_talent_is_one_short_value_paragraph():
    about = _SKILL.index("## About this Talent")
    table = _SKILL.index("## What the owner types")
    assert about < table
    pitch = _about_stamp(_SKILL).lower()
    assert "trade show" in pitch
    assert "voice" in pitch
    assert "photo" in pitch
    assert "tell me about" not in pitch
    assert "do not recite" not in pitch
    assert "pit of failure" not in pitch
    assert "you are the owner's" not in pitch


def test_channel_prompt_has_no_about_meta():
    profile = (_BUNDLE / "agent-profile.yaml").read_text(encoding="utf-8")
    prompt = _flat(profile)
    assert "do not recite the command table" not in prompt
    assert "tell me about" not in prompt
    assert "about this talent" not in prompt
    assert "builds on" in prompt
    assert "do not start" in prompt
