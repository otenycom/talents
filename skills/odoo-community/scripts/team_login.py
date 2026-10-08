#!/usr/bin/env python3
"""team_login.py — one Odoo login per person, over JSON-2.

The bot makes and checks logins for the owner's team on the Odoo in this box.
Every command talks to ``127.0.0.1:8069`` only: JSON-2 with the bearer key in
``.odoo-admin`` (``local_odoo_rpc.OdooRPC``), plus one session sign-in for
``check``. No ``odoo shell``, no public URL.

    team_login.py create --login <email> --name <name> \\
        (--like <login> | --groups <xmlid,...>) [--groups …] [--without …] \\
        [--password-env <VAR>]
    team_login.py set-password --login <email> --password-env <VAR>
    team_login.py check --login <as typed> --password-env <VAR>
    team_login.py can
    team_login.py lowercase-all

A password only ever comes from an environment variable (``--password-env``).
It is never an argument and never printed. Result lines are plain tokens the
bot quotes. Exit 0 on success, 1 on a refusal or a failed check.
``lowercase-all`` (the ``lowercase-logins`` migration) always exits 0; its
outcome is in the output.
"""
from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from local_odoo_paths import admin_candidates, db_name, home, normalize_login
from local_odoo_rpc import OdooRPC, as_id

_URL = "http://127.0.0.1:8069"
_USER_FIELDS = ["id", "login", "email", "name", "active", "share", "group_ids"]
_ALL = {"active_test": False}


class _Parser(argparse.ArgumentParser):
    """argparse echoes unrecognized arguments. One of them may be a password
    passed by mistake, so this parser never echoes them."""

    def error(self, message):
        if message.startswith("unrecognized arguments"):
            message = "unrecognized arguments (not shown) — a password never goes on argv"
        self.exit(2, f"TEAM_LOGIN_USAGE {message}\n")


class Refused(Exception):
    """A result line that ends the command with exit 1."""


# --------------------------------------------------------------------------- #
# small helpers                                                                #
# --------------------------------------------------------------------------- #
def _password_from_env(var: str | None) -> str:
    if not var:
        return ""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", var):
        # Never echo it: a value that is not a variable name may be the
        # password itself, passed by mistake.
        raise Refused("BAD_ENV_NAME — --password-env takes a variable name")
    value = (os.environ.get(var) or "").strip()
    if not value:
        raise Refused(f"EMPTY_ENV {var}")
    return value


def _like_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _users_any_case(rpc, login: str) -> list[dict]:
    """Every user (archived too) whose login equals ``login`` in any case."""
    rows = rpc.call(
        "res.users", "search_read",
        [[["login", "=ilike", _like_escape(login.strip())]]],
        {"fields": _USER_FIELDS, "context": _ALL},
    ) or []
    want = login.strip().lower()
    return [r for r in rows if (r.get("login") or "").lower() == want]


def _group_ids(rpc, xmlids: list[str]) -> list[int]:
    out: list[int] = []
    missing: list[str] = []
    for xmlid in xmlids:
        module, _, name = xmlid.partition(".")
        rows = rpc.call(
            "ir.model.data", "search_read",
            [[["module", "=", module], ["name", "=", name], ["model", "=", "res.groups"]]],
            {"fields": ["res_id"], "limit": 1},
        ) if module and name else []
        if rows:
            out.append(int(rows[0]["res_id"]))
        else:
            missing.append(xmlid)
    if missing:
        raise Refused("GROUP_NOT_FOUND " + ",".join(missing))
    return out


def _group_xmlids(rpc, ids: list[int]) -> list[str]:
    if not ids:
        return []
    rows = rpc.call(
        "ir.model.data", "search_read",
        [[["model", "=", "res.groups"], ["res_id", "in", list(ids)]]],
        {"fields": ["module", "name", "res_id"]},
    ) or []
    named = {int(r["res_id"]): f"{r['module']}.{r['name']}" for r in rows}
    return sorted(named.get(i, f"id:{i}") for i in ids)


def _reason(exc: Exception) -> str:
    """A short cause token for a failed JSON-2 call: the Odoo exception name
    and its message, or the shared client's ``ODOO_RPC_FAILED`` reason."""
    text = str(exc)
    if text.startswith("ODOO_RPC_FAILED "):
        return text.split()[1].rstrip(":")
    if ": {" in text:
        try:
            body = json.loads(text.split(": ", 1)[1])
            name = (body.get("name") or "").rsplit(".", 1)[-1]
            message = (body.get("message") or "").splitlines()[0][:200]
            return f"{name}: {message}" if name else message
        except (ValueError, AttributeError, IndexError):
            pass
    return type(exc).__name__


def _split(values: list[str] | None) -> list[str]:
    out: list[str] = []
    for value in values or []:
        out += [v.strip() for v in value.split(",") if v.strip()]
    return out


