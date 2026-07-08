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


def _mem_gb() -> float | None:
    """Total memory in GiB — the cgroup v2 hard cap (the container envelope) first, then
    /proc/meminfo (a VM's real RAM). OTENY_MEM_GB overrides (deployer injection / tests)."""
    override = (os.environ.get("OTENY_MEM_GB") or "").strip()
    if override:
        try:
            return float(override)
        except ValueError:
            pass
    try:
        v = Path("/sys/fs/cgroup/memory.max").read_text().strip()
        if v.isdigit():
            return int(v) / (1024 ** 3)
    except Exception:  # noqa: BLE001
        pass
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                return int(line.split()[1]) / (1024 ** 2)
    except Exception:  # noqa: BLE001
        pass
    return None


def _substrate() -> str:
    """The compute substrate: 'vm' (a dedicated machine) or 'container' (a packed gVisor
    sandbox). The deployer injects OTENY_SUBSTRATE from the tenant's isolation_tier; else
    probe the kernel (gVisor names itself in /proc/version). 'unknown' when neither says."""
    env = (os.environ.get("OTENY_SUBSTRATE") or "").strip().lower()
    if env in ("vm", "container"):
        return env
    try:
        if "gvisor" in Path("/proc/version").read_text().lower():
            return "container"
    except Exception:  # noqa: BLE001
        pass
    return "unknown"


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
    # The effective envelope — so the persona (and install_odoo.sh) can refuse an
    # under-provisioned box and tell the owner to upgrade to the Max plan (§14.2).
    mem = _mem_gb()
    print(f"SUBSTRATE: {_substrate()}")
    print(f"TIER: {os.environ.get('OTENY_TIER') or '-'}")
    print("MEM_GB: " + (f"{mem:.1f}" if mem is not None else "-"))
    if missing:
        print("MISSING: " + " ".join(missing))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
