#!/usr/bin/env python3
"""import_talent — install a shared Talent into the overlay (Phase 2, open import).

The owner shares a Talent someone else exported (an Oteny Talent Drop link or a zip)
and asks me to install it:

    python3 import_talent.py --url https://drop.oteny.bot/<id>/<slug>.zip
    python3 import_talent.py --zip /path/to/bundle.zip [--overwrite] [--slug <name>]

Import is **open** by design — the per-tenant VM is the isolation boundary (D1), so an
imported bundle is no new code-execution surface; nothing runs at import time (a
``SKILL.md`` is only read on a normal ``skill_view``). What this enforces is the
structural floor that keeps the *managed* overlay safe:

- a valid bundle — a ``SKILL.md`` with YAML frontmatter and a safe slug;
- **no path traversal** in the archive (a hard stop);
- it **never shadows an Oteny-managed Talent** (D34) — refused, not overwritten;
- it lands marked ``source: imported`` / ``verified: false`` (unverified, third-party);
- it never silently clobbers one of the owner's own Talents (``--overwrite`` is explicit).

A format/quality lint is deferred (Talents are versioned, so "which rules apply" is
itself a question — the exporter stamps the authoring-standard version for a future
version-aware gate). Pure (bytes in → an install under a sandbox home), so it is
unit-tested offline.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import shutil
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

# Mirror of deploy/skills.py DEFAULT_SKILLS — the always-delivered infra skills an
# import must never shadow, even when the on-VM manifest is absent (a dev box).
_DEFAULT_SKILLS = (
    "skill-translator", "index-reconciler", "oteny-cron-authoring",
    "oteny-set-timezone", "oteny-drop", "oteny-talent-authoring",
    "talent-authoring-standard",
)
_SAFE_SLUG = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


class TalentImportError(RuntimeError):
    """A hard, security-relevant rejection (e.g. a path-traversal archive)."""


def _hermes_home(override=None) -> Path:
    if override is not None:
        return Path(override)
    env = os.environ.get("HH_HERMES_HOME") or os.environ.get("HERMES_HOME")
    if env:
        return Path(env)
    home = os.environ.get("HH_HOME")
    return (Path(home) if home else Path.home()) / ".hermes"


def _protected_slugs(home: Path) -> set[str]:
    slugs = set(_DEFAULT_SKILLS)
    manifest = home / ".hermeshost-manifest.json"
    if manifest.is_file():
        try:
            data = json.loads(manifest.read_text())
            slugs |= set(data.get("bundles") or [])
        except (ValueError, OSError):
            pass
    return slugs


def _detect_fmt(blob: bytes, fmt: str | None) -> str:
    if fmt:
        return fmt
    if blob[:4] == b"PK\x03\x04":
        return "zip"
    if blob[:2] == b"\x1f\x8b" or blob[:5] == b"ustar":
        return "tar"
    return "zip"


def _safe_members(names, dest: Path):
    """Yield archive member names, raising on anything that escapes ``dest``."""
    dest_res = dest.resolve()
    for name in names:
        if not name or name.endswith("/"):
            continue
        norm = os.path.normpath(name)
        if os.path.isabs(name) or norm.startswith("..") or ".." in Path(norm).parts:
            raise TalentImportError(f"unsafe path in archive: {name!r}")
        target = (dest / norm).resolve()
        if dest_res != target and dest_res not in target.parents:
            raise TalentImportError(f"archive member escapes destination: {name!r}")
        yield name, norm


def _extract(blob: bytes, fmt: str, dest: Path) -> None:
    if fmt == "zip":
        with zipfile.ZipFile(io.BytesIO(blob)) as zf:
            for name, norm in _safe_members(zf.namelist(), dest):
                out = dest / norm
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(zf.read(name))
    else:
        with tarfile.open(fileobj=io.BytesIO(blob)) as tar:
            members = {m.name: m for m in tar.getmembers() if m.isfile()}
            for name, norm in _safe_members(members.keys(), dest):
                out = dest / norm
                out.parent.mkdir(parents=True, exist_ok=True)
                src = tar.extractfile(members[name])
                out.write_bytes(src.read() if src else b"")


def _bundle_root(extracted: Path) -> Path:
    """The dir that holds the bundle's top-level SKILL.md (handles a slug-rooted tar)."""
    if (extracted / "SKILL.md").is_file():
        return extracted
    children = [c for c in extracted.iterdir() if c.is_dir()]
    if len(children) == 1 and (children[0] / "SKILL.md").is_file():
        return children[0]
    # last resort: the shallowest SKILL.md
    found = sorted(extracted.rglob("SKILL.md"), key=lambda p: len(p.parts))
    if found:
        return found[0].parent
    return extracted


