"""Unit tests for the project-store helpers — the deterministic half of the Talent.

These cover exactly the behaviours that must never regress silently: a body that survives the
board's editor, and a recurring summary that stays quiet on a quiet day.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def _load(name: str):
    sys.path.insert(0, str(_SCRIPTS))
    spec = importlib.util.spec_from_file_location(f"bps_{name}", _SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ps = _load("project_store")
common = _load("_common")


# --------------------------------------------------------------------------- #
# Bodies that survive the board's editor                                        #
# --------------------------------------------------------------------------- #
def test_pipe_table_becomes_bullets():
    body = "\n".join([
        "Rates:",
        "",
        "| Service | Duration | Price |",
        "|---|---|---|",
        "| Wash & cut | 30 min | EUR 40 |",
        "| Beard trim | 30 min | EUR 35 |",
        "",
        "Ends here.",
    ])
    out, tables, fenced = ps.prepare_body(body)
    assert tables == 1
    assert fenced == 0
    assert "|" not in out, "a surviving pipe renders as literal bars on the board"
    assert "- **Wash & cut** — Duration: 30 min; Price: EUR 40" in out
    assert "- **Beard trim** — Duration: 30 min; Price: EUR 35" in out
    assert out.startswith("Rates:")
    assert out.rstrip().endswith("Ends here.")


def test_raw_html_is_fenced_so_the_editor_cannot_eat_it():
    body = 'Embed this:\n<iframe src="https://example.test/widget/" style="width:100%"></iframe>\ndone'
    out, _tables, fenced = ps.prepare_body(body)
    assert fenced == 1
    lines = out.split("\n")
    idx = next(i for i, line in enumerate(lines) if "<iframe" in line)
    assert lines[idx - 1] == "```" and lines[idx + 1] == "```"


def test_already_fenced_html_is_left_alone():
    body = "```\n<iframe src=\"https://example.test/\"></iframe>\n```"
    out, _tables, fenced = ps.prepare_body(body)
    assert fenced == 0
    assert out == body


def test_prepare_body_is_idempotent():
    body = "| A | B |\n|---|---|\n| 1 | 2 |\n\n<b>bold</b>"
    once, _, _ = ps.prepare_body(body)
    twice, tables, fenced = ps.prepare_body(once)
    assert twice == once
    assert (tables, fenced) == (0, 0)


# --------------------------------------------------------------------------- #
# Board markup -> readable text                                                 #
# --------------------------------------------------------------------------- #
def test_board_markup_reads_as_plain_text():
    markup = '<p dir="auto">Foundation first.</p><br><ul><li>Dutch</li><li>English</li></ul>'
    text = ps.to_text(markup)
    assert "Foundation first." in text
    assert "- Dutch" in text and "- English" in text
    assert "<" not in text


def test_entities_are_decoded_not_shown():
    assert ps.to_text("<p>Tom &amp; Jerry &lt;3</p>") == "Tom & Jerry <3"


# --------------------------------------------------------------------------- #
# The quiet-day rule                                                            #
# --------------------------------------------------------------------------- #
def _todo(tid, title, *, completed=False, updated="2026-08-07T10:00:00Z"):
    return {"id": tid, "title": title, "completed": completed, "updated_at": updated}


def test_unchanged_board_produces_no_news():
    todos = [_todo(1, "Chair page"), _todo(2, "Home page")]
    messages = [{"id": 9, "subject": "Brief", "updated_at": "2026-08-07T09:00:00Z"}]
    state = ps.snapshot(todos, messages)
    changes = ps.diff(state, ps.snapshot(todos, messages))
    assert changes["added"] == []
    assert changes["completed"] == []
    assert changes["reopened"] == []
    assert changes["updated"] == []
    assert changes["messages"] == []
    assert changes["still_open"] == 2


def test_completion_addition_and_edit_are_each_reported_once():
    before = ps.snapshot([_todo(1, "Chair page"), _todo(2, "Home page")], [])
    after = ps.snapshot(
        [
            _todo(1, "Chair page", completed=True, updated="2026-08-07T12:00:00Z"),
            _todo(2, "Home page", updated="2026-08-07T12:30:00Z"),
            _todo(3, "Contact page"),
        ],
        [],
    )
    changes = ps.diff(before, after)
    assert changes["completed"] == ["Chair page"]
    assert changes["added"] == ["Contact page"]
    assert changes["updated"] == ["Home page"]
    assert changes["reopened"] == []
    assert changes["still_open"] == 2


def test_a_reopened_todo_is_not_reported_as_new():
    before = ps.snapshot([_todo(1, "Chair page", completed=True)], [])
    after = ps.snapshot([_todo(1, "Chair page", updated="2026-08-08T09:00:00Z")], [])
    changes = ps.diff(before, after)
    assert changes["reopened"] == ["Chair page"]
    assert changes["added"] == []
    assert changes["updated"] == []


def test_a_changed_message_is_news():
    before = ps.snapshot([], [{"id": 9, "subject": "Brief", "updated_at": "a"}])
    after = ps.snapshot([], [{"id": 9, "subject": "Brief", "updated_at": "b"},
                             {"id": 10, "subject": "Content pack", "updated_at": "c"}])
    assert sorted(ps.diff(before, after)["messages"]) == ["Brief", "Content pack"]


def test_state_round_trips_through_the_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("BASECAMP_STORE_DATA", str(tmp_path / "store"))
    assert ps.load_state() == {}
    state = ps.snapshot([_todo(1, "Chair page")], [])
    ps.save_state(state)
    assert ps.load_state() == state
    assert json.loads((tmp_path / "store" / "digest_state.json").read_text())["todos"]


# --------------------------------------------------------------------------- #
# Profile reading (the list-ownership contract lives here)                      #
# --------------------------------------------------------------------------- #
def test_profile_is_read_without_a_yaml_dependency(tmp_path, monkeypatch):
    monkeypatch.setenv("BASECAMP_STORE_DATA", str(tmp_path))
    (tmp_path / "profile.yaml").write_text(
        '# a comment\naccount_id: "12"\nproject_id: 34\n'
        "work_todolist_id: 56\nread_todolist_ids: 78, 90\nbrief_message_ids: \n",
        encoding="utf-8",
    )
    profile = common.read_profile()
    assert profile["account_id"] == "12"
    assert profile["project_id"] == "34"
    assert common.id_list(profile["read_todolist_ids"]) == ["78", "90"]
    assert common.id_list(profile["brief_message_ids"]) == []


def test_an_absent_profile_is_empty_not_an_error(tmp_path, monkeypatch):
    monkeypatch.setenv("BASECAMP_STORE_DATA", str(tmp_path / "nope"))
    assert common.read_profile() == {}


@pytest.mark.parametrize("raw,expected", [("", []), ("  ", []), ("1", ["1"]), (" 1 , 2 ,", ["1", "2"])])
def test_id_list_shapes(raw, expected):
    assert common.id_list(raw) == expected
