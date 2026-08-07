#!/usr/bin/env python3
"""connect_auth — sign the box in to Basecamp across two chat turns.

Basecamp's sign-in is a browser flow. The box has no browser, so the tool offers a headless
mode: it prints a link and then waits, at a prompt with no newline, for the address the
browser lands on to be pasted back. That wait cannot span two chat turns inside one command
call — so this script parks the waiting in a small detached supervisor:

    connect_auth.py start                      -> AUTH_URL <link>      (turn 1)
    connect_auth.py finish --callback "<url>"  -> AUTH_OK              (turn 2)
    connect_auth.py status                     -> where the flow is
    connect_auth.py cancel                     -> stop and clean up

Everything lives under ~/.hermes/data/basecamp-project-store/auth/ and is removed on success
or cancel. Standard library only; the exit code is 0 whenever the command ran (the verdict is
in the output, so a normal "not yet" never looks like a crashed tool).

The link and the pasted address are one-time credentials. They are written to files readable
only by this user, never echoed to a board, and deleted when the flow ends.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import select
import signal
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import auth_dir, cli_path  # noqa: E402

# The authorize link the tool prints. Kept broad on purpose (the sign-in host has moved
# before); it is only ever matched against the tool's own output.
_URL_RE = re.compile(r"https://\S*/authorization/new\S*")
_URL_WAIT = 45          # seconds to wait for the link to appear after starting
_FINISH_WAIT = 90       # seconds to wait for the sign-in to complete after the paste
_FLOW_TTL = 900         # a sign-in nobody finishes is abandoned after 15 minutes


def _paths() -> dict[str, Path]:
    d = auth_dir()
    return {
        "dir": d,
        "url": d / "url.txt",
        "callback": d / "callback.txt",
        "result": d / "result.json",
        "log": d / "out.log",
        "pid": d / "supervisor.pid",
    }


def _write_private(path: Path, text: str) -> None:
    """Write a one-time credential so only this user can read it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)


def _clean(p: dict[str, Path]) -> None:
    for key in ("url", "callback", "result", "log", "pid"):
        try:
            p[key].unlink()
        except FileNotFoundError:
            pass


def _supervisor_alive(p: dict[str, Path]) -> bool:
    try:
        pid = int(p["pid"].read_text().strip())
    except (OSError, ValueError):
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


