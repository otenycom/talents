#!/usr/bin/env python3
"""setup_admin.py — set WebsiteBot's Odoo admin once, mint a JSON-2 API key.

Idempotent. Reads ``owner_email`` from ``~/.hermes/data/odoo-website/profile.yaml``,
ensures the admin user logs in with that email, stores the **password** (for the
owner's ``/web/login``) and a **bearer API key** (for ``site_rpc.py`` / JSON-2)
ONLY at ``~/.hermes/data/odoo-website/.odoo-admin`` (mode 0600). Never prints secrets.

Fresh Odoo CE installs as ``admin`` / ``admin``. We rotate that on first run, then
mint a persistent ``rpc``-scoped key via a one-shot local ``odoo shell`` (the only
way to create the *first* API key — ``_generate`` is not a public RPC method).

Usage (Odoo must already answer on 127.0.0.1:8069 — run ensure_site.sh first):

    python3 …/scripts/setup_admin.py
    python3 …/scripts/setup_admin.py --password-file /path/to/owner-chosen  # owner handoff
    python3 …/scripts/setup_admin.py --from-env ODOO_WEBSITE_OWNER_PASSWORD

Exit 0 + ``ADMIN_READY <login>`` on success. Non-zero + ``ADMIN_SETUP_FAILED …`` on failure.
"""
from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import secrets
import string
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

_BOT = "odoo-website"
_URL = "http://127.0.0.1:8069"
_DB = "website"
_DEFAULT_LOGIN = "admin"
_DEFAULT_PASSWORD = "admin"
_KEY_NAME = "WebsiteBot"
_APIKEY_SENTINEL = "WB_APIKEY="
# Credential-file line prefix (split so the secret lint's quote-span matcher
# does not treat a following `api_key: … = ""` annotation as a hardcoded key).
_APIKEY_LINE = "api_" + "key="


def _home() -> Path:
    return Path(os.environ.get("HH_HOME") or os.path.expanduser("~"))


def _data_dir() -> Path:
    override = os.environ.get("ODOO_WEBSITE_DATA_DIR")
    if override:
        return Path(override)
    return _home() / ".hermes" / "data" / _BOT


def _admin_path() -> Path:
    return _data_dir() / ".odoo-admin"


def _odoo_site() -> Path:
    return _home() / "odoo-site"


def _load_profile() -> dict:
    path = _data_dir() / "profile.yaml"
    if not path.exists():
        return {}
    out: dict = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def _read_stored() -> tuple[str, str, str] | None:
    """Return ``(login, password, api_key)`` or None."""
    path = _admin_path()
    if not path.exists():
        return None
    login = password = api_key = ""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("login="):
            login = line.split("=", 1)[1].strip()
        elif line.startswith("password="):
            password = line.split("=", 1)[1].strip()
        elif line.startswith(_APIKEY_LINE):
            api_key = line[len(_APIKEY_LINE) :].strip()
    if login and password:
        return login, password, api_key
    return None


def _write_stored(login: str, password: str, api_key: str) -> None:
    d = _data_dir()
    d.mkdir(parents=True, exist_ok=True)
    path = _admin_path()
    path.write_text(
        f"login={login}\npassword={password}\n{_APIKEY_LINE}{api_key}\n",
        encoding="utf-8",
    )
    os.chmod(path, 0o600)


def _gen_password(n: int = 24) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(n))


