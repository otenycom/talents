#!/usr/bin/env python3
"""preflight — the ONE per-turn call before answering anything about a project board.

Answers in a single read-only call what the triage would otherwise fan out into four: is the
command-line tool installed, is this box signed in, which board is it working, and which list
is its own. Pure and side-effect-free; the exit code is always 0 (the verdict is in the
output, so a "not connected yet" never looks like a failed command).

    python3 ~/.hermes/skills/talents/basecamp-project-store/scripts/preflight.py

Prints a compact parseable block:
  READY   — yes|no   (tool installed + signed in + the board fields set)
  CLI     — installed <version> | missing
  AUTH    — yes|no|unknown
  BOARD   — the account/project this bot works
  LISTS   — the list it owns, and the lists it may only read
  BRIEF   — the messages holding the rules
  DIGEST  — the recurring summary, if the owner asked for one
  MISSING — the blocking pieces when READY is no
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import authenticated, cli_path, id_list, read_profile, run_cli  # noqa: E402

_REQUIRED_FIELDS = ("account_id", "project_id", "work_todolist_id")


def _cli_version() -> str | None:
    if not cli_path():
        return None
    try:
        proc = run_cli(["--version"], timeout=20)
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        return "unknown"
    line = (proc.stdout or proc.stderr or "").strip().splitlines()
    return line[0] if line else "unknown"


def main() -> int:
    profile = read_profile()
    version = _cli_version()
    auth = authenticated() if version else None

    missing: list[str] = []
    if not version:
        missing.append("basecamp_cli")
    elif auth is not True:
        missing.append("sign_in")
    unset = [f for f in _REQUIRED_FIELDS if not (profile.get(f) or "").strip()]
    if unset:
        missing.append("profile:" + ",".join(unset))

    print(f"READY: {'no' if missing else 'yes'}")
    # Print the RESOLVED path, not just "installed": the tool lands in ~/.local/bin, which is on
    # a login shell's PATH but not on a plain one — so a bare `basecamp …` fails on exactly the
    # box where it is installed. The skill calls it by this path.
    print("CLI: " + (f"installed {version} at {cli_path()}" if version else "missing"))
    print("AUTH: " + {True: "yes", False: "no", None: "unknown"}[auth])
    print("BOARD: "
          f"account={profile.get('account_id') or '-'} "
          f"project={profile.get('project_id') or '-'} "
          f"name={profile.get('project_name') or '-'}")
    read_ids = id_list(profile.get("read_todolist_ids"))
    print("LISTS: "
          f"work={profile.get('work_todolist_id') or '-'} "
          f"read={','.join(read_ids) if read_ids else '-'}")
    brief = id_list(profile.get("brief_message_ids"))
    print("BRIEF: " + (",".join(brief) if brief else "-"))
    digest_time = (profile.get("digest_time") or "").strip()
    digest_chat = (profile.get("digest_chat") or "").strip()
    print("DIGEST: " + (f"{digest_time} -> {digest_chat}" if digest_time else "none"))
    if missing:
        print("MISSING: " + " ".join(missing))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
