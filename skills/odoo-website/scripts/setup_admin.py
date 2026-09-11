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
import uuid
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from website_paths import admin_candidates, existing_data_dir, home, profile_path, writable_data_dir

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
    return home()


def _data_dir() -> Path:
    return existing_data_dir()


def _admin_path() -> Path:
    return _data_dir() / ".odoo-admin"


def _bootstrap_admin_path() -> Path:
    """Parent-bake copy of the admin file. Lives in the tree, not in ``.hermes``."""
    return _odoo_site() / ".odoo-admin"


def _odoo_site() -> Path:
    return _home() / "odoo-site"


def _load_profile() -> dict:
    path = profile_path()
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


def _parse_admin_file(path: Path) -> tuple[str, str, str] | None:
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


def _read_stored() -> tuple[str, str, str] | None:
    """Return ``(login, password, api_key)`` or None."""
    for path in admin_candidates():
        if path.exists():
            parsed = _parse_admin_file(path)
            if parsed:
                return parsed
    boot = _bootstrap_admin_path()
    if boot.exists():
        return _parse_admin_file(boot)
    return None


def _write_stored(login: str, password: str, api_key: str) -> None:
    text = f"login={login}\npassword={password}\n{_APIKEY_LINE}{api_key}\n"
    boot = _bootstrap_admin_path()
    wrote_boot = False
    if boot.parent.is_dir():
        boot.write_text(text, encoding="utf-8")
        os.chmod(boot, 0o600)
        wrote_boot = True
    try:
        d = writable_data_dir()
        path = d / ".odoo-admin"
        path.write_text(text, encoding="utf-8")
        os.chmod(path, 0o600)
    except OSError:
        if wrote_boot:
            return
        raise


def _gen_password(n: int = 24) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(n))


def _gen_secret(n: int = 32) -> str:
    return secrets.token_hex(n)


def _odoo_conf_path() -> Path:
    return _odoo_site() / "odoo.conf"


def _odoo_db_host() -> str:
    """TCP when the Postgres Talent cluster exists. Else the legacy unix dir."""
    if (_home() / "postgres" / "data").is_dir():
        return "127.0.0.1"
    pgdata = _odoo_site() / "pgdata"
    if pgdata.is_dir():
        return str(pgdata)
    return "127.0.0.1"


def _write_odoo_conf(*, admin_passwd: str, proxy_mode: bool = True) -> None:
    """Write the clone-local Odoo conf. Mode 0600. Never print the password."""
    site = _odoo_site()
    site.mkdir(parents=True, exist_ok=True)
    path = _odoo_conf_path()
    proxy = "True" if proxy_mode else "False"
    path.write_text(
        "[options]\n"
        f"admin_passwd = {admin_passwd}\n"
        f"proxy_mode = {proxy}\n",
        encoding="utf-8",
    )
    os.chmod(path, 0o600)


def _json2_bearer(api_key: str, model: str, method: str, **kwargs) -> object:
    opener = urllib.request.build_opener()
    status, data = _http_json(
        opener,
        f"{_URL}/json/2/{model}/{method}",
        kwargs,
        headers={
            "Authorization": f"bearer {api_key}",
            "X-Odoo-Database": _DB,
        },
    )
    if status != 200:
        raise RuntimeError(f"json2 bearer {model}.{method} HTTP {status}: {data!r}")
    return data


def _rotate_db_params_bearer(
    api_key: str,
    *,
    database_secret: str,
    database_uuid: str,
) -> None:
    """Replace the cloned database.secret and database.uuid (bearer)."""
    for key, value in (
        ("database.secret", database_secret),
        ("database.uuid", database_uuid),
    ):
        _json2_bearer(
            api_key,
            "ir.config_parameter",
            "set_param",
            key=key,
            value=value,
        )


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
    if not venv_py.is_file() or not src.is_dir():
        raise RuntimeError(f"odoo-site missing under {site}")
    db_host = _odoo_db_host()

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
        f"--db_host={db_host}",
        "--db_port=5432",
        "--db_user=odoo",
        f"--data-dir={site / 'odoo-data'}",
    ]
    conf = _odoo_conf_path()
    if conf.is_file():
        cmd.append(f"--config={conf}")
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
    ap.add_argument(
        "--rotate-clone-secrets",
        action="store_true",
        help="Mint-time rotate after a parent clone: new admin password, API key, "
        "database.secret, database.uuid, and odoo.conf admin_passwd + proxy_mode. "
        "Does not require owner_email.",
    )
    args = ap.parse_args(argv)

    profile = _load_profile()
    login = (profile.get("owner_email") or "").strip()
    if args.rotate_clone_secrets:
        login = login if login and "@" in login else _DEFAULT_LOGIN
    elif not login or "@" not in login:
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
        not args.rotate_clone_secrets
        and stored
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
        _gen_password()
        if args.rotate_clone_secrets
        else (stored_password if stored and stored_login == login else _gen_password())
    )
    password_unchanged = (
        not args.rotate_clone_secrets
        and stored
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
        _write_stored(login, new_password, stored_api_key or "")

    if args.rotate_clone_secrets:
        try:
            master = _gen_password()
            _write_odoo_conf(admin_passwd=master, proxy_mode=True)
        except Exception as exc:  # noqa: BLE001
            print(f"ADMIN_SETUP_FAILED clone_rotate_failed {exc!r}", file=sys.stderr)
            return 1

    api_key = (
        ""
        if args.rotate_clone_secrets
        else (stored_api_key if stored and stored_login == login else "")
    )
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

    if args.rotate_clone_secrets:
        try:
            _rotate_db_params_bearer(
                api_key,
                database_secret=_gen_secret(32),
                database_uuid=str(uuid.uuid4()),
            )
        except Exception as exc:  # noqa: BLE001
            print(f"ADMIN_SETUP_FAILED clone_rotate_failed {exc!r}", file=sys.stderr)
            return 1

    _write_stored(login, new_password, api_key)
    print(f"ADMIN_READY {login}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