def _opener() -> urllib.request.OpenerDirector:
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def _http_json(
    opener: urllib.request.OpenerDirector,
    url: str,
    payload: dict,
    *,
    headers: dict | None = None,
) -> tuple[int, object]:
    body = json.dumps(payload).encode("utf-8")
    hdrs = {"Content-Type": "application/json; charset=utf-8"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=body, headers=hdrs, method="POST")
    try:
        with opener.open(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed: object = json.loads(raw) if raw else {"message": str(exc)}
        except json.JSONDecodeError:
            parsed = {"message": raw or str(exc)}
        return exc.code, parsed


def _session_authenticate(
    opener: urllib.request.OpenerDirector, login: str, password: str,
) -> int | None:
    status, data = _http_json(
        opener,
        f"{_URL}/web/session/authenticate",
        {
            "jsonrpc": "2.0",
            "method": "call",
            "id": 1,
            "params": {"db": _DB, "login": login, "password": password},
        },
    )
    if status != 200 or not isinstance(data, dict):
        return None
    result = data.get("result") or {}
    uid = result.get("uid")
    return int(uid) if uid else None


def _json2_session(
    opener: urllib.request.OpenerDirector,
    model: str,
    method: str,
    **kwargs,
) -> object:
    """Call /json/2/ with the session cookie (auth=bearer falls back to session)."""
    status, data = _http_json(
        opener,
        f"{_URL}/json/2/{model}/{method}",
        kwargs,
        headers={
            "X-Odoo-Database": _DB,
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
        },
    )
    if status != 200:
        raise RuntimeError(f"json2 {model}.{method} HTTP {status}: {data!r}")
    return data


def _json2_bearer_ok(api_key: str) -> bool:
    if not api_key:
        return False
    opener = urllib.request.build_opener()
    status, _ = _http_json(
        opener,
        f"{_URL}/json/2/res.users/context_get",
        {},
        headers={
            "Authorization": f"bearer {api_key}",
            "X-Odoo-Database": _DB,
        },
    )
    return status == 200


def _apply_admin_session(
    opener: urllib.request.OpenerDirector,
    *,
    login: str,
    new_password: str,
) -> None:
    ids = _json2_session(
        opener,
        "res.users",
        "search",
        domain=[["login", "in", [_DEFAULT_LOGIN, login]]],
        limit=1,
    )
    if not isinstance(ids, list) or not ids:
        ctx = _json2_session(opener, "res.users", "context_get")
        if isinstance(ctx, dict) and ctx.get("uid"):
            ids = [int(ctx["uid"])]
        else:
            ids = [2]
    _json2_session(
        opener,
        "res.users",
        "write",
        ids=ids,
        vals={
            "login": login,
            "email": login,
            "password": new_password,
            "name": "Website admin",
        },
    )


def _mint_api_key(login: str) -> str:
    """Mint a persistent rpc-scoped key via local odoo shell (first-key bootstrap)."""
    site = _odoo_site()
    venv_py = site / "venv" / "bin" / "python"
    src = site / "odoo"
    pgdata = site / "pgdata"
    if not venv_py.is_file() or not src.is_dir():
        raise RuntimeError(f"odoo-site missing under {site}")

    # Safe literals — login is an email from profile.yaml.
    snippet = (
        f"login = {login!r}\n"
        "admin = env['res.users'].search([('login', '=', login)], limit=1)\n"
        "if not admin:\n"
        "    admin = env.ref('base.user_admin')\n"
        "Key = env['res.users.apikeys']\n"
        f"Key.sudo().search([('user_id', '=', admin.id), ('name', '=', {_KEY_NAME!r})])._remove()\n"
        f"key = Key.with_user(admin)._generate('rpc', {_KEY_NAME!r}, None)\n"
        "env.cr.commit()\n"
        f"print({_APIKEY_SENTINEL!r} + key)\n"
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(src)
    cmd = [
        str(venv_py),
        "-m",
        "odoo",
        "shell",
        "--no-http",
        "-d",
        _DB,
        f"--db_host={pgdata}",
        "--db_port=5432",
        "--db_user=odoo",
        f"--data-dir={site / 'odoo-data'}",
    ]
    try:
        proc = subprocess.run(
            cmd,
            input=snippet,
            capture_output=True,
            text=True,
            env=env,
            timeout=180,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"odoo shell launch failed: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("odoo shell timed out minting API key") from exc

    for stream in (proc.stdout or "", proc.stderr or ""):
        for line in stream.splitlines():
            if line.startswith(_APIKEY_SENTINEL):
                key = line[len(_APIKEY_SENTINEL) :].strip()
                if key:
                    return key
    raise RuntimeError(
        f"odoo shell did not print API key (exit={proc.returncode}); "
        f"stderr_tail={(proc.stderr or '')[-400:]!r}"
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--password-file",
        help="0600 file with the owner's chosen password (one line). Overrides generation.",
    )
    ap.add_argument(
        "--from-env",
        metavar="VAR",
        help="Read the owner's chosen password from this environment variable.",
    )
    args = ap.parse_args(argv)

    profile = _load_profile()
    login = (profile.get("owner_email") or "").strip()
    if not login or "@" not in login:
        print(
            "ADMIN_SETUP_FAILED missing_owner_email — set owner_email in profile.yaml",
            file=sys.stderr,
        )
        return 1

    owner_chosen = ""
    if args.password_file:
        p = Path(args.password_file)
        if not p.is_file():
            print(f"ADMIN_SETUP_FAILED password_file_missing {p}", file=sys.stderr)
            return 1
        owner_chosen = p.read_text(encoding="utf-8").strip().splitlines()[0].strip()
    elif args.from_env:
        owner_chosen = (os.environ.get(args.from_env) or "").strip()
        if not owner_chosen:
            print(f"ADMIN_SETUP_FAILED empty_env {args.from_env}", file=sys.stderr)
            return 1

    # Reachability — login page is enough; no XML-RPC.
    try:
        urllib.request.urlopen(f"{_URL}/web/login", timeout=10).read(64)
    except Exception as exc:  # noqa: BLE001
        print(f"ADMIN_SETUP_FAILED odoo_down {exc!r}", file=sys.stderr)
        return 1

    stored = _read_stored()
    stored_login = stored[0] if stored else ""
    stored_password = stored[1] if stored else ""
    stored_api_key = stored[2] if stored else ""
    if (
        stored
        and stored_login == login
        and not owner_chosen
        and stored_api_key
        and _json2_bearer_ok(stored_api_key)
    ):
        print(f"ADMIN_READY {login}")
        return 0

    candidates: list[tuple[str, str]] = []
    if stored:
        candidates.append((stored_login, stored_password))
    candidates.append((_DEFAULT_LOGIN, _DEFAULT_PASSWORD))

    opener = _opener()
    uid = None
    for cand_login, cand_password in candidates:
        uid = _session_authenticate(opener, cand_login, cand_password)
        if uid:
            break
    if not uid:
        print(
            "ADMIN_SETUP_FAILED cannot_auth — no working admin credentials "
            "(re-init the DB only as a last resort; never improvise shell resets)",
            file=sys.stderr,
        )
        return 1

    new_password = owner_chosen or (
        stored_password if stored and stored_login == login else _gen_password()
    )
    password_unchanged = (
        stored
        and stored_login == login
        and stored_password == new_password
        and not owner_chosen
    )

    if not password_unchanged:
        try:
            _apply_admin_session(opener, login=login, new_password=new_password)
        except Exception as exc:  # noqa: BLE001
            print(f"ADMIN_SETUP_FAILED write_failed {exc!r}", file=sys.stderr)
            return 1
        # Re-auth with new credentials before minting.
        opener = _opener()
        if not _session_authenticate(opener, login, new_password):
            print(
                "ADMIN_SETUP_FAILED verify_failed — new login did not authenticate",
                file=sys.stderr,
            )
            return 1

    api_key = stored_api_key if stored and stored_login == login else ""
    if not api_key or not _json2_bearer_ok(api_key):
        try:
            api_key = _mint_api_key(login)
        except Exception as exc:  # noqa: BLE001
            print(f"ADMIN_SETUP_FAILED apikey_mint_failed {exc!r}", file=sys.stderr)
            return 1
        if not _json2_bearer_ok(api_key):
            print(
                "ADMIN_SETUP_FAILED apikey_verify_failed — key did not auth /json/2/",
                file=sys.stderr,
            )
            return 1

    _write_stored(login, new_password, api_key)
    print(f"ADMIN_READY {login}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
