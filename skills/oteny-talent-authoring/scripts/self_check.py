#!/usr/bin/env python3
"""self_check — is an owner Talent share-ready? (health report + publish self-check).

The owner asks *"health report my Talents"* or *"publish my <X> Talent"*. This checks
each owner-authored Talent on the box against the authoring standard and grades it
**green / yellow / red**, so the owner sees promotion candidates before anything leaves
the VM:

    python3 self_check.py --all --json                     # every owner Talent, graded
    python3 self_check.py --slug plant-tracker --json       # one Talent
    python3 self_check.py --slug plant-tracker --request-publish --viewer-url <url>

Grading mirrors the promote gate: it **sanitizes** a copy (strips per-tenant state the
way an export/promote does), then runs the canonical ``talent-authoring-standard`` lint
(``lint_bundle`` + ``checklist_warnings``) **if the rules are on the box**; when they
aren't, it falls back to a **structural pre-flight** (the obvious, owner-fixable checks)
and marks the result ``provisional`` — the authoritative grade always re-runs Oteny-side
(the fleet ``owner-talent-health`` sweep + ``promote-talent``, three passes, defence in
depth). ``red`` = lint violations (not share-ready); ``yellow`` = clean but with
checklist warnings; ``green`` = clean.

``--request-publish`` on a green/yellow Talent writes a publish-request marker under
``~/.hermes/data/oteny-talent-authoring/publish-requests/<slug>.json`` (never a red one).
The sidecar sweep drains that marker into the Oteny Bot Market review queue; nothing here
touches the network or the control plane (the box holds no control-plane key). Pure +
file-based → unit-tested offline.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # sibling declared scripts
import _managed  # noqa: E402
import package_talent  # noqa: E402 — reuse its sanitize + version/profile readers

# Where the owner's publish requests queue for the sidecar sweep to drain. Under the
# data plane (never the bundle) so a re-export/promote never ships a request marker.
_REQUESTS_SUBDIR = ("data", "oteny-talent-authoring", "publish-requests")

# Publish is allowed on a clean bundle (green) or one with only soft warnings (yellow) —
# warnings never block a promote. A red (lint violations) is refused.
_PUBLISHABLE = ("green", "yellow")


def _load_lint():
    """The canonical ``(lint_bundle, checklist_warnings)`` if the standard is on the box,
    else ``None`` (a product box ships the authoring skill but not always the lint rules;
    the sidecar is the authoritative grader either way)."""
    path = (
        Path(__file__).resolve().parents[2]
        / "talent-authoring-standard" / "scripts" / "lint_upgrade_safe.py"
    )
    if not path.is_file():
        return None
    try:
        spec = importlib.util.spec_from_file_location("oteny_self_check_lint", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
    except Exception:  # noqa: BLE001 — a broken/absent rules file → pre-flight fallback
        return None
    lint = getattr(mod, "lint_bundle", None)
    warns = getattr(mod, "checklist_warnings", lambda _b: [])
    return (lint, warns) if lint else None


def _publishability_floor(bundle: Path) -> list[str]:
    """The one hard 'can this even become a Bot Market Talent?' check — runs ALWAYS,
    lint present or not, because the upgrade-safety lint does NOT cover it: a bundle with
    no ``agent-profile.yaml`` is a bare skill, and the store seed only ever creates an
    ``hh.talent`` row from a profile (``bot:``) — so a profile-less bundle can never list,
    route, or self-check. Promoting it is a dead end, so it grades red."""
    if not (bundle / "agent-profile.yaml").is_file():
        return ["no agent-profile.yaml — a bare skill can't be published as a Talent "
                "(add a profile so it can route + list in the Bot Market)"]
    return []


def _preflight(bundle: Path) -> list[str]:
    """Structural checks an owner can act on WITHOUT the full lint (the fallback grade).

    A deliberately small subset of the standard for when the canonical rules aren't on the
    box: a top-level ``SKILL.md`` must carry YAML frontmatter with a sharp ``description``
    (≤ ~60 chars routes), and the Talent must declare a ``version``. These both fail a
    promote AND are obvious to fix; the deep upgrade-safety checks run only when the real
    lint is present. The 'is it a Talent' floor is separate (``_publishability_floor``).
    """
    out: list[str] = []
    skill_md = bundle / "SKILL.md"
    fm = package_talent._frontmatter(skill_md.read_text()) if skill_md.is_file() else {}
    if skill_md.is_file():
        if not fm:
            out.append("SKILL.md has no YAML frontmatter (needs `name:` + `description:`)")
        desc = fm.get("description") or ""
        if desc and len(desc) > 60:
            out.append(f"SKILL.md description is {len(desc)} chars — trim to ≤60 so it "
                       "routes as a sharp trigger")
    if not fm.get("version") and not package_talent._profile_fields(bundle).get("version"):
        out.append("no `version:` in agent-profile.yaml / SKILL.md — stamp a semver")
    return out


def _classify(violations: list[str], warnings: list[str]) -> tuple[str, list[str]]:
    """red (violations) / yellow (warnings only) / green (clean) + the reason list."""
    if violations:
        return "red", list(violations)
    if warnings:
        return "yellow", list(warnings)
    return "green", []


def check_one(slug: str, *, home: Path | str | None = None, lint=None) -> dict:
    """Sanitize a copy of the owner Talent ``slug`` and grade it green/yellow/red.

    ``lint`` is the ``(lint_bundle, checklist_warnings)`` pair (``_load_lint()``); when
    ``None`` the structural pre-flight stands in and ``provisional`` is set (the real
    grade runs Oteny-side). Returns a per-Talent DTO — never raises for a normal bundle.
    """
    h = _managed.hermes_home(home)
    bundle = h / "skills" / "talents" / slug
    if not bundle.is_dir():
        return {"slug": slug, "status": "red", "provisional": False,
                "reasons": [f"no Talent {slug!r} on this box"], "error": "not_found"}

    with tempfile.TemporaryDirectory() as td:
        staged = Path(td) / slug
        package_talent._copy_clean(bundle, staged)
        sanitized = package_talent._sanitize(staged)  # strip per-tenant state like a promote

        violations = _publishability_floor(staged)  # always — the lint doesn't cover it
        if lint is not None:
            lint_bundle, checklist_warnings = lint
            violations += list(lint_bundle(staged))
            warnings = list(checklist_warnings(staged))
            provisional = False
        else:
            violations += _preflight(staged)
            warnings = []
            provisional = True

        # A baked chat/owner id was stripped for sharing — clean to promote, but the owner
        # should know their routing won't carry over (routing is by topic, not a baked id).
        if sanitized["stripped_id_lines"]:
            warnings = warnings + [
                f"{sanitized['stripped_id_lines']} baked chat/owner id line(s) were "
                "stripped for sharing — the shared version routes by topic, not a baked id"]

        status, reasons = _classify(violations, warnings)
        prof = package_talent._profile_fields(staged)
        top = staged / "SKILL.md"
        fm = package_talent._frontmatter(top.read_text()) if top.is_file() else {}
        return {
            "slug": slug,
            "display_name": prof.get("display_name") or fm.get("name") or slug,
            "status": status,
            "provisional": provisional,
            "reasons": reasons,
            "violations": violations,
            "warnings": warnings,
            "talent_version": fm.get("version") or prof.get("version"),
            "standard_version": package_talent._resolve_standard_version(None),
            "sanitized": {
                "removed_files": sanitized["removed_files"],
                "stripped_id_lines": sanitized["stripped_id_lines"],
            },
        }


def check_all(*, home: Path | str | None = None, lint=None) -> list[dict]:
    """Grade every owner-authored Talent on the box (the health report)."""
    if lint is None:
        lint = _load_lint()
    return [check_one(slug, home=home, lint=lint)
            for slug in _managed.owner_talent_slugs(home)]


def _requests_dir(home: Path) -> Path:
    return home.joinpath(*_REQUESTS_SUBDIR)


def request_publish(slug: str, *, home: Path | str | None = None,
                    viewer_url: str | None = None, lint=None) -> dict:
    """Self-check ``slug`` and, only on a green/yellow result, write a publish-request
    marker for the sidecar sweep to drain into the Bot Market review queue. A red Talent
    is refused (the marker is never written) with the violations to fix."""
    h = _managed.hermes_home(home)
    report = check_one(slug, home=h, lint=lint if lint is not None else _load_lint())
    if report["status"] not in _PUBLISHABLE:
        return {"requested": False, "slug": slug, "report": report,
                "reason": "self-check failed — fix the violations and retry"}
    reqs = _requests_dir(h)
    reqs.mkdir(parents=True, exist_ok=True)
    marker = {
        "slug": slug,
        "display_name": report["display_name"],
        "status": report["status"],
        "provisional": report["provisional"],
        "talent_version": report["talent_version"],
        "standard_version": report["standard_version"],
        "viewer_url": viewer_url or "",
        "requested_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    path = reqs / f"{slug}.json"
    path.write_text(json.dumps(marker, indent=2, sort_keys=True) + "\n")
    return {"requested": True, "slug": slug, "marker_path": str(path),
            "status": report["status"], "report": report}


def _print_report(reports: list[dict]) -> None:
    if not reports:
        print("No owner-authored Talents found on this box.")
        return
    glyph = {"green": "✅", "yellow": "⚠️ ", "red": "❌"}
    for r in reports:
        prov = " (provisional — full check runs Oteny-side)" if r.get("provisional") else ""
        print(f"{glyph.get(r['status'], '?')} {r['slug']} — {r['status']}{prov}")
        for reason in r.get("reasons", []):
            print(f"     - {reason}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Health-check / publish-self-check an owner Talent.")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--all", action="store_true", help="grade every owner Talent on the box")
    g.add_argument("--slug", help="grade a single Talent dir under ~/.hermes/skills/talents/")
    ap.add_argument("--request-publish", action="store_true",
                    help="on a green/yellow --slug, queue it for Oteny Bot Market review")
    ap.add_argument("--viewer-url", help="the Oteny Talent Drop viewer link (for the reviewer)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    if args.request_publish:
        if not args.slug:
            ap.error("--request-publish needs --slug")
        res = request_publish(args.slug, viewer_url=args.viewer_url)
        if args.json:
            print(json.dumps(res, indent=2))
        elif res["requested"]:
            print(f"Submitted {args.slug} ({res['status']}) for Oteny Bot Market review.")
        else:
            print(f"Not submitted: {res['reason']}")
            _print_report([res["report"]])
        return 0 if res["requested"] else 1

    # Load the canonical lint ONCE and pass it to both paths — so a single --slug check on a
    # box that HAS the rules gets the full grade, not the shallow provisional pre-flight.
    lint = _load_lint()
    reports = (check_all(lint=lint) if args.all
               else [check_one(args.slug, lint=lint)])
    if args.json:
        print(json.dumps(reports, indent=2))
    else:
        _print_report(reports)
    # Exit non-zero if any Talent is red (so a scripted --slug check gates cleanly).
    return 1 if any(r["status"] == "red" for r in reports) else 0


if __name__ == "__main__":
    raise SystemExit(main())
