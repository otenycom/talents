"""The demo's run ledger (stdlib sqlite3). Every helper records one row per run."""
from __future__ import annotations

import datetime as _dt
import json
import os
import sqlite3
from pathlib import Path

_DB = Path(os.environ.get("HH_HOME") or "~").expanduser() / ".hermes" / "data" / \
    "oteny-helper-runner-demo" / "runs.db"
_SCHEMA = Path(__file__).with_name("init.sql")


def record(helper: str, argv: list[str], exit_code: int) -> None:
    """Append one row. Creates the ledger from init.sql when it is missing."""
    _DB.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(_DB) as con:
        con.executescript(_SCHEMA.read_text())
        con.execute(
            "INSERT INTO helper_runs (ran_at, helper, argv, exit_code) VALUES (?, ?, ?, ?)",
            (_dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
             helper, json.dumps(argv), int(exit_code)))
