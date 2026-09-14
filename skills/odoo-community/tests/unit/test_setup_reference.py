"""Community setup.md owns owner email, language, and the password link."""
from __future__ import annotations

from pathlib import Path

_BUNDLE = Path(__file__).resolve().parents[2]
_SETUP = (_BUNDLE / "references" / "setup.md").read_text(encoding="utf-8")
_FIRST_RUN = (_BUNDLE / "references" / "first-run.md").read_text(encoding="utf-8")
_SKILL = (_BUNDLE / "SKILL.md").read_text(encoding="utf-8")


def test_setup_exists_and_is_distinct_from_install():
    assert (_BUNDLE / "references" / "setup.md").is_file()
    assert "install_odoo.sh" not in _SETUP
    assert "setup.md" in _FIRST_RUN
    assert "references/setup.md" in _SKILL


def test_setup_owns_email_language_password():
    text = _SETUP.lower()
    assert "admin email" in text
    assert "language" in text
    assert "connect_account" in text
    assert "credential_status" in text
    assert "odoo_admin_password" in text
    assert ".odoo-admin" in text
    assert "never treat" in text and "admin" in text
    assert "ask only for that field" in text
    assert "must not re-ask" in text
    assert "send it here" not in text
    assert "paste it in chat" not in text


def test_install_drill_does_not_own_owner_facts():
    text = _FIRST_RUN.lower()
    assert "does not ask for admin" in text
    assert "connect_account" not in text


def test_setup_owns_public_url_live_recipe():
    import re
    text = re.sub(r"\s+", " ", _SETUP.lower())
    assert "public url is live" in text
    assert "wait_for_public_dns.py" in text
    assert "public_url_ready" in text
    assert "edge_reachable" in text
    assert "reachable_from_box_only" in text
    assert "do not send that url yet" in text
    assert "do not add your own sleep" in text
    assert "do not `curl`" in text or "do not curl" in text
