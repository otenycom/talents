#!/usr/bin/env python3
"""Put CRM first in the Odoo app menu on a Community box.

Odoo 19 ships Discuss at sequence 5 and CRM at 25. ``/odoo`` then opens
the first root app, which is Discuss. After a consumer Talent installs
``crm``, this script writes CRM's root menu to sequence 1 and sets the
admin Home Action to My Pipeline. Idempotent. Skip when CRM is not
installed.

Usage:
    python3 pin_crm_home.py
    python3 pin_crm_home.py --require-crm

Prints ``CRM_HOME_PINNED`` or ``CRM_HOME_SKIPPED no_crm``. Exit 0 on
those. ``--require-crm`` exits 1 on skip, so a just-finished
``install_modules.sh crm`` cannot silently leave Discuss first.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

TARGET_SEQUENCE = 1
CRM_MENU = "crm.crm_menu_root"
CRM_ACTION = "crm.action_your_pipeline"
ADMIN_USER = "base.user_admin"
_DB = "website"


def _home() -> Path:
    return Path(os.environ.get("HH_HOME") or Path.home())


def _odoo_site(home: Path | None = None) -> Path:
    return (home or _home()) / "odoo-site"


def apply_pin(ref, commit) -> str:
    """Write CRM first. ``ref`` is ``env.ref``. ``commit`` is ``env.cr.commit``."""
    crm = ref(CRM_MENU, raise_if_not_found=False)
    if not crm:
        return "CRM_HOME_SKIPPED no_crm"
    action = ref(CRM_ACTION, raise_if_not_found=False)
    admin = ref(ADMIN_USER, raise_if_not_found=False)
    changed: list[str] = []
    if int(getattr(crm, "sequence", 0) or 0) != TARGET_SEQUENCE:
        crm.sequence = TARGET_SEQUENCE
        changed.append("sequence")
    if action is not None and admin is not None:
        current = getattr(getattr(admin, "action_id", None), "id", None)
        want = getattr(action, "id", None)
        if current != want:
            # Home Action is a Many2one to ir.actions.actions. Odoo 19 refuses
            # a record of the concrete ir.actions.server model, so assign the id.
            admin.action_id = want
            changed.append("home_action")
    commit()
    if changed:
        return "CRM_HOME_PINNED " + ",".join(changed)
    return "CRM_HOME_PINNED already"


def _db_cli_args(home: Path | None = None) -> list[str]:
    root = home or _home()
    site = _odoo_site(root)
    src = site / "odoo"
    addons = site / "addons"
    if (root / "postgres" / "data").is_dir():
        args = ["--db_host=127.0.0.1", "--db_port=5432", "--db_user=odoo"]
    else:
        args = [
            f"--db_host={site / 'pgdata'}",
            "--db_port=5432",
            "--db_user=odoo",
        ]
    args.append(f"--addons-path={src / 'addons'},{addons}")
    conf = site / "odoo.conf"
    if conf.is_file():
        args.append(f"--config={conf}")
    return args


def _snippet() -> str:
    here = str(Path(__file__).resolve().parent)
    return (
        f"import sys\n"
        f"sys.path.insert(0, {here!r})\n"
        "from pin_crm_home import apply_pin\n"
        "print(apply_pin(env.ref, env.cr.commit))\n"
    )


def _run_shell(home: Path | None = None) -> subprocess.CompletedProcess[str]:
    root = home or _home()
    site = _odoo_site(root)
    venv_py = site / "venv" / "bin" / "python"
    src = site / "odoo"
    if not venv_py.is_file() or not src.is_dir():
        raise RuntimeError(f"odoo-site missing under {site}")
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
        *_db_cli_args(root),
        f"--data-dir={site / 'odoo-data'}",
    ]
    return subprocess.run(
        cmd,
        input=_snippet(),
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
        check=False,
    )


def _result_line(proc: subprocess.CompletedProcess[str]) -> str | None:
    for stream in (proc.stdout or "", proc.stderr or ""):
        for line in stream.splitlines():
            if line.startswith("CRM_HOME_PINNED") or line.startswith(
                "CRM_HOME_SKIPPED"
            ):
                return line
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--require-crm",
        action="store_true",
        help="Exit 1 when CRM is not installed.",
    )
    args = ap.parse_args(argv)

    try:
        proc = _run_shell()
    except FileNotFoundError as exc:
        print(f"CRM_HOME_FAILED odoo_shell {exc}", file=sys.stderr)
        return 1
    except subprocess.TimeoutExpired:
        print("CRM_HOME_FAILED odoo_shell_timeout", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(f"CRM_HOME_FAILED {exc}", file=sys.stderr)
        return 1

    line = _result_line(proc)
    if line is None:
        print(
            "CRM_HOME_FAILED odoo_shell "
            f"(exit={proc.returncode}); "
            f"stderr_tail={(proc.stderr or '')[-400:]!r}",
            file=sys.stderr,
        )
        return 1
    print(line)
    if args.require_crm and line.startswith("CRM_HOME_SKIPPED"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