def _session_authenticate(login: str, password: str) -> tuple[int | None, str]:
    """Sign in on the local Odoo with the exact ``login``. Returns
    ``(uid, error_name)``; ``uid`` is None on a refusal."""
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
    )
    body = json.dumps({
        "jsonrpc": "2.0", "method": "call", "id": 1,
        "params": {"db": db_name(), "login": login, "password": password},
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{_URL}/web/session/authenticate", data=body,
        headers={"Content-Type": "application/json; charset=utf-8"}, method="POST",
    )
    try:
        with opener.open(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        return None, f"HTTP_{exc.code}"
    except OSError:
        return None, "odoo_down"
    uid = (data.get("result") or {}).get("uid") if isinstance(data, dict) else None
    if uid:
        return int(uid), ""
    error = (data.get("error") or {}).get("data") or {} if isinstance(data, dict) else {}
    return None, (error.get("name") or "AccessDenied").rsplit(".", 1)[-1]


def _report_check(login: str, password: str) -> bool:
    uid, _error = _session_authenticate(login, password)
    print(f"CHECK_OK {login}" if uid else f"CHECK_FAILED {login}")
    return bool(uid)


def _exact_user(rpc, login: str) -> dict:
    rows = _users_any_case(rpc, login)
    exact = [r for r in rows if r.get("login") == login]
    if exact:
        return exact[0]
    if rows:
        raise Refused("\n".join(f"LOGIN_CASE_MISMATCH stored={r['login']}" for r in rows))
    raise Refused(f"LOGIN_NOT_FOUND {login}")


def _normalized(raw: str) -> str:
    try:
        login = normalize_login(raw)
    except ValueError:
        raise Refused(f"LOGIN_INVALID {raw.strip()}") from None
    if "@" not in login:
        raise Refused(f"LOGIN_INVALID {login}")
    return login


# --------------------------------------------------------------------------- #
# commands                                                                     #
# --------------------------------------------------------------------------- #
def cmd_create(args) -> int:
    login = _normalized(args.login)
    password = _password_from_env(args.password_env)
    rpc = OdooRPC()
    rows = _users_any_case(rpc, login)
    for row in rows:
        if row.get("login") == login:
            raise Refused(f"EXISTS {login} id={row['id']}")
    if rows:
        raise Refused(f"EXISTS_CASE_VARIANT {rows[0]['login']}")

    groups: set[int] = set()
    if args.like:
        like = _users_any_case(rpc, args.like)
        exact = [r for r in like if r.get("login") in (args.like.strip(), args.like.strip().lower())]
        pick = exact or like
        if not pick:
            raise Refused(f"LIKE_NOT_FOUND {args.like.strip()}")
        if len(pick) > 1:
            raise Refused("LIKE_AMBIGUOUS " + ",".join(r["login"] for r in pick))
        groups |= {int(g) for g in pick[0].get("group_ids") or []}
    groups |= set(_group_ids(rpc, _split(args.groups)))
    groups -= set(_group_ids(rpc, _split(args.without)))
    if not groups:
        raise Refused("GROUPS_REQUIRED — pass --like <login> or --groups <xmlid,...>")

    vals = {
        "name": args.name.strip(),
        "login": login,
        "email": login,
        "group_ids": [[6, 0, sorted(groups)]],
    }
    if password:
        vals["password"] = password
    new_id = as_id(rpc.call("res.users", "create", [vals]))
    stored = rpc.call("res.users", "read", [[new_id]], {"fields": ["login", "group_ids"]}) or [{}]
    print(f"CREATED {login} id={new_id}")
    print("GROUPS " + ",".join(_group_xmlids(rpc, stored[0].get("group_ids") or [])))
    if not password:
        print("NO_PASSWORD_YET — run set-password once the person set one on the secure link")
        return 0
    return 0 if _report_check(login, password) else 1


def cmd_set_password(args) -> int:
    login = _normalized(args.login)
    password = _password_from_env(args.password_env)
    rpc = OdooRPC()
    user = _exact_user(rpc, login)
    rpc.call("res.users", "write", [[int(user["id"])], {"password": password}])
    print(f"PASSWORD_SET {login}")
    return 0 if _report_check(login, password) else 1


def cmd_check(args) -> int:
    typed = args.login  # exact, as the person typed it — never normalized
    password = _password_from_env(args.password_env)
    uid, error = _session_authenticate(typed, password)
    if uid:
        print(f"CHECK_OK {typed}")
        return 0
    print(f"CHECK_FAILED {typed}")
    if error == "odoo_down":
        print("ODOO_DOWN")
        return 1
    try:
        rows = _users_any_case(OdooRPC(), typed)
    except RuntimeError as exc:
        print(f"CAUSE_UNKNOWN ({_reason(exc)})")
        return 1
    exact = [r for r in rows if r.get("login") == typed]
    if exact and not exact[0].get("active", True):
        print(f"USER_ARCHIVED {typed}")
    elif exact:
        print(f"PASSWORD_REJECTED {typed}")
        if error and error != "AccessDenied":
            print(f"AUTH_ERROR {error}")
    elif rows:
        for row in rows:
            print(f"LOGIN_CASE_MISMATCH stored={row['login']}")
    else:
        print(f"LOGIN_NOT_FOUND {typed}")
    return 1


def cmd_can(_args) -> int:
    try:
        rpc = OdooRPC()
        me = rpc.call("res.users", "read", [[rpc.uid]], {"fields": ["login"]}) or [{}]
        print(f"KEY_USER {me[0].get('login') or rpc.uid}")
        allowed = rpc._json2("res.users", "has_access", ids=[], operation="create")
    except RuntimeError as exc:
        print(f"CAN_CREATE_USERS unknown ({_reason(exc)})")
        return 1
    print(f"CAN_CREATE_USERS {'yes' if allowed else 'no'}")
    return 0


def _rewrite_admin_files(renames: dict[str, str]) -> None:
    """An ``.odoo-admin`` ``login=`` line that held an old spelling gets the new
    one. Otherwise ``setup_admin.py`` sees a different stored login and asks
    for the owner's password again. Never prints a password."""
    paths = list(admin_candidates()) + [home() / "odoo-site" / ".odoo-admin"]
    for path in dict.fromkeys(paths):
        if not path.is_file():
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        changed = False
        for i, line in enumerate(lines):
            if line.startswith("login="):
                old = line.split("=", 1)[1].strip()
                if old in renames:
                    lines[i] = f"login={renames[old]}"
                    changed = True
        if changed:
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            os.chmod(path, 0o600)
            print(f"ADMIN_FILE_UPDATED {path}")


def cmd_lowercase_all(_args) -> int:
    try:
        rpc = OdooRPC()
    except RuntimeError as exc:
        text = str(exc)
        if "odoo_down" in text and (home() / "odoo-site" / "odoo").is_dir():
            # Odoo is on this box but does not answer now. Do not mark the
            # migration done; the next turn runs it again.
            print("LOWERCASE_LATER odoo_down — do not mark; run again next turn")
            return 0
        reason = "no_odoo" if "odoo_down" in text else "no_key"
        print(f"LOWERCASE_NOTHING_TO_DO {reason}")
        return 0
    users = rpc.call(
        "res.users", "search_read", [[]],
        {"fields": ["id", "login", "email", "share"], "context": _ALL},
    ) or []
    by_lower: dict[str, list[dict]] = {}
    for user in users:
        by_lower.setdefault((user.get("login") or "").lower(), []).append(user)
    renames: dict[str, str] = {}
    twins = 0
    for user in users:
        old = user.get("login") or ""
        new = old.lower()
        if user.get("share") or old == new:
            continue
        others = [u for u in by_lower[new] if u["id"] != user["id"]]
        if others:
            for other in others:
                print(f"TWIN {old} {other['login']}")
            twins += 1
            continue
        vals = {"login": new}
        if (user.get("email") or "") == old:
            vals["email"] = new
        rpc.call("res.users", "write", [[int(user["id"])], vals])
        renames[old] = new
        print(f"LOWERCASED {old} -> {new}")
    _rewrite_admin_files(renames)
    print(f"LOWERCASE_DONE changed={len(renames)} twins={twins}")
    return 0


def main(argv: list[str] | None = None) -> int:
    # allow_abbrev=False: ``--password`` must not match ``--password-env``.
    ap = _Parser(description=__doc__.split("\n\n", 1)[0], allow_abbrev=False)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("create", allow_abbrev=False, help="make one internal user")
    p.add_argument("--login", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--like", help="copy this user's groups exactly")
    p.add_argument("--groups", action="append", help="group xmlids to add (comma list)")
    p.add_argument("--without", action="append", help="group xmlids to leave out (comma list)")
    p.add_argument("--password-env", metavar="VAR")
    p = sub.add_parser("set-password", allow_abbrev=False,
                       help="set the password of an existing user")
    p.add_argument("--login", required=True)
    p.add_argument("--password-env", metavar="VAR", required=True)
    p = sub.add_parser("check", allow_abbrev=False,
                       help="sign in on this box with the exact login typed")
    p.add_argument("--login", required=True)
    p.add_argument("--password-env", metavar="VAR", required=True)
    sub.add_parser("can", allow_abbrev=False, help="may the key's user create logins?")
    sub.add_parser("lowercase-all", allow_abbrev=False, help="the lowercase-logins migration")
    args = ap.parse_args(argv)
    handler = {
        "create": cmd_create,
        "set-password": cmd_set_password,
        "check": cmd_check,
        "can": cmd_can,
        "lowercase-all": cmd_lowercase_all,
    }[args.cmd]
    try:
        return handler(args)
    except Refused as exc:
        print(str(exc))
        return 1
    except RuntimeError as exc:
        print(f"TEAM_LOGIN_FAILED {_reason(exc)}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
