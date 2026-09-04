"""The author-facing `oteny traces` summary — parity with the platform's own verb.

An author holding nothing but an account key has to be able to answer "what did my
bot click, and did it stick" from this DTO alone. That is the dog-food bar, and it
is what the 2026-08-25 off-viewport halt failed: the run reported success on a
radio that never checked, and only an operator box shell could see it.
"""

from __future__ import annotations

import json

from oteny.traces import (MESSAGE_WINDOW, _enrich_browser_trace_row, build_traces_dto,
                          harvest_trace_text)


class FakeClient:
    """Returns canned rows per model, so the shaping is exercised offline."""

    def __init__(self, rows):
        self._rows = rows

    def search_read(self, model, domain, fields=None, limit=None, order=None):
        return self._rows.get(model, [])


def _dto(browser_rows):
    return build_traces_dto(FakeClient({"hh.browser.trace": browser_rows}), "hh00506")


def test_summary_counts_native_action_rows():
    dto = _dto([
        {"kind": "click", "target_attempted": "@e50", "el_id": "informeren_ja",
         "ok": True, "checked_state": 1},
        {"kind": "type", "target_attempted": "@e9", "el_id": "bsn",
         "ok": True, "checked_state": -1, "value_matched": 1},
    ])
    bs = dto["browser_summary"]
    assert bs["actions"] == 2
    assert bs["click_no_ops"] == 0
    # a ref-click has no locator count — it must not be counted as a miss
    assert bs["misses"] == 0 and bs["ambiguous"] == 0


def test_summary_named_actions_are_not_misses_and_clicks_carry_no_value():
    """A named click or type carries match_count 0 and a click carries no value.
    A miss is a FAILED step with nothing matched; a value mismatch needs a step
    that set a value. Otherwise a clean named walk reads as all misses."""
    dto = _dto([
        {"kind": "click", "target_attempted": 'role=combobox[name="Sector"]',
         "match_count": 0, "ok": True, "checked_state": -1, "value_matched": 0},
        {"kind": "type", "target_attempted": 'role=textbox[name="Street *"]',
         "match_count": 0, "ok": True, "checked_state": -1, "value_matched": 1},
        {"kind": "type", "target_attempted": 'role=textbox[name*="End date"]',
         "match_count": 0, "ok": False, "checked_state": -1, "value_matched": 0,
         "error": "set value could not be verified"},
    ])
    bs = dto["browser_summary"]
    assert (bs["actions"], bs["misses"], bs["value_mismatches"], bs["failed"]) == (3, 1, 1, 1)


def test_summary_surfaces_the_click_that_reported_success_and_stuck_nothing():
    dto = _dto([
        {"kind": "click", "target_attempted": "@e51", "el_id": "informeren_nee",
         "ok": True, "checked_state": 0},
    ])
    assert dto["browser_summary"]["click_no_ops"] == 1
    assert dto["browser_summary"]["failed"] == 0  # the TOOL succeeded — that is the point
    assert "click_no_ops=1" in harvest_trace_text(dto)


def test_summary_reports_the_captured_inventory():
    inv = [{"tag": "input", "type": "radio", "name": "informeren",
            "label": "Nee", "checked": True},
           {"tag": "input", "type": "text", "id": "bsn",
            "value_len": 9, "value_sha": "deadbeefdeadbeef"}]
    dto = _dto([{"kind": "page_snapshot", "page_url": "https://stub/type",
                 "has_snapshot": True,
                 "snapshot_pretty": json.dumps({"form_inventory": inv, "url": "u"})}])
    bs = dto["browser_summary"]
    assert bs["pages_captured"] == 1
    assert bs["controls_captured"] == 2
    # the inventory is promoted out of the zlib payload for the author to read
    assert dto["browser_traces"][0]["form_inventory"] == inv
    # and it answers "which radio is checked" without any box access
    radio = dto["browser_traces"][0]["form_inventory"][0]
    assert radio["checked"] is True
    # no raw value ever appears — only the fingerprint
    assert "value" not in dto["browser_traces"][0]["form_inventory"][1]


def test_enrichment_is_inert_on_a_step_row_and_on_junk():
    step = {"kind": "click", "target_attempted": "@e1"}
    assert _enrich_browser_trace_row(step) == step
    for raw in (None, "", "   ", "not json", json.dumps([1, 2])):
        row = {"kind": "page_snapshot", "snapshot_pretty": raw}
        assert "form_inventory" not in _enrich_browser_trace_row(row)


def test_summary_is_all_zero_for_a_bot_that_never_browsed():
    bs = _dto([])["browser_summary"]
    assert bs == {"actions": 0, "misses": 0, "ambiguous": 0, "value_mismatches": 0,
                  "click_no_ops": 0, "failed": 0, "pages_captured": 0,
                  "controls_captured": 0}


