"""First-run ready copy offers secure intake; chat never collects a secret."""
from __future__ import annotations

import re
from pathlib import Path

_BUNDLE = Path(__file__).resolve().parents[2]
_FIRST_RUN = (_BUNDLE / "references" / "first-run.md").read_text(encoding="utf-8")
_SKILL = (_BUNDLE / "SKILL.md").read_text(encoding="utf-8")
_COMMUNITY_SETUP = (
    Path(__file__).resolve().parents[3]
    / "odoo-community"
    / "references"
    / "setup.md"
).read_text(encoding="utf-8")


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text).lower()


def test_ready_path_names_secure_intake_and_rejects_chat_paste():
    blob = f"{_FIRST_RUN}\n{_SKILL}\n{_COMMUNITY_SETUP}".lower()
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


def test_first_run_asks_once_and_does_not_confirm_install():
    text = _FIRST_RUN.lower()
    assert 'do not ask "shall i install?"' in text
    assert "explicit yes" not in text
    assert "ask only for that field" in text
    assert "host_website" in text
    assert "do not ask" in text
    assert "public url is live" in text
    assert "public_url_ready" in text
    assert "edge_reachable" in text
    assert "provisioning" in text


def test_first_run_loads_community_owner_setup():
    text = _FIRST_RUN.lower()
    assert "odoo-community" in text
    assert "references/setup.md" in text
    assert "skill_view" in text
    assert "you also need admin email and language" not in text
    assert "ask those three together" not in text
    assert "event name is crmbot-specific" in text


def test_first_run_splits_cold_and_warm():
    text = _FIRST_RUN.lower()
    assert "cold" in text
    assert "warm" in text
    assert "install_modules.sh crm" in text
    assert "pin_crm_home.py" in text
    assert "crm_home_pinned" in text
    assert "do not run `install_odoo.sh`" in text or "do not run install_odoo.sh" in text
    assert "event name" in text
    assert "admin_file" in text
    prompt = (_BUNDLE / "agent-profile.yaml").read_text(encoding="utf-8").lower()
    assert "and yes" not in prompt
    assert "hard stop until this turn has an email" not in prompt
    assert "warm box" in prompt
    assert "install_modules.sh crm" in prompt
    assert "pin_crm_home.py" in prompt


def test_about_this_talent_sits_above_the_command_table():
    about = _SKILL.index("## About this Talent")
    table = _SKILL.index("## What the owner types")
    assert about < table
    pitch = _SKILL[about:table].lower()
    assert "tell me about" not in pitch
    assert "you are the owner" not in pitch


def test_hot_path_is_one_skill_file():
    assert not (_BUNDLE / "references" / "capture.md").exists()
    assert not (_BUNDLE / "references" / "lessons.md").exists()
    assert (_BUNDLE / "references" / "first-run.md").is_file()
    text = _SKILL.lower()
    assert "capture.md" not in text
    assert "lessons.md" not in text
    assert "upsert_lead.py" in text
    assert "list_leads.py" in text
    assert "crm_home: discuss" in text
    assert "pin_crm_home.py" in text
    assert "do not `skill_view`" in text or "do not skill_view" in text
    assert "do not `read_file`" in text or "do not read_file" in text
    assert "bare personal name" in text
    assert "name-only" in text
    assert "partner_id" in text
    assert '"correction": true' in _SKILL
    assert "overwrite the lead card" in text
    assert "rewrites" in text and "notes" in text
    assert "no `correction`" in text or "no correction" in text
    prompt = (_BUNDLE / "agent-profile.yaml").read_text(encoding="utf-8").lower()
    assert "list_leads.py" in prompt
    assert "upsert_lead.py" in prompt


def test_channel_prompt_does_not_stamp_how_to_answer_about():
    profile = (_BUNDLE / "agent-profile.yaml").read_text(encoding="utf-8")
    start = profile.index("channel_prompt:")
    end = profile.index("signature:", start)
    prompt = _flat(profile[start:end])
    assert "tell me about" not in prompt
    assert "do not recite the command table" not in prompt
    assert "about this talent" not in prompt
