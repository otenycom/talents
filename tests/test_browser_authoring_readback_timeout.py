"""Authoring fixture: type confirm pins host grade, not a hollow peek.

The wrap reports ``confirm`` / ``confirm_text``. ``unseen`` uses
``set value could not be verified``. That class is not empty.
An unscoped bot will retype or call ``browser_snapshot``. The author
rule must name one next step per class.
"""

from __future__ import annotations

from pathlib import Path

REFS = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "talent-authoring-standard"
    / "references"
)
_UNSEEN = "set value could not be verified"
_MATCH = "set value matches input"
_DIFFER = "set value differs from input"
_OLD_TIMEOUT = "_TYPE_READBACK_TIMEOUT: readback timed out; write not confirmed."
_AUTHOR_DOCS = (
    REFS / "browser-authoring.md",
    REFS / "business-bot-pattern.md",
)


def _paragraph_with(text: str, token: str) -> str:
    for para in text.split("\n\n"):
        if token in para:
            return " ".join(para.split())
    raise AssertionError(f"missing {token!r}")


def test_confirm_class_does_not_prescribe_snapshot_or_immediate_retype():
    for path in _AUTHOR_DOCS:
        assert path.is_file(), path
        body = path.read_text()
        assert _OLD_TIMEOUT not in body
        para = _paragraph_with(body, _UNSEEN)
        assert _MATCH in para
        assert _DIFFER in para
        assert _UNSEEN in para
        assert "do not retype" in para.lower()
        assert "Do not call `browser_snapshot` for this class" in para
        assert "look at that one value" in para
        assert "retype immediately" not in para.lower()
        assert "call `browser_snapshot` then" not in para.lower()
        assert "Retype only if" not in para
