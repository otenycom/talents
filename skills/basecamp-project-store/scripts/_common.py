#!/usr/bin/env python3
"""Shared helpers for the project-store scripts — paths, the profile, and the CLI.

Standard library only, no side effects on import, so every script that needs a home dir or a
profile field agrees on exactly one answer. Test hooks mirror the readiness scripts:

    HH_HOME              stand-in for $HOME
    BASECAMP_CLI         explicit path to the command-line tool
    BASECAMP_STORE_DATA  stand-in for ~/.hermes/data/basecamp-project-store
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

BOT = "basecamp-project-store"


def home() -> Path:
    return Path(os.environ.get("HH_HOME") or os.path.expanduser("~"))


def data_dir() -> Path:
    override = os.environ.get("BASECAMP_STORE_DATA")
    if override:
        return Path(override)
    return home() / ".hermes" / "data" / BOT


def auth_dir() -> Path:
    return data_dir() / "auth"


def profile_path() -> Path:
    return data_dir() / "profile.yaml"


def read_profile() -> dict:
    """The owner's board settings as a flat str->str mapping; {} when not connected yet.

    A deliberately tiny reader rather than a YAML dependency: the profile is a flat list of
    ``key: value`` lines by construction (its template is the contract), and a readiness
    script must work on a box whose system python has no third-party modules.
    """
    path = profile_path()
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def id_list(raw: str | None) -> list[str]:
    """A comma-separated id field from the profile as a clean list."""
    return [part.strip() for part in (raw or "").split(",") if part.strip()]


def cli_path() -> str | None:
    """The Basecamp command-line tool: the explicit override, the install location, or PATH."""
    override = (os.environ.get("BASECAMP_CLI") or "").strip()
    if override:
        return override if Path(override).exists() else None
    local = home() / ".local" / "bin" / "basecamp"
    if local.exists():
        return str(local)
    return shutil.which("basecamp")


def run_cli(args: list[str], *, timeout: int = 60) -> subprocess.CompletedProcess:
    """Run the command-line tool with input closed and output captured.

    Input is closed on purpose: the tool waits on a terminal when it thinks it has one, and
    then hangs for minutes instead of failing. Raises FileNotFoundError when the tool is not
    installed, so callers can tell "not connected" from "the call failed".
    """
    exe = cli_path()
    if not exe:
        raise FileNotFoundError("the Basecamp command-line tool is not installed")
    return subprocess.run(  # noqa: S603 — fixed executable, argument list, no shell
        [exe, *args],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


TOKEN_ENV = "BASECAMP_TOKEN"


def auth_status() -> tuple[bool | None, str]:
    """``(signed_in, source)`` from the tool's own cheap check. No network.

    ``source`` is ``BASECAMP_TOKEN`` when the tool is reading the environment
    variable Oteny leases the access token into, ``stored`` when it is reading its
    own saved credentials, and ``""`` when it could not be asked.

    Cheap on purpose: this runs on every turn through ``preflight``. Its answer is
    a claim about CONFIGURATION, not about whether the token still works — see
    ``probe_account`` for that difference, which is load-bearing.
    """
    import json

    try:
        proc = run_cli(["auth", "status", "--json"], timeout=30)
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        return None, ""
    try:
        payload = json.loads(proc.stdout or "{}")
    except ValueError:
        return None, ""
    if not payload.get("ok"):
        return False, ""
    data = payload.get("data") or {}
    return bool(data.get("authenticated")), str(data.get("source") or "stored")


def authenticated() -> bool | None:
    """True/False when the tool could be asked; None when it is not installed or did not answer."""
    return auth_status()[0]


def probe_account() -> bool | None:
    """Does the token this box holds actually work? One real API call.

    ``auth status`` cannot answer this, and it does not pretend to — with
    ``BASECAMP_TOKEN`` set it reports ``authenticated: true`` for ANY value,
    including a revoked or misspelt one. So a readiness check built on it alone
    would report a connected board over a dead credential, which is the exact
    class of lie that cost hh00452 its connect.

    Kept OFF the per-turn path for that one API call's sake: ``preflight`` stays
    cheap, and the truth verb (``connect_auth.py status``) pays for the probe.
    Returns None when the tool is absent or did not answer.
    """
    import json

    try:
        proc = run_cli(["accounts", "list", "--json"], timeout=30)
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        return None
    try:
        payload = json.loads(proc.stdout or "{}")
    except ValueError:
        return None
    return bool(payload.get("ok"))
