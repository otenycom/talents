"""Unit tests for the readiness call and the two-turn sign-in relay.

The sign-in is the one mechanism in this Talent that cannot be proven by reading the code: it
spans two chat turns and a detached waiter. So these tests stand up a fake command-line tool
that behaves like the real one (prints a link, then blocks on standard input until the pasted
address arrives) and drive the real relay against it end to end.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import time
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
_AUTH_URL = "https://launchpad.example.test/authorization/new?client_id=x&state=y"


def _load(name: str):
    sys.path.insert(0, str(_SCRIPTS))
    spec = importlib.util.spec_from_file_location(f"bpsx_{name}", _SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


common = _load("_common")
preflight = _load("preflight")
connect = _load("connect_auth")


def _fake_cli(tmp_path: Path, *, authed_marker: Path) -> Path:
    """A stand-in for the real tool: same output shapes, no network."""
    script = tmp_path / "basecamp"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys, pathlib\n"
        f"MARK = pathlib.Path({str(authed_marker)!r})\n"
        "argv = sys.argv[1:]\n"
        "if argv[:1] == ['--version']:\n"
        "    print('basecamp version 9.9.9'); raise SystemExit(0)\n"
        "if argv[:2] == ['auth', 'status']:\n"
        "    print(json.dumps({'ok': True, 'data': {'authenticated': MARK.exists()}}))\n"
        "    raise SystemExit(0)\n"
        "if argv[:2] == ['auth', 'login']:\n"
        f"    sys.stdout.write('Remote Authentication\\n  {_AUTH_URL}\\n')\n"
        "    sys.stdout.write('Paste the callback URL: ')\n"
        "    sys.stdout.flush()\n"
        "    pasted = sys.stdin.readline().strip()\n"
        "    if 'code=' in pasted:\n"
        "        MARK.write_text('ok')\n"
        "        print('\\nAuthenticated'); raise SystemExit(0)\n"
        "    print('\\nno input received'); raise SystemExit(1)\n"
        "raise SystemExit('unexpected: %s' % argv)\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script


def _leased_cli(tmp_path: Path, *, authed_marker: Path, monkeypatch, works: bool):
    """A stand-in for the tool when Oteny has LEASED the access token.

    Modelled on the real binary, including the detail that matters: with
    ``BASECAMP_TOKEN`` set it answers ``authenticated: true`` whatever the value
    is, and only a call that reaches the provider can tell a live token from a
    dead one.
    """
    script = tmp_path / "basecamp-leased"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        "argv = sys.argv[1:]\n"
        "if argv[:1] == ['--version']:\n"
        "    print('basecamp version 0.7.2'); raise SystemExit(0)\n"
        "if argv[:2] == ['auth', 'status']:\n"
        "    print(json.dumps({'ok': True, 'data': {'authenticated': True,\n"
        "                                           'source': 'BASECAMP_TOKEN'}}))\n"
        "    raise SystemExit(0)\n"
        "if argv[:2] == ['accounts', 'list']:\n"
        f"    ok = {works!r}\n"
        "    print(json.dumps({'ok': ok} if ok else\n"
        "                     {'ok': False, 'error': 'Authorization failed: invalid "
        "or expired token'}))\n"
        "    raise SystemExit(0)\n"
        "raise SystemExit('unexpected: %s' % argv)\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    monkeypatch.setenv("BASECAMP_CLI", str(script))
    return script


def _banner_cli(tmp_path: Path, *, authed_marker: Path, monkeypatch, chunked: bool = False):
    """A stand-in that prints the REAL tool's banner shape.

    Two details matter and both come from the tool's own output. It names the
    sign-in endpoint, with no query string, before the usable link. And with
    ``chunked`` it flushes the link in two pieces, which is what a read boundary
    looks like from the extractor's side.
    """
    script = tmp_path / "basecamp-banner"
    head, tail = _AUTH_URL[:60], _AUTH_URL[60:]
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys, time, pathlib\n"
        f"MARK = pathlib.Path({str(authed_marker)!r})\n"
        "argv = sys.argv[1:]\n"
        "if argv[:2] == ['auth', 'status']:\n"
        "    print(json.dumps({'ok': True, 'data': {'authenticated': MARK.exists()}}))\n"
        "    raise SystemExit(0)\n"
        "if argv[:2] == ['auth', 'login']:\n"
        "    sys.stdout.write('Remote authentication "
        "(https://launchpad.37signals.com/authorization/new)\\n')\n"
        "    sys.stdout.write('  1. Open this URL in a browser on any device:\\n     ')\n"
        "    sys.stdout.flush()\n"
        f"    sys.stdout.write({head!r})\n"
        + ("    sys.stdout.flush()\n    time.sleep(0.4)\n" if chunked else "")
        + f"    sys.stdout.write({tail!r} + '\\n')\n"
        "    sys.stdout.write('Paste the callback URL: ')\n"
        "    sys.stdout.flush()\n"
        "    pasted = sys.stdin.readline().strip()\n"
        "    if 'code=' in pasted:\n"
        "        MARK.write_text('ok')\n"
        "        print('\\nAuthenticated'); raise SystemExit(0)\n"
        "    print('\\nno input received'); raise SystemExit(1)\n"
        "raise SystemExit('unexpected: %s' % argv)\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    monkeypatch.setenv("BASECAMP_CLI", str(script))
    return script


def _sandbox(tmp_path, monkeypatch, *, authed: bool = False):
    marker = tmp_path / "authed"
    if authed:
        marker.write_text("ok")
    cli = _fake_cli(tmp_path, authed_marker=marker)
    monkeypatch.setenv("BASECAMP_CLI", str(cli))
    monkeypatch.setenv("BASECAMP_STORE_DATA", str(tmp_path / "store"))
    monkeypatch.setenv("HH_HOME", str(tmp_path / "home"))
    return marker


def _is_dead(pid: int) -> bool:
    """True once the waiter is gone. The waiter is a child of the test process, so a dead one
    lingers as an unreaped entry that a bare signal probe still reports as alive — reap first."""
    try:
        reaped, _status = os.waitpid(pid, os.WNOHANG)
        if reaped == pid:
            return True
    except ChildProcessError:
        pass
    except OSError:
        return True
    try:
        os.kill(pid, 0)
    except OSError:
        return True
    return False


def _write_profile(tmp_path, **fields):
    store = tmp_path / "store"
    store.mkdir(parents=True, exist_ok=True)
    (store / "profile.yaml").write_text(
        "\n".join(f"{k}: {v}" for k, v in fields.items()) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
# preflight                                                                     #
# --------------------------------------------------------------------------- #
def test_a_box_with_no_tool_is_not_ready(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("BASECAMP_CLI", str(tmp_path / "absent"))
    monkeypatch.setenv("BASECAMP_STORE_DATA", str(tmp_path / "store"))
    monkeypatch.setenv("HH_HOME", str(tmp_path / "home"))
    preflight.main()
    out = capsys.readouterr().out
    assert "READY: no" in out
    assert "CLI: missing" in out
    assert "basecamp_cli" in out


def test_signed_out_box_is_not_ready(tmp_path, monkeypatch, capsys):
    _sandbox(tmp_path, monkeypatch, authed=False)
    _write_profile(tmp_path, account_id=1, project_id=2, work_todolist_id=3)
    preflight.main()
    out = capsys.readouterr().out
    assert "READY: no" in out
    assert "AUTH: no" in out
    assert "sign_in" in out


def test_signed_in_without_a_board_names_the_missing_fields(tmp_path, monkeypatch, capsys):
    _sandbox(tmp_path, monkeypatch, authed=True)
    preflight.main()
    out = capsys.readouterr().out
    assert "READY: no" in out
    assert "profile:account_id,project_id,work_todolist_id" in out


def test_a_connected_box_is_ready_and_shows_its_lists(tmp_path, monkeypatch, capsys):
    _sandbox(tmp_path, monkeypatch, authed=True)
    _write_profile(tmp_path, account_id=1, project_id=2, work_todolist_id=3,
                   read_todolist_ids="4, 5", brief_message_ids=6, project_name="Board")
    preflight.main()
    out = capsys.readouterr().out
    assert "READY: yes" in out
    assert "MISSING" not in out
    assert "work=3" in out and "read=4,5" in out
    assert "BRIEF: 6" in out
    assert "DIGEST: none" in out


# --------------------------------------------------------------------------- #
# the two-turn sign-in                                                          #
# --------------------------------------------------------------------------- #
def test_sign_in_relays_the_link_then_completes_on_the_pasted_address(tmp_path, monkeypatch, capsys):
    marker = _sandbox(tmp_path, monkeypatch, authed=False)

    connect.cmd_start()
    started = capsys.readouterr().out
    assert started.startswith("AUTH_URL ")
    assert _AUTH_URL in started

    connect.cmd_finish(f"http://127.0.0.1:8976/callback?code=abc&state=y")
    finished = capsys.readouterr().out
    assert "AUTH_OK" in finished
    assert marker.exists(), "the fake tool only writes its marker on a real paste"
    # the one-time credentials are gone once the flow ends
    assert not (tmp_path / "store" / "auth" / "url.txt").exists()
    assert not (tmp_path / "store" / "auth" / "callback.txt").exists()


def test_status_reports_the_leased_token_and_probes_that_it_works(tmp_path, monkeypatch, capsys):
    """The lane-1 shape: Oteny leases the access token, no sign-in flow at all.

    ``auth status`` answers ``authenticated: yes`` for ANY value of the variable,
    so a readiness verdict built on it alone calls a revoked token a live board.
    ``status`` pays for one real API call and says what the provider thinks.
    """
    marker = _sandbox(tmp_path, monkeypatch, authed=True)
    _leased_cli(tmp_path, authed_marker=marker, monkeypatch=monkeypatch, works=True)

    connect.cmd_status()

    out = capsys.readouterr().out
    assert "SIGNED_IN: yes" in out
    assert "SOURCE: oteny" in out
    assert "WORKS: yes" in out
    assert "FLOW: none" in out


def test_status_calls_a_dead_leased_token_dead(tmp_path, monkeypatch, capsys):
    marker = _sandbox(tmp_path, monkeypatch, authed=True)
    _leased_cli(tmp_path, authed_marker=marker, monkeypatch=monkeypatch, works=False)

    connect.cmd_status()

    out = capsys.readouterr().out
    assert "SIGNED_IN: yes" in out
    assert "WORKS: no" in out
    assert "Reconnect" in out


def test_preflight_names_where_the_credential_came_from(tmp_path, monkeypatch, capsys):
    """Support has to be able to tell a leased token from a CLI sign-in."""
    marker = _sandbox(tmp_path, monkeypatch, authed=True)
    _leased_cli(tmp_path, authed_marker=marker, monkeypatch=monkeypatch, works=True)
    _write_profile(tmp_path, account_id=1, project_id=2, work_todolist_id=3)

    preflight.main()

    out = capsys.readouterr().out
    assert "READY: yes" in out
    assert "AUTH: yes via=oteny" in out


def test_the_link_is_read_past_the_banner_that_names_the_endpoint(tmp_path, monkeypatch, capsys):
    """The banner names the sign-in endpoint before the real link streams.

    On hh00452 (2026-08-25) the extractor matched that bare mention — closing
    bracket and all — and handed the owner a link that cannot sign anyone in. It
    happened on every box, in both of that conversation's sign-in attempts, and
    the bot worked around it by hand each time.
    """
    marker = _sandbox(tmp_path, monkeypatch, authed=False)
    _banner_cli(tmp_path, authed_marker=marker, monkeypatch=monkeypatch)

    connect.cmd_start()

    out = capsys.readouterr().out
    assert out.startswith("AUTH_URL ")
    assert out.split(" ", 1)[1].strip() == _AUTH_URL
    connect.cmd_cancel()


def test_a_link_split_across_two_reads_is_not_handed_over_half_written(
        tmp_path, monkeypatch, capsys):
    """A 4096-byte read has no idea where a URL ends.

    The old pattern matched whatever had arrived, so a link cut by a read boundary
    latched as the answer — the second way one connect produced an unusable link.
    The extractor now waits for the character that ends the URL.
    """
    marker = _sandbox(tmp_path, monkeypatch, authed=False)
    _banner_cli(tmp_path, authed_marker=marker, monkeypatch=monkeypatch, chunked=True)

    connect.cmd_start()

    out = capsys.readouterr().out
    assert out.startswith("AUTH_URL ")
    assert out.split(" ", 1)[1].strip() == _AUTH_URL
    connect.cmd_cancel()


def test_a_paste_without_a_code_is_refused_before_it_reaches_the_tool(tmp_path, monkeypatch, capsys):
    _sandbox(tmp_path, monkeypatch, authed=False)
    connect.cmd_start()
    capsys.readouterr()
    connect.cmd_finish("I clicked it but nothing happened")
    out = capsys.readouterr().out
    assert "AUTH_FAILED" in out
    assert "code" in out
    connect.cmd_cancel()


def test_finish_without_a_start_is_refused(tmp_path, monkeypatch, capsys):
    _sandbox(tmp_path, monkeypatch, authed=False)
    connect.cmd_finish("http://127.0.0.1:8976/callback?code=abc")
    assert "AUTH_FAILED" in capsys.readouterr().out


def test_the_link_file_is_owner_only(tmp_path, monkeypatch, capsys):
    _sandbox(tmp_path, monkeypatch, authed=False)
    connect.cmd_start()
    capsys.readouterr()
    url_file = tmp_path / "store" / "auth" / "url.txt"
    assert url_file.exists()
    assert oct(url_file.stat().st_mode)[-3:] == "600"
    connect.cmd_cancel()


def test_cancel_stops_the_waiter_and_clears_the_flow(tmp_path, monkeypatch, capsys):
    _sandbox(tmp_path, monkeypatch, authed=False)
    connect.cmd_start()
    capsys.readouterr()
    auth = tmp_path / "store" / "auth"
    pid = int((auth / "supervisor.pid").read_text())
    connect.cmd_cancel()
    assert "AUTH_CANCELLED" in capsys.readouterr().out
    assert not (auth / "url.txt").exists()
    for _ in range(60):                      # the waiter gets a moment to die
        if _is_dead(pid):
            break
        time.sleep(0.05)
    else:
        raise AssertionError("the detached waiter is still running after cancel")
    connect.cmd_status()
    assert "FLOW: none" in capsys.readouterr().out


def test_status_reports_the_phase(tmp_path, monkeypatch, capsys):
    _sandbox(tmp_path, monkeypatch, authed=False)
    connect.cmd_status()
    assert "FLOW: none" in capsys.readouterr().out
    connect.cmd_start()
    capsys.readouterr()
    connect.cmd_status()
    assert "FLOW: waiting for the pasted address" in capsys.readouterr().out
    connect.cmd_cancel()


def test_preflight_reports_the_resolved_tool_path(tmp_path, monkeypatch, capsys):
    """The tool installs into ~/.local/bin, which is on a LOGIN shell's PATH but not on the
    plain shell a tool call usually gets — so a bare `basecamp …` fails on exactly the box
    where it is installed. The skill calls it by path, and preflight is where that path comes
    from, so it has to be in the output rather than a bare "installed"."""
    _sandbox(tmp_path, monkeypatch, authed=True)
    preflight.main()
    out = capsys.readouterr().out
    cli_line = next(line for line in out.splitlines() if line.startswith("CLI:"))
    assert " at " in cli_line, "preflight must print WHERE the tool is, not just that it is"
    assert str(tmp_path / "basecamp") in cli_line
