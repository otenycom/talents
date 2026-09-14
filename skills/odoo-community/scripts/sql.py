#!/usr/bin/env python3
"""Guarded local psql against the Community database. Never prints a secret.

Stdin JSON: {"sql": "...", "confirm": false}. SELECT is free. Mutating SQL
needs confirm=true. Refuses DROP DATABASE and password/api_key columns.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from local_odoo_paths import db_name, home

_MUTATE = re.compile(
    r"^\s*(INSERT|UPDATE|DELETE|ALTER|DROP|TRUNCATE|CREATE|GRANT|REVOKE|COPY|VACUUM|REINDEX)\b",
    re.I,
)
_DROP_DB = re.compile(r"\bDROP\s+DATABASE\b", re.I)
_SECRET_COL = re.compile(
    r"\b(password|api_key|api_secret|totp_secret|totp_enabled|oauth_uid)\b",
    re.I,
)
_LINE_CAP = 200


def _psql() -> Path:
    return home() / "postgres" / "bin" / "psql"


def _load() -> dict:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("stdin JSON must be an object")
    return data


def main() -> int:
    try:
        payload = _load()
        sql = str(payload.get("sql") or "").strip()
        confirm = bool(payload.get("confirm", False))
        if not sql:
            print(json.dumps({"ok": False, "error": "sql_required"}))
            return 0
        if _DROP_DB.search(sql):
            print(json.dumps({"ok": False, "error": "drop_database_refused"}))
            return 0
        if _SECRET_COL.search(sql):
            print(json.dumps({"ok": False, "error": "secret_column_refused"}))
            return 0
        mutating = bool(_MUTATE.search(sql))
        if mutating and not confirm:
            print(json.dumps({"ok": False, "error": "confirm_required", "mutating": True}))
            return 0
        psql = _psql()
        if not psql.is_file():
            print(json.dumps({"ok": False, "error": "psql_missing"}))
            return 0
        db = db_name()
        env = os.environ.copy()
        env.pop("PGPASSWORD", None)
        proc = subprocess.run(
            [
                str(psql),
                "-h", "127.0.0.1",
                "-p", "5432",
                "-d", db,
                "-A",
                "-F", "\t",
                "-P", "pager=off",
                "-c", sql,
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
            check=False,
        )
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        lines = stdout.splitlines()
        truncated = len(lines) > _LINE_CAP
        print(json.dumps({
            "ok": proc.returncode == 0,
            "db": db,
            "mutating": mutating,
            "returncode": proc.returncode,
            "rows": lines[:_LINE_CAP],
            "truncated": truncated,
            "error": stderr.strip() if proc.returncode else "",
        }))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
