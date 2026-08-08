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
_C_VALUES = ("C", "C.UTF-8", "C.utf8")
# Matches:  lc_messages = 'en_US.UTF-8'\t\t# locale for system error message
#
# The trailing group is load-bearing. Postgres ALWAYS writes these four settings with a
# tab + comment after the value, and the first version of this pattern anchored `$`
# straight after the closing quote — so it matched nothing on a real cluster, rewrote
# nothing, and printed "noop" while the carried database went on refusing to start
# (found live on hh00412, 2026-08-08). Keep `rest` and put it back verbatim.
_LC_RE = re.compile(
    r"^(?P<key>lc_(?:messages|monetary|numeric|time))(?P<mid>\s*=\s*)'(?P<val>[^']*)'(?P<rest>.*)$",
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
        if val in available or val in _C_VALUES:
            return m.group(0)
        changes.append(f"{key}: {val!r} → {target!r}")
        # Preserve the spacing and the trailing comment exactly as Postgres wrote them.
        return f"{key}{m.group('mid')}'{target}'{m.group('rest')}"

    new = _LC_RE.sub(_sub, text)
    return new, changes


def unavailable_lc_values(text: str, available: set[str]) -> list[str]:
    """Every ``lc_*`` in ``text`` naming a locale this box does not have.

    The post-condition, and the reason "noop" is no longer trusted on its own: printing
    "nothing to do" is correct when the conf is already fine and catastrophic when the
    rewrite silently matched nothing. Only this can tell the two apart."""
    return [
        f"{m.group('key')}={m.group('val')!r}"
        for m in _LC_RE.finditer(text)
        if m.group("val") and m.group("val") not in available
        and m.group("val") not in _C_VALUES
    ]


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
    # VERIFY THE OUTCOME, not the action. A silent "noop" is what let a broken regex hide
    # for a whole build: the rewrite matched nothing, said it was fine, and Postgres FATAL'd
    # a minute later on a message nobody connected back to here. If any lc_* still names a
    # locale this box lacks, the cluster CANNOT start — say so now, loudly, from the place
    # that knows why.
    conf = pgdata / "postgresql.conf"
    if conf.is_file():
        bad = unavailable_lc_values(
            conf.read_text(encoding="utf-8", errors="replace"), available_locales())
        if bad:
            print(
                "NORMALIZE_PG_LOCALES FAILED: postgresql.conf still requires locales this "
                f"box does not have: {', '.join(bad)}. Postgres will refuse to start. "
                "Install the locale, or make a usable C/C.UTF-8 locale available.",
                file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
