"""Authoring fixture: type readback timeout pins peek, not snapshot or retype.

The wrap reports ``_TYPE_READBACK_TIMEOUT: readback timed out; write not
confirmed.`` when the 3 s probe dies. That string does not say empty.
An unscoped bot will retype or call ``browser_snapshot``. The author
rule must name one next step.
"""

from __future__ import annotations

from pathlib import Path

REFS = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "talent-authoring-standard"
    / "references"
)
_TIMEOUT = "_TYPE_READBACK_TIMEOUT: readback timed out; write not confirmed."
_AUTHOR_DOCS = (
    REFS / "browser-authoring.md",
    REFS / "business-bot-pattern.md",
)


def _paragraph_with(text: str, token: str) -> str:
    for para in text.split("\n\n"):
        if token in para:
            return " ".join(para.split())
    raise AssertionError(f"missing {token!r}")


def test_timeout_class_does_not_prescribe_snapshot_or_immediate_retype():
    for path in _AUTHOR_DOCS:
        assert path.is_file(), path
        para = _paragraph_with(path.read_text(), _TIMEOUT)
        assert _TIMEOUT in para
        assert "do not retype" in para.lower()
        assert "Retype only if" in para
        assert "Do not call `browser_snapshot` for this class" in para
        assert "retype immediately" not in para.lower()
        assert "call `browser_snapshot` then" not in para.lower()
