#!/usr/bin/env python3
"""package_talent — sanitize + zip + manifest an owner Talent for export (Phase 1).

The owner asks me to review/export a Talent they built. This packages the bundle at
``~/.hermes/skills/talents/<slug>/`` into a shareable drop:

    python3 package_talent.py --slug plant-tracker            # -> exports/<slug>/{bundle.zip,manifest.json,...}
    python3 package_talent.py --slug plant-tracker --json     # machine-readable summary

It does three deterministic things and NOTHING that touches the network:

1. **Sanitize** a copy of the bundle — delete per-tenant state files (``*.db``,
   ``profile.yaml``, ``memory.md``, …, D34) and strip any line that bakes a Telegram
   chat/user id (a public drop is effectively permanent, so secrets/PII must never
   leave the VM). This is the safety floor, independent of the deferred format lint.
2. **Manifest** — stamp the Talent's own version, the **authoring-standard version**
   it targeted (the bridge to a future version-aware lint), the source, and a hash
   inventory of every shipped file. It carries NO stripped secret content.
3. **Zip** the sanitized tree deterministically (same tree → same bytes → a stable
   drop), with the manifest inside.

The agent then ``publish_file``s the zip, renders the viewer (``render_viewer.py``,
fed the published zip URL), and publishes that. Pure + file-based → unit-tested
offline; reused by no other process.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import zipfile
from pathlib import Path

# Keep in sync with talent-authoring-standard/SKILL.md `version:` — the last-known
# default when the standard bundle isn't on the box to read.
_DEFAULT_STANDARD_VERSION = "0.3.0"

# Per-tenant state / data-plane artifacts (D34) — never enter a shared export. Mirrors
# promote.py's `_STATE_GLOBS` so an owner export sanitizes exactly like a promote.
_STATE_GLOBS = (
    "*.db", "*.db-wal", "*.db-shm", "*.sqlite", "*.sqlite3",
    "profile.yaml", ".bundle_lang", "memory.md", "USER.md", "sessions.json",
)
_TEXT_SUFFIXES = {".md", ".yaml", ".yml", ".py", ".txt", ".json", ".toml", ".sh", ".cfg"}
_ID_ASSIGN_LINE = re.compile(
    r"(?i)\b(channel_chat_id|chat_id|user_id|owner_telegram\w*|allowed_users|"
    r"allowed_chats|home_channel|telegram_bot_token|telegram_allowed\w*|telegram_group\w*)"
    r'\b\s*[:=]\s*["\']?[+-]?\d{6,}'
)
_SKIP_DIRS = {"__pycache__", ".git"}
_SKIP_SUFFIXES = {".pyc", ".pyo"}

# Deterministic zip: a fixed DOS epoch so the bytes depend only on the content.
_ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)


class PackageError(RuntimeError):
    """A bundle can't be located / packaged (a clean, owner-facing failure)."""


def _hermes_home(override: Path | None = None) -> Path:
    if override is not None:
        return Path(override)
    env = os.environ.get("HH_HERMES_HOME") or os.environ.get("HERMES_HOME")
    if env:
        return Path(env)
    home = os.environ.get("HH_HOME")
    return (Path(home) if home else Path.home()) / ".hermes"


def _resolve_standard_version(explicit: str | None) -> str:
    if explicit:
        return explicit
    env = os.environ.get("HH_AUTHORING_STANDARD_VERSION")
    if env:
        return env
    sibling = Path(__file__).resolve().parents[2] / "talent-authoring-standard" / "SKILL.md"
    if sibling.is_file():
        m = re.search(r"(?m)^version:\s*([0-9][\w.\-]*)\s*$", sibling.read_text())
        if m:
            return m.group(1)
    return _DEFAULT_STANDARD_VERSION


def _scalar(v: str) -> str:
    """A flat YAML scalar value with a trailing inline ``# comment`` removed.

    A quoted scalar returns its inner text and drops anything after the close quote (so
    ``"1.2.3" # bump`` → ``1.2.3`` and ``"a # b"`` → ``a # b`` — the ``#`` inside quotes is
    literal). An unquoted scalar drops a `` #…`` comment only when whitespace precedes the
    ``#`` (so ``http://x#frag`` survives, ``1.0.0  # x`` → ``1.0.0``)."""
    v = v.strip()
    m = re.match(r"""^(['"])(.*?)\1\s*(?:#.*)?$""", v)
    if m:
        return m.group(2)
    return re.sub(r"\s+#.*$", "", v).strip().strip("\"'")


def _frontmatter(text: str) -> dict[str, str]:
    """A flat scalar-only read of a leading ``---`` YAML block (no deps needed)."""
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    out: dict[str, str] = {}
    for line in text[3:end].splitlines():
        m = re.match(r"\s*([A-Za-z0-9_]+):\s*(.*)$", line)
        if m and m.group(2):
            out[m.group(1)] = _scalar(m.group(2))
    return out


def _profile_fields(bundle: Path) -> dict[str, str]:
    p = bundle / "agent-profile.yaml"
    if not p.is_file():
        return {}
    out: dict[str, str] = {}
    for line in p.read_text().splitlines():
        m = re.match(r"^([A-Za-z0-9_]+):\s*(.+)$", line)  # top-level scalars only
        if m and m.group(2).strip():
            out[m.group(1)] = _scalar(m.group(2))
    return out


