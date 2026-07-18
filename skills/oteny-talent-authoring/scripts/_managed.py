#!/usr/bin/env python3
"""_managed — which overlay dirs Oteny manages, so the rest are the owner's.

A tenant's ``~/.hermes/skills/talents/`` holds THREE kinds of dir: the infra default
skills, the delivered product bundles + the author-on-ramp, and the **owner-authored
Talents** the tenant's own agent built. Only the last kind is the owner's to
review / health-check / publish — everything else is managed by Oteny and must
never be flagged as a promotion candidate or shadowed by an import.

This is the on-VM twin of the control-plane overlay partitioner:
owner-authored == ``existing − managed``, where ``managed = DEFAULT_SKILLS ∪
AUTHORING_DIRS ∪ (the on-VM manifest's recorded bundles)``. ``DEFAULT_SKILLS`` is a
byte-mirror of the control-plane sidecar's tuple (Oteny CI keeps the two in sync,
the same rule the shared bootstrap interpreters follow); the manifest supplies the
per-tenant product set so a purchased bundle is never mistaken for owner content.

Shared by ``self_check.py`` (the health/publish self-check) and ``import_talent.py``
(the never-shadow-a-managed-slug guard) so both agree on the one managed set.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

# Byte-mirror of the Oteny control-plane DEFAULT_SKILLS — the infra skills every
# tenant gets regardless of product bundles. Oteny CI asserts this tuple equals the
# sidecar's, so a drifted mirror fails there (the same defence the _shared bootstrap
# copies use).
DEFAULT_SKILLS = (
    "index-reconciler", "oteny-cron-authoring", "oteny-set-timezone", "oteny-drop",
    "oteny-investigate", "oteny-web-operator", "oteny-remember-login", "oteny-web-search",
    "oteny-travel", "oteny-read-document", "oteny-analyze-video", "oteny-youtube-transcript",
    "oteny-connect-credential", "oteny-file-search", "oteny-sites",
)

# The author-on-ramp dirs are managed infra, never owner-authored (D154). They may or
# may not be present on a given box (delivery packs the product set), but if one IS on
# the box it is ours, so listing them here keeps a self-check / import from ever treating
# the authoring skill or the lint rules as an owner Talent.
AUTHORING_DIRS = ("oteny-talent-authoring", "talent-authoring-standard", "_shared")


def hermes_home(override: Path | str | None = None) -> Path:
    """Resolve ``~/.hermes`` (or a test sandbox via ``HH_HERMES_HOME`` / ``HH_HOME``)."""
    if override is not None:
        return Path(override)
    env = os.environ.get("HH_HERMES_HOME") or os.environ.get("HERMES_HOME")
    if env:
        return Path(env)
    home = os.environ.get("HH_HOME")
    return (Path(home) if home else Path.home()) / ".hermes"


def _manifest_bundles(home: Path) -> set[str]:
    """The product bundles the on-VM manifest records as delivered (empty on a dev box)."""
    manifest = home / ".hermeshost-manifest.json"
    if not manifest.is_file():
        return set()
    try:
        data = json.loads(manifest.read_text())
    except (ValueError, OSError):
        return set()
    return {b for b in (data.get("bundles") or []) if b}


def managed_slugs(home: Path | str | None = None) -> set[str]:
    """Every overlay dir Oteny manages: defaults ∪ authoring ∪ recorded bundles."""
    h = hermes_home(home)
    return set(DEFAULT_SKILLS) | set(AUTHORING_DIRS) | _manifest_bundles(h)


def _is_bundle_dir(d: Path) -> bool:
    """A Talent bundle is a dir marked by a top-level SKILL.md OR agent-profile.yaml
    (a composed Talent carries no root SKILL.md) — mirrors the control-plane
    ``extract_bundle`` marker test."""
    return d.is_dir() and (
        (d / "SKILL.md").is_file() or (d / "agent-profile.yaml").is_file()
    )


def owner_talent_slugs(home: Path | str | None = None) -> list[str]:
    """The owner-authored Talents on this box: overlay bundle dirs minus the managed set.

    Sorted for a deterministic report. A dir that is neither managed nor a valid bundle
    (stray scratch) is skipped — only real owner bundles surface as promotion candidates.
    """
    h = hermes_home(home)
    talents = h / "skills" / "talents"
    if not talents.is_dir():
        return []
    managed = managed_slugs(h)
    return sorted(
        d.name for d in talents.iterdir()
        if d.name not in managed and not d.name.startswith(".") and _is_bundle_dir(d)
    )
