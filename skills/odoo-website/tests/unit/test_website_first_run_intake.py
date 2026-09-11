"""WebsiteBot ready copy offers secure intake; chat never collects a secret."""
from __future__ import annotations

from pathlib import Path

_BUNDLE = Path(__file__).resolve().parents[2]
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