def _sanitize(root: Path) -> dict:
    """Strip per-tenant state IN PLACE; return removed filenames + a stripped-line count.

    Only counts (never the stripped *content*) cross into the manifest — the manifest
    ships in the public drop, so it must not echo the very ids we removed.
    """
    removed: list[str] = []
    for pat in _STATE_GLOBS:
        for p in root.rglob(pat):
            if p.is_file() and not (set(p.parts) & _SKIP_DIRS):
                removed.append(str(p.relative_to(root)))
                p.unlink()
    stripped = 0
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.suffix not in _TEXT_SUFFIXES or (set(p.parts) & _SKIP_DIRS):
            continue
        try:
            lines = p.read_text().splitlines(keepends=True)
        except UnicodeDecodeError:
            continue
        kept = [ln for ln in lines if not _ID_ASSIGN_LINE.search(ln)]
        if len(kept) != len(lines):
            stripped += len(lines) - len(kept)
            p.write_text("".join(kept))
    return {"removed_files": sorted(removed), "stripped_id_lines": stripped}


def _copy_clean(src: Path, dst: Path) -> None:
    """Copy the bundle tree, dropping caches/VCS scratch (the data plane isn't here)."""
    def ignore(_dir, names):
        return [
            n for n in names
            if n in _SKIP_DIRS or Path(n).suffix in _SKIP_SUFFIXES
        ]
    shutil.copytree(src, dst, ignore=ignore)


def _inventory(root: Path) -> list[dict]:
    files = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        raw = p.read_bytes()
        try:
            raw.decode("utf-8")
            binary = False
        except UnicodeDecodeError:
            binary = True
        files.append({
            "path": str(p.relative_to(root)).replace(os.sep, "/"),
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "binary": binary,
        })
    return files


def _write_zip(staged: Path, slug: str, zip_path: Path) -> None:
    members = sorted(p for p in staged.rglob("*") if p.is_file())
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in members:
            arc = f"{slug}/{p.relative_to(staged).as_posix()}"
            info = zipfile.ZipInfo(arc, date_time=_ZIP_EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, p.read_bytes())


def package(
    *, slug: str, hermes_home: Path | None = None, out_dir: Path | None = None,
    source: str = "owner", standard_version: str | None = None,
) -> dict:
    """Sanitize → manifest → zip the Talent ``slug``; write the export under ``out_dir``."""
    home = _hermes_home(hermes_home)
    bundle = home / "skills" / "talents" / slug
    if not bundle.is_dir():
        raise PackageError(f"no Talent {slug!r} at {bundle}")

    out_dir = Path(out_dir) if out_dir else (home / "data" / "oteny-talent-authoring" / "exports" / slug)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    staged = out_dir / slug
    _copy_clean(bundle, staged)
    sanitized = _sanitize(staged)

    prof = _profile_fields(staged)
    top_skill = staged / "SKILL.md"
    fm = _frontmatter(top_skill.read_text()) if top_skill.is_file() else {}
    manifest = {
        "slug": slug,
        "display_name": prof.get("display_name") or fm.get("name") or slug,
        "tagline": prof.get("tagline") or fm.get("description") or "",
        "talent_version": fm.get("version") or prof.get("version"),
        "talent_authoring_standard_version": _resolve_standard_version(standard_version),
        "source": source,
        "verified": source != "imported",
        "exported_with": "oteny-talent-authoring/package_talent.py",
        "files": _inventory(staged),
        "sanitized": {
            "removed_files": sanitized["removed_files"],
            "stripped_id_lines": sanitized["stripped_id_lines"],
        },
    }
    payload = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    (staged / "manifest.json").write_text(payload)
    (out_dir / "manifest.json").write_text(payload)
    _write_zip(staged, slug, out_dir / "bundle.zip")

    return {
        "slug": slug,
        "out_dir": str(out_dir),
        "zip_path": str(out_dir / "bundle.zip"),
        "manifest_path": str(out_dir / "manifest.json"),
        "staged_dir": str(staged),
        "sanitized": sanitized,
        "file_count": len(manifest["files"]),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Package an owner Talent for export.")
    ap.add_argument("--slug", required=True, help="the Talent dir under ~/.hermes/skills/talents/")
    ap.add_argument("--out", help="output dir (default: ~/.hermes/data/oteny-talent-authoring/exports/<slug>/)")
    ap.add_argument("--source", default="owner", choices=("owner", "imported"))
    ap.add_argument("--standard-version", help="override the stamped authoring-standard version")
    ap.add_argument("--json", action="store_true", help="print the summary as JSON")
    args = ap.parse_args(argv)
    try:
        res = package(
            slug=args.slug, out_dir=Path(args.out) if args.out else None,
            source=args.source, standard_version=args.standard_version,
        )
    except PackageError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(res, indent=2))
    else:
        san = res["sanitized"]
        print(
            f"Packaged {res['slug']}: {res['file_count']} files -> {res['zip_path']}\n"
            f"  sanitized: removed {len(san['removed_files'])} state file(s), "
            f"stripped {san['stripped_id_lines']} baked-id line(s)\n"
            f"  next: publish_file('{res['zip_path']}'), then render_viewer.py --zip-url <that url>"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
