"""The devbot environment's owner verbs (repository keys and tokens, dev branches).

Each verb is one account-scoped /json/2/ call to a seam the platform checks, so these
tests pin the model, the method and the arguments, and the promise that a token never
rides the command line.
"""
from __future__ import annotations

import json

import pytest

from oteny import cli


class _Client:
    def __init__(self, answers=None):
        self.calls: list = []
        self._answers = list(answers or [])

    def call(self, model, method, **kw):
        self.calls.append((model, method, kw))
        if self._answers:
            return self._answers.pop(0) if len(self._answers) > 1 else self._answers[0]
        return {"ok": True}


@pytest.fixture
def client(monkeypatch):
    c = _Client()
    monkeypatch.setattr(cli, "_client", lambda args: c)
    monkeypatch.setattr(cli.time, "sleep", lambda s: None)
    return c


def _run(argv, capsys):
    rc = cli.main(argv)
    return rc, json.loads(capsys.readouterr().out)


@pytest.mark.parametrize("argv, model, method, kw", [
    (["repo-key", "create", "--repo", "git@github.com:acme/bots.git"],
     "hh.talent.repo_credential", "repo_credential_create",
     {"repo": "git@github.com:acme/bots.git"}),
    (["repo-key", "check", "--repo", "git@github.com:acme/bots.git"],
     "hh.talent.repo_credential", "repo_credential_check",
     {"repo": "git@github.com:acme/bots.git"}),
    (["repo-key", "list"], "hh.talent.repo_credential", "repo_credentials", {}),
    (["repo-key", "remove", "--repo", "git@github.com:acme/bots.git"],
     "hh.talent.repo_credential", "repo_credential_remove",
     {"repo": "git@github.com:acme/bots.git"}),
    (["branch", "open", "--source-id", "12", "--name", "fix-greeting"],
     "hh.talent.dev_branch", "dev_branch_open",
     {"source_id": 12, "name": "fix-greeting", "delete_branch_on_close": False}),
    (["branch", "list"], "hh.talent.dev_branch", "dev_branches", {"source_id": None}),
    (["branch", "status", "--id", "5"], "hh.talent.dev_branch", "dev_branch_status",
     {"dev_branch_id": 5}),
    (["branch", "test", "--id", "5"], "hh.talent.dev_branch", "dev_branch_test",
     {"dev_branch_id": 5}),
    (["branch", "promote", "--id", "5"], "hh.talent.dev_branch", "dev_branch_promote",
     {"dev_branch_id": 5}),
    (["branch", "close", "--id", "5", "--delete-branch"], "hh.talent.dev_branch",
     "dev_branch_close", {"dev_branch_id": 5, "delete_branch": True}),
    (["link", "promote-mode", "--source-id", "12", "--set", "pull_request"],
     "hh.talent.source", "set_promote_mode", {"source_id": 12, "promote_mode": "pull_request"}),
])
def test_each_verb_is_one_checked_seam(client, capsys, argv, model, method, kw):
    rc, out = _run(argv, capsys)
    assert rc == 0 and out == {"ok": True}
    assert client.calls == [(model, method, kw)]


def test_a_refusal_exits_non_zero_and_prints_the_reason(monkeypatch, capsys):
    c = _Client([{"ok": False, "reason": "needs_write_credential"}])
    monkeypatch.setattr(cli, "_client", lambda args: c)
    rc, out = _run(["branch", "open", "--source-id", "12", "--name", "x"], capsys)
    assert rc == 1 and out["reason"] == "needs_write_credential"


def test_a_token_is_read_from_a_file_never_the_command_line(client, capsys, tmp_path):
    token_file = tmp_path / "token"
    token_file.write_text("tok-secret-123\n")
    rc, out = _run(["repo-token", "set", "--repo", "https://gitea.example.org/t/b.git",
                    "--token-file", str(token_file), "--username", "writer"], capsys)
    assert rc == 0
    assert client.calls == [("hh.talent.repo_credential", "repo_credential_set_token",
                             {"repo": "https://gitea.example.org/t/b.git",
                              "token": "tok-secret-123", "username": "writer"})]
    assert "tok-secret-123" not in json.dumps(out)


def test_there_is_no_token_flag_to_put_a_secret_on_argv():
    with pytest.raises(SystemExit):
        cli.main(["repo-token", "set", "--repo", "https://x.org/a/b", "--token", "leak"])


def test_a_token_can_come_from_stdin(client, capsys, monkeypatch):
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO("tok-from-stdin\n"))
    rc, _ = _run(["repo-token", "set", "--repo", "https://x.org/a/b", "--token-stdin"],
                 capsys)
    assert rc == 0
    assert client.calls[0][2]["token"] == "tok-from-stdin"


def test_wait_polls_a_test_to_green_or_red(monkeypatch, capsys):
    c = _Client([{"ok": True, "state": "open", "job": "save"},
                 {"ok": True, "state": "testing", "job": ""},
                 {"ok": True, "state": "green", "job": "", "green_commit": "beef"}])
    monkeypatch.setattr(cli, "_client", lambda args: c)
    monkeypatch.setattr(cli.time, "sleep", lambda s: None)
    rc, out = _run(["branch", "test", "--id", "5", "--wait", "600"], capsys)
    assert rc == 0 and out["state"] == "green"
    assert [m for _model, m, _kw in c.calls] == [
        "dev_branch_test", "dev_branch_status", "dev_branch_status"]


def test_wait_ends_red_with_a_non_zero_exit(monkeypatch, capsys):
    c = _Client([{"ok": True, "state": "testing", "job": ""},
                 {"ok": True, "state": "red", "job": "", "last_error": "scenario failed"}])
    monkeypatch.setattr(cli, "_client", lambda args: c)
    monkeypatch.setattr(cli.time, "sleep", lambda s: None)
    rc, out = _run(["branch", "test", "--id", "5", "--wait", "600"], capsys)
    assert rc == 1 and out["state"] == "red"


def test_wait_gives_up_at_its_deadline(monkeypatch, capsys):
    c = _Client([{"ok": True, "state": "testing", "job": ""}])
    clock = iter(range(0, 10_000, 30))
    monkeypatch.setattr(cli, "_client", lambda args: c)
    monkeypatch.setattr(cli.time, "sleep", lambda s: None)
    monkeypatch.setattr(cli.time, "monotonic", lambda: next(clock))
    rc, out = _run(["branch", "test", "--id", "5", "--wait", "60"], capsys)
    assert rc == 2 and out["state"] == "testing" and out["timed_out"] is True
