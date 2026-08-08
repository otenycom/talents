#!/usr/bin/env python3
"""Rewrite postgresql.conf lc_* settings the box does not have → C.UTF-8.

A Postgres cluster created on an Ubuntu VM pins lc_messages/lc_monetary/lc_numeric/
lc_time to en_US.UTF-8. That locale is missing from the gVisor container image, so a
*carried* cluster (Max→Power) fails to start with:

    FATAL: configuration file ".../pgdata/postgresql.conf" contains errors

A fresh initdb on the container works (it picks a locale the image has). This helper
runs before pgserver starts in ensure_site.sh — the single owner of the rewrite
(platform site_carry deliberately does NOT touch postgresql.conf).

Idempotent: no-op when the conf is absent, when every lc_* is already available, or
when values are already C.UTF-8 / C.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

_LC_KEYS = ("lc_messages", "lc_monetary", "lc_numeric", "lc_time")
_FALLBACK = "C.UTF-8"
# Matches: lc_messages = 'en_US.UTF-8'  (optional spaces/quotes)
_LC_RE = re.compile(
    r"^(?P<key>lc_(?:messages|monetary|numeric|time))\s*=\s*'(?P<val>[^']*)'\s*$",
    re.MULTILINE,
)


def available_locales() -> set[str]:
    """Names from `locale -a`, normalized (strip charset suffixes like .utf8)."""
    try:
        out = subprocess.check_output(["locale", "-a"], text=True, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.CalledProcessError):
        return set()
    names: set[str] = set()
    for line in out.splitlines():
        name = line.strip()
        if not name:
            continue
        names.add(name)
        # locale -a often prints en_US.utf8; conf may say en_US.UTF-8
        names.add(name.replace(".utf8", ".UTF-8").replace(".utf-8", ".UTF-8"))
        names.add(name.replace(".UTF-8", ".utf8"))
    return names


def _pick_fallback(available: set[str], preferred: str = _FALLBACK) -> str | None:
    """Conf-spelling locale to rewrite to, or None if the box has nothing usable."""
    if preferred in available or preferred.replace(".UTF-8", ".utf8") in available:
        return preferred
    if "C.utf8" in available or "C.UTF-8" in available:
        return "C.UTF-8"
    if "C" in available or "POSIX" in available:
        return "C"
    return None


def normalize_conf(text: str, available: set[str], *, fallback: str = _FALLBACK) -> tuple[str, list[str]]:
    """Return (new_text, list of 'key: old → new' change notes)."""
    target = _pick_fallback(available, fallback)
    if target is None:
        # Nothing we can rewrite to — leave the file alone and let Postgres fail loudly.
        return text, []
    changes: list[str] = []

    def _sub(m: re.Match[str]) -> str:
        key, val = m.group("key"), m.group("val")
        if val in available or val in ("C", "C.UTF-8", "C.utf8"):
            return m.group(0)
        changes.append(f"{key}: {val!r} → {target!r}")
        return f"{key} = '{target}'"

    new = _LC_RE.sub(_sub, text)
    return new, changes


def normalize_pgdata(pgdata: Path) -> list[str]:
    conf = pgdata / "postgresql.conf"
    if not conf.is_file():
        return []
    text = conf.read_text(encoding="utf-8", errors="replace")
    new, changes = normalize_conf(text, available_locales())
    if not changes:
        return []
    conf.write_text(new, encoding="utf-8")
    return changes


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    pgdata = Path(argv[0] if argv else os.path.expanduser("~/odoo-site/pgdata"))
    changes = normalize_pgdata(pgdata)
    for c in changes:
        print(f"normalize_pg_locales: {c}", file=sys.stderr)
    if changes:
        print(f"NORMALIZE_PG_LOCALES changed={len(changes)}")
    else:
        print("NORMALIZE_PG_LOCALES noop")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