# --------------------------------------------------------------------------- #
# The supervisor: holds the sign-in open while the owner uses their browser.    #
# --------------------------------------------------------------------------- #
def _supervise() -> int:
    p = _paths()
    p["dir"].mkdir(parents=True, exist_ok=True)
    exe = cli_path()
    if not exe:
        _write_private(p["result"], json.dumps({"ok": False, "reason": "cli-not-installed"}))
        return 0
    proc = subprocess.Popen(  # noqa: S603 — fixed executable, argument list, no shell
        [exe, "auth", "login", "--remote", "--no-browser", "--scope", "full"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=False,
    )
    captured = bytearray()
    url_seen = False
    callback_sent = False
    fd = proc.stdout.fileno()
    deadline = time.monotonic() + _FLOW_TTL
    try:
        while time.monotonic() < deadline:
            # Wait for output with a timeout rather than reading straight through: the tool
            # prints its link, then blocks at a prompt with no newline, and a plain read would
            # sit there forever — never noticing that the owner has pasted their address.
            ready, _, _ = select.select([fd], [], [], 0.5)
            if ready:
                chunk = os.read(fd, 4096)
                if not chunk:                      # the tool has finished talking
                    break
                captured += chunk
                text = captured.decode("utf-8", "replace")
                _write_private(p["log"], text)
                if not url_seen:
                    match = _URL_RE.search(text)
                    if match:
                        url_seen = True
                        _write_private(p["url"], match.group(0))
                continue
            if proc.poll() is not None:
                break
            if url_seen and not callback_sent and p["callback"].is_file():
                callback = p["callback"].read_text(encoding="utf-8").strip()
                proc.stdin.write((callback + "\n").encode())
                proc.stdin.flush()
                callback_sent = True
        else:
            proc.kill()
            _write_private(p["result"], json.dumps({"ok": False, "reason": "expired"}))
            return 0
    except OSError as exc:
        proc.kill()
        _write_private(p["result"], json.dumps({"ok": False, "reason": f"io-error: {exc}"}))
        return 0
    finally:
        try:
            proc.stdin.close()
        except OSError:
            pass

    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()

    if not url_seen:
        tail = captured.decode("utf-8", "replace")[-400:]
        _write_private(p["result"], json.dumps({"ok": False, "reason": "no-link", "tail": tail}))
        return 0

    # The tool's own exit code is not enough (it can exit 0 after an unusable paste), so ask
    # it whether the box is actually signed in now.
    from _common import authenticated

    ok = authenticated() is True
    tail = captured.decode("utf-8", "replace")[-400:]
    _write_private(p["result"], json.dumps({"ok": ok, "reason": "" if ok else "not-authenticated",
                                            "tail": tail}))
    return 0


# --------------------------------------------------------------------------- #
# The two owner-facing halves                                                   #
# --------------------------------------------------------------------------- #
def cmd_start() -> int:
    p = _paths()
    if not cli_path():
        print("AUTH_START_FAILED the Basecamp command-line tool is not installed "
              "(run install_cli.sh first)")
        return 0
    if _supervisor_alive(p) and p["url"].is_file() and not p["result"].is_file():
        print(f"AUTH_URL {p['url'].read_text().strip()}")
        print("NOTE a sign-in was already waiting; the same link is still valid")
        return 0
    cmd_cancel(quiet=True)
    p["dir"].mkdir(parents=True, exist_ok=True)
    child = subprocess.Popen(  # noqa: S603 — this same file, no shell
        [sys.executable, str(Path(__file__).resolve()), "_supervise"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    _write_private(p["pid"], str(child.pid))

    deadline = time.monotonic() + _URL_WAIT
    while time.monotonic() < deadline:
        if p["url"].is_file():
            print(f"AUTH_URL {p['url'].read_text().strip()}")
            return 0
        if p["result"].is_file():
            break
        time.sleep(0.5)
    reason = "timed out waiting for the sign-in link"
    if p["result"].is_file():
        try:
            reason = json.loads(p["result"].read_text()).get("reason") or reason
        except ValueError:
            pass
    print(f"AUTH_START_FAILED {reason}")
    return 0


def cmd_finish(callback: str) -> int:
    p = _paths()
    callback = (callback or "").strip()
    if "code=" not in callback:
        print("AUTH_FAILED that does not look like the address the browser landed on "
              "(it must contain a code) — ask for the full address bar contents")
        return 0
    if not p["url"].is_file():
        print("AUTH_FAILED no sign-in is waiting — run start first")
        return 0
    _write_private(p["callback"], callback)

    deadline = time.monotonic() + _FINISH_WAIT
    while time.monotonic() < deadline:
        if p["result"].is_file():
            try:
                result = json.loads(p["result"].read_text())
            except ValueError:
                result = {"ok": False, "reason": "unreadable result"}
            if result.get("ok"):
                _clean(p)
                print("AUTH_OK signed in")
                return 0
            print(f"AUTH_FAILED {result.get('reason') or 'sign-in did not complete'}")
            return 0
        time.sleep(0.5)
    print("AUTH_FAILED timed out completing the sign-in")
    return 0


def cmd_status() -> int:
    p = _paths()
    from _common import authenticated

    state = authenticated()
    print("SIGNED_IN: " + {True: "yes", False: "no", None: "unknown"}[state])
    if p["result"].is_file():
        print("FLOW: finished")
    elif p["url"].is_file():
        print("FLOW: waiting for the pasted address")
    elif _supervisor_alive(p):
        print("FLOW: starting")
    else:
        print("FLOW: none")
    return 0


def cmd_cancel(quiet: bool = False) -> int:
    p = _paths()
    try:
        pid = int(p["pid"].read_text().strip())
        os.kill(pid, signal.SIGTERM)
    except (OSError, ValueError):
        pass
    _clean(p)
    if not quiet:
        print("AUTH_CANCELLED")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Sign this box in to Basecamp")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("start")
    fin = sub.add_parser("finish")
    fin.add_argument("--callback", required=True,
                     help="the full address the owner's browser landed on")
    sub.add_parser("status")
    sub.add_parser("cancel")
    sub.add_parser("_supervise")   # internal: the detached waiter
    args = ap.parse_args(argv)

    if args.cmd == "start":
        return cmd_start()
    if args.cmd == "finish":
        return cmd_finish(args.callback)
    if args.cmd == "status":
        return cmd_status()
    if args.cmd == "cancel":
        return cmd_cancel()
    return _supervise()


if __name__ == "__main__":
    raise SystemExit(main())
