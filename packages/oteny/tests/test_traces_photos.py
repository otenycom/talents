"""`oteny traces --photos` — the author reads the pages their bot saw.

The page archive is tenant data: the platform keeps every page a bot sees on a
portal, and the author reads it back as a photo (visible text, the aim, the option
list — never the HTML). This is the author half of the self-capture loop: after a
run, the archived pages are the ground truth the Talent and the stub are fixed
against. An account key must be enough, and an older platform that has no archive
yet must answer with a note, not a failed `traces`.
"""

from __future__ import annotations

import base64
import json
import zlib

from oteny.traces import build_traces_dto, compact_photo, harvest_trace_text


def _blob(archive: dict) -> str:
    return base64.b64encode(zlib.compress(json.dumps(archive).encode())).decode()


class FakeClient:
    """Canned rows per model; records every `call` so a test can assert the seam."""

    def __init__(self, rows, *, flags=None, blobs=None, archive_field=True):
        self._rows = rows
        self._flags = flags or {}
        self._blobs = blobs or {}
        self._archive_field = archive_field
        self.calls: list[tuple] = []

    def search_read(self, model, domain, fields=None, limit=None, order=None):
        if model == "hh.browser.trace" and fields and "has_page_archive" in fields:
            if not self._archive_field:
                raise RuntimeError("HTTP 500 from hh.browser.trace/search_read: "
                                   "Invalid field 'has_page_archive'")
            return [{"id": i, "has_page_archive": bool(self._flags.get(i))}
                    for i in self._flags]
        return self._rows.get(model, [])

    def call(self, model, method, **kw):
        self.calls.append((model, method, kw))
        if method == "read_page_archive":
            return {str(i): self._blobs[i] for i in kw.get("ids", []) if i in self._blobs}
        return None


_ARCHIVE = {
    "url": "https://portal.example/step-2",
    "title": "Step 2",
    "capture_reason": "hop",
    "tool_name": "browser_click",
    "aim": 'role=combobox[name="Country"]',
    "generation": 7,
    "visible_text": "Country *\nMaak een keuze\nStreet *",
    "options": {"label": "Country", "total": 3, "virtualized": False,
                "names": ["Duitsland (EER)", "Filipijnen", "Nederland (EER)"]},
    "outer_html": "<html><body>NEVER SHOWN</body></html>",
}

_ROWS = {"hh.browser.trace": [
    {"id": 11, "kind": "page_snapshot", "page_title": "Step 2", "ok": True},
    {"id": 12, "kind": "page_snapshot", "page_title": "Step 1", "ok": True},
    {"id": 13, "kind": "click", "target_attempted": "@e5", "ok": True, "checked_state": 1},
]}


def test_photos_attach_the_compact_page_never_the_html():
    client = FakeClient(_ROWS, flags={11: True, 12: False}, blobs={11: _blob(_ARCHIVE)})
    dto = build_traces_dto(client, "hh00506", photos=True)
    rows = {t["id"]: t for t in dto["browser_traces"]}
    photo = rows[11]["photo"]
    assert photo["aim"] == 'role=combobox[name="Country"]'
    assert photo["options"]["names"] == ["Duitsland (EER)", "Filipijnen", "Nederland (EER)"]
    assert "Maak een keuze" in photo["visible_text"]
    assert "outer_html" not in photo and "NEVER SHOWN" not in json.dumps(photo)
    assert "photo" not in rows[12] and "photo" not in rows[13]
    bs = dto["browser_summary"]
    assert (bs["pages_archived"], bs["photos_attached"]) == (1, 1)
    # the blobs come through the row's own seam, once, for the archived ids only
    assert client.calls == [("hh.browser.trace", "read_page_archive", {"ids": [11]})]
    assert "archived=1 photos=1" in harvest_trace_text(dto)


def test_without_the_flag_no_archive_is_read():
    client = FakeClient(_ROWS, flags={11: True}, blobs={11: _blob(_ARCHIVE)})
    dto = build_traces_dto(client, "hh00506")
    assert client.calls == []
    assert "pages_archived" not in dto["browser_summary"]
    assert "archived=" not in harvest_trace_text(dto)


def test_an_older_platform_answers_with_a_note_not_a_failure():
    client = FakeClient(_ROWS, archive_field=False)
    dto = build_traces_dto(client, "hh00506", photos=True)
    bs = dto["browser_summary"]
    assert bs["photos_attached"] == 0
    assert "no page archive yet" in bs["photos_note"]
    assert client.calls == []


def test_compact_photo_caps_text_and_options():
    long_names = [f"Land {i}" for i in range(80)]
    photo = compact_photo({"visible_text": "x" * 5000,
                           "options": {"names": long_names, "total": 80}})
    assert len(photo["visible_text"]) == 2000 and photo["visible_text_truncated"]
    assert len(photo["options"]["names"]) == 50 and photo["options"]["names_truncated"]
