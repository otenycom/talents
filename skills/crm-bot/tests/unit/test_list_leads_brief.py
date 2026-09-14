"""list_leads.py's brief fields (plan §2): note snippet, has_photo, has_audio,
avatar — enough for a voice escalate to answer "how does Kajal look?" or
"what is on the card?" without a second round-trip through ``session_search``.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "list_leads.py"


def _load():
    spec = importlib.util.spec_from_file_location("crm_list_leads_brief_under_test", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_note_snippet_strips_html_and_collapses_whitespace():
    mod = _load()
    html = "<p><b>Captured at</b>  OXP.</p>\n<p>Summary</p>"
    assert mod._note_snippet(html) == "Captured at OXP. Summary"


def test_note_snippet_caps_length_with_ellipsis():
    mod = _load()
    long_text = "word " * 60  # well over _NOTE_CAP characters
    snippet = mod._note_snippet(long_text)
    assert len(snippet) <= mod._NOTE_CAP + 1
    assert snippet.endswith("…")


def test_note_snippet_empty_when_no_description():
    mod = _load()
    assert mod._note_snippet("") == ""
    assert mod._note_snippet(None) == ""


def test_attachment_flags_batched_by_mimetype():
    mod = _load()

    class _Rpc:
        def call(self, model, method, args=None, kwargs=None):
            assert (model, method) == ("ir.attachment", "search_read")
            assert kwargs["domain"] == [
                ("res_model", "=", "crm.lead"), ("res_id", "in", [1, 2]),
            ]
            return [
                {"res_id": 1, "mimetype": "image/jpeg"},
                {"res_id": 1, "mimetype": "audio/mp4"},
                {"res_id": 2, "mimetype": "image/png"},
            ]

    flags = mod._attachment_flags(_Rpc(), [1, 2])
    assert flags[1] == {"has_photo": True, "has_audio": True}
    assert flags[2] == {"has_photo": True, "has_audio": False}


def test_attachment_flags_empty_lead_ids_short_circuits():
    mod = _load()

    class _Rpc:
        def call(self, *a, **k):
            raise AssertionError("must not call JSON-2 with no leads")

    assert mod._attachment_flags(_Rpc(), []) == {}


def test_avatar_flags_uses_bin_size_context():
    mod = _load()

    class _Rpc:
        def call(self, model, method, args=None, kwargs=None):
            assert (model, method) == ("res.partner", "read")
            assert kwargs["context"] == {"bin_size": True}
            return [{"id": 10, "image_1920": "x"}, {"id": 11, "image_1920": False}]

    flags = mod._avatar_flags(_Rpc(), [10, 11, 0, None])
    assert flags == {10: True, 11: False}


def test_avatar_flags_empty_partner_ids_short_circuits():
    mod = _load()

    class _Rpc:
        def call(self, *a, **k):
            raise AssertionError("must not call JSON-2 with no partners")

    assert mod._avatar_flags(_Rpc(), [0, None]) == {}


def test_main_reports_note_photo_audio_and_avatar_per_lead(tmp_path, monkeypatch, capsys):
    data = tmp_path / ".hermes" / "data" / "crm-bot"
    data.mkdir(parents=True)
    (data / ".odoo-admin").write_text(
        "login=a@b.c\npassword=x\napi_key=k\n", encoding="utf-8",
    )
    monkeypatch.setenv("HH_HOME", str(tmp_path))
    mod = _load()

    def fake_json2(self, model, method, **kwargs):
        if method == "context_get":
            return {"uid": 7}
        if model == "crm.lead" and method == "search_read":
            return [{
                "id": 3, "name": "Kajal — OXP", "contact_name": "Kajal",
                "partner_name": "", "email_from": "", "phone": "",
                "function": "", "source_id": [1, "OXP"],
                "partner_id": [39, "Kajal"],
                "description": "<p>Captured at OXP.</p>",
            }]
        if model == "ir.attachment" and method == "search_read":
            return [
                {"res_id": 3, "mimetype": "image/jpeg"},
                {"res_id": 3, "mimetype": "audio/mp4"},
            ]
        if model == "res.partner" and method == "read":
            return [{"id": 39, "image_1920": False}]
        raise AssertionError(f"unexpected {model}.{method}")

    monkeypatch.setattr(mod.OdooRPC, "_json2", fake_json2)
    assert mod.main([]) == 0
    out = json.loads(capsys.readouterr().out.strip())
    assert out["count"] == 1
    row = out["leads"][0]
    assert row["lead_id"] == 3
    assert row["note"] == "Captured at OXP."
    assert row["has_photo"] is True
    assert row["has_audio"] is True
    assert row["avatar"] is False