class RecordingClient(FakeClient):
    """Records the query each model got, so the window and its order are asserted."""

    def __init__(self, rows):
        super().__init__(rows)
        self.queries = []
        self.domains = []

    def search_read(self, model, domain, fields=None, limit=None, order=None):
        self.queries.append((model, limit, order))
        self.domains.append((model, domain))
        return super().search_read(model, domain, fields, limit, order)


def test_window_is_the_walk_newest_first_and_rendered_in_order():
    """A draft walk is about 100 model calls with a tool result each. The window
    reads the newest 300 rows so the end of the walk is never cut off, and renders
    them oldest first; a tool result keeps 800 characters so a click's own
    ``picked`` / ``resolved_by`` lines survive the preview."""
    long_result = "x" * 900
    client = RecordingClient({
        "hh.hermes.session": [{"id": 9, "source_session_id": "20260904_1", "display_label": "l",
                               "started_at": "2026-09-04 16:05:41"}],
        # the client answers newest first, as ``order="id desc"`` asks
        "hh.hermes.message": [
            {"id": 3, "role": "tool", "tool_name": "browser_click", "content": long_result},
            {"id": 2, "role": "assistant", "content": "a" * 300},
            {"id": 1, "role": "user", "content": "start"},
        ],
        "hh.browser.trace": [
            {"id": 2, "kind": "click", "target_attempted": 'role=option[name="Nederland (EER)"]',
             "ok": False, "error": "the option sits below the list's fold and the panel did not scroll"},
            {"id": 1, "kind": "page_snapshot", "ok": True},
        ],
    })
    dto = build_traces_dto(client, "lab00003", session="20260904_1")
    assert ("hh.hermes.message", MESSAGE_WINDOW, "id desc") in client.queries
    assert ("hh.browser.trace", MESSAGE_WINDOW, "id desc") in client.queries
    # the browser rows are windowed on the task id, never on the Steel session id
    bt_domains = [d for m, d in client.domains if m == "hh.browser.trace"]
    assert ["task_id", "=", "20260904_1"] in bt_domains[0]
    assert not any(c[0] == "session_ref" for c in bt_domains[0])
    msgs = dto["sessions"][0]["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant", "tool"]
    assert len(msgs[2]["preview"]) == 800 and len(msgs[1]["preview"]) == 160
    assert [t["kind"] for t in dto["browser_traces"]] == ["page_snapshot", "click"]
    text = harvest_trace_text(dto)
    assert ('[browser] click target=role=option[name="Nederland (EER)"] ok=False '
            "error=the option sits below the list's fold and the panel did not scroll") in text
    assert "[browser] page_snapshot" not in text


def test_a_browser_result_verdict_is_lifted_out_of_the_long_preview():
    """A click result starts with a 10 000-character tree and ends with the
    platform's own keys (`picked`, `resolved_by`, `options`, a halt). The 800-
    character preview never reaches them; the verdict line does, so an author reads
    a landed pick or a recovery from `oteny traces` alone."""
    from oteny.traces import _msg_preview, harvest_trace_text
    tree = "- combobox \"Sector\" [ref=e40]\n" * 400
    result = json.dumps({"success": True, "snapshot": tree,
                         "picked": {"option": "H. Vervoer en opslag", "combobox": "Sector",
                                    "now_reads": "H. Vervoer en opslag", "matched": True,
                                    "recovered_by": "typeahead"},
                         "resolved_by": "typeahead",
                         "options": {"label": "Sector", "total": 21, "visible": 7,
                                     "virtualized": False, "names": ["A."] * 21}})
    row = _msg_preview({"role": "tool", "tool_name": "browser_click", "content": result})
    assert len(row["preview"]) == 800 and "picked" not in row["preview"]
    assert row["verdict"]["picked"]["recovered_by"] == "typeahead"
    assert row["verdict"]["options"] == {"label": "Sector", "total": 21, "visible": 7,
                                         "virtualized": False}, "names stay out of the line"
    assert "names" not in row["verdict"]["options"]
    plain = _msg_preview({"role": "tool", "tool_name": "browser_click",
                          "content": json.dumps({"success": True, "snapshot": tree})})
    assert "verdict" not in plain
    assert "verdict" not in _msg_preview({"role": "tool", "tool_name": "read_file", "content": result})
    text = harvest_trace_text({"sessions": [{"session": "s", "label": "l", "turns": 1,
                                             "model_calls": 1, "messages": [row]}]})
    assert '[verdict] {"picked": {"option": "H. Vervoer en opslag"' in text