def _has_frontmatter(skill_md: Path) -> bool:
    if not skill_md.is_file():
        return False
    text = skill_md.read_text(errors="replace")
    if not text.startswith("---"):
        return False
    end = text.find("\n---", 3)
    return end != -1 and bool(re.search(r"(?m)^name:\s*\S", text[:end]))


def install(
    *, archive: bytes, hermes_home=None, fmt: str | None = None,
    slug_override: str | None = None, overwrite: bool = False, imported_from: str | None = None,
) -> dict:
    """Install a Talent archive into ``~/.hermes/skills/talents/``; return a DTO dict."""
    home = _hermes_home(hermes_home)
    talents = home / "skills" / "talents"
    talents.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as td:
        staging = Path(td) / "x"
        staging.mkdir()
        _extract(archive, _detect_fmt(archive, fmt), staging)  # raises on traversal
        root = _bundle_root(staging)

        if not (root / "SKILL.md").is_file():
            return {"installed": False, "reason": "no SKILL.md — not a Talent bundle"}
        if not _has_frontmatter(root / "SKILL.md"):
            return {"installed": False, "reason": "SKILL.md has no YAML frontmatter"}

        slug = slug_override or (root.name if root is not staging else None)
        if not slug or not _SAFE_SLUG.match(slug):
            return {"installed": False, "reason": f"unsafe or missing slug: {slug!r}"}
        if slug in _protected_slugs(home):
            return {
                "installed": False,
                "reason": f"{slug!r} is an Oteny-managed Talent — import can't shadow it",
            }
        dest = talents / slug
        if dest.exists() and not overwrite:
            return {
                "installed": False,
                "reason": f"{slug!r} already exists — pass overwrite to replace it",
            }

        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(root, dest)
        _stamp_imported(dest, slug, imported_from)

    return {"installed": True, "slug": slug, "path": str(dest), "verified": False}


def _stamp_imported(dest: Path, slug: str, imported_from: str | None) -> None:
    """Mark the installed Talent as unverified third-party content."""
    man_path = dest / "manifest.json"
    manifest = {}
    if man_path.is_file():
        try:
            manifest = json.loads(man_path.read_text())
        except ValueError:
            manifest = {}
    manifest.update({"slug": slug, "source": "imported", "verified": False})
    if imported_from:
        manifest["imported_from"] = imported_from
    man_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


def _fetch(url: str) -> bytes:
    from urllib.request import Request, urlopen  # stdlib; only when --url is used

    with urlopen(Request(url, headers={"User-Agent": "oteny-talent-import"}), timeout=30) as r:
        return r.read()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Install a shared Talent (open import).")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--url", help="a drop URL of a Talent zip/tar.gz")
    src.add_argument("--zip", dest="path", help="a local Talent zip/tar.gz path")
    ap.add_argument("--slug", dest="slug_override", help="override the installed slug")
    ap.add_argument("--overwrite", action="store_true", help="replace one of your own Talents")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if args.url:
        blob, imported_from = _fetch(args.url), args.url
    else:
        blob, imported_from = Path(args.path).read_bytes(), args.path
    try:
        res = install(
            archive=blob, slug_override=args.slug_override,
            overwrite=args.overwrite, imported_from=imported_from,
        )
    except TalentImportError as e:
        print(f"REJECTED (unsafe archive): {e}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(res, indent=2))
    elif res["installed"]:
        print(f"Installed {res['slug']} (imported, unverified) at {res['path']}")
    else:
        print(f"Not installed: {res['reason']}")
    return 0 if res.get("installed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
