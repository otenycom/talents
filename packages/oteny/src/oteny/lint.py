"""Offline talent-authoring-standard lint (path-load from skills/)."""
from __future__ import annotations

import importlib.util
from pathlib import Path


def _default_skills_root() -> Path:
    # packages/oteny/src/oteny → talents/skills
    return Path(__file__).resolve().parents[4] / "skills"


def lint_talent_dir(bundle_dir: str, catalog_dir: str | None = None) -> dict:
    bp = Path(bundle_dir).expanduser().resolve()
    if not bp.is_dir():
        return {"ok": False, "error": f"not a directory: {bundle_dir}"}
    skills = Path(catalog_dir).expanduser().resolve() if catalog_dir else _default_skills_root()
    rules = skills / "talent-authoring-standard" / "scripts" / "lint_upgrade_safe.py"
    if not rules.is_file():
        # sibling checkout layout: --catalog-dir pointing at skills/
        alt = skills / "lint_upgrade_safe.py"
        if alt.is_file():
            rules = alt
        else:
            return {"ok": False, "error": f"lint rules unavailable under {skills}"}
    spec = importlib.util.spec_from_file_location("oteny_lint_upgrade_safe", rules)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    lint_bundle = getattr(mod, "lint_bundle", None)
    if lint_bundle is None:
        # script may expose main-only; try lint_tools
        tools = rules.parent / "lint_tools.py"
        if tools.is_file():
            tspec = importlib.util.spec_from_file_location("oteny_lint_tools", tools)
            tmod = importlib.util.module_from_spec(tspec)
            assert tspec.loader is not None
            tspec.loader.exec_module(tmod)
            lint_bundle = tmod.lint_bundle
    if lint_bundle is None:
        return {"ok": False, "error": f"no lint_bundle in {rules}"}
    violations = lint_bundle(bp)
    warnings = []
    cw = getattr(mod, "checklist_warnings", None)
    if cw:
        warnings = cw(bp)
    return {
        "ok": not violations, "dir": bp.name,
        "violations": violations, "warnings": warnings,
    }
