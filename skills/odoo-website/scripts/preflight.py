#!/usr/bin/env python3
"""preflight — the ONE per-turn context call for WebsiteBot (odoo-website).

Answers, in a single read-only call, the questions the triage would otherwise fan out into
several: is the site engine installed + a profile set (can I build now?), is Odoo actually
serving locally, and the few profile fields the persona needs. Pure / side-effect-free / exit
code always 0 (readiness is in the OUTPUT, not the exit code — a non-zero would make the LLM's
terminal call look failed).

    python3 ~/.hermes/skills/talents/odoo-website/scripts/preflight.py

Prints a compact parseable block:
  READY   — yes|no  (Odoo installed + profile fields set)
  ODOO    — serving|down  (is Odoo answering on 127.0.0.1:8069 right now?)
  PROFILE — site_name / site_slug / language (so the triage never re-reads profile.yaml)
  MISSING — the blocking artifacts when READY is no
"""
from __future__ import annotations

import os
from pathlib import Path

_BOT = "odoo-website"
_PORT = 8069
_REQUIRED_FIELDS = ("site_name", "site_purpose", "site_slug", "owner_email", "language")


def _home() -> Path:
    # HH_HOME lets tests / a relocated overlay stay hermetic (mirrors selfcheck.py).
    return Path(os.environ.get("HH_HOME") or os.path.expanduser("~"))


def _data_dir() -> Path:
    override = os.environ.get("ODOO_WEBSITE_DATA_DIR")
    if override:
        return Path(override)
    return _home() / ".hermes" / "data" / _BOT


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


def _installed() -> bool:
    base = _home() / "odoo-site"
    return (base / ".deps-installed").exists() and (base / "odoo" / "odoo").is_dir()


def _odoo_serving() -> bool:
    import http.client
    try:
        conn = http.client.HTTPConnection("127.0.0.1", _PORT, timeout=3)
        conn.request("GET", "/web/login")
        resp = conn.getresponse()
        return resp.status < 500
    except Exception:  # noqa: BLE001
        return False


def main() -> int:
    profile = _load_profile()
    missing = []
    if not _installed():
        missing.append("odoo_install")
    unset = [f for f in _REQUIRED_FIELDS if not (profile.get(f) or "").strip()]
    if unset:
        missing.append("profile:" + ",".join(unset))
    ready = not missing
    print(f"READY: {'yes' if ready else 'no'}")
    print(f"ODOO: {'serving' if _odoo_serving() else 'down'}")
    print("PROFILE: "
          f"site_name={profile.get('site_name') or '-'} "
          f"site_slug={profile.get('site_slug') or '-'} "
          f"language={profile.get('language') or '-'}")
    if missing:
        print("MISSING: " + " ".join(missing))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
