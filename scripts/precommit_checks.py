#!/usr/bin/env python3
"""Run the same gates CI runs, locally, before a commit lands.

The canonical CI for this repo is two GitHub workflows — ``bundle-tests.yml`` (the
marketable-Talent unit tests + the offline behavioral scenarios) and ``talent-lint.yml``
(the publishable upgrade-safety + tool-claim lints). A direct push to ``main`` skips them
until after the fact; this script is the local mirror so a red change never leaves the
machine. It is wired as a ``pre-commit`` hook (``.pre-commit-config.yaml``) and is safe to
run by hand: ``python scripts/precommit_checks.py``.

Parity is the whole point — each step below runs the *same* command its workflow runs, so
the hook and CI can't drift. Exit non-zero on the first failing step (blocks the commit).
"""
from __future__ import annotations

import glob
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _run(label: str, argv: list[str], env: dict | None = None) -> bool:
    print(f"\n\033[1m▶ {label}\033[0m\n  $ {' '.join(argv)}")
    proc = subprocess.run(argv, cwd=REPO, env={**os.environ, **(env or {})})
    ok = proc.returncode == 0
    print(f"  {'✓ pass' if ok else '✗ FAIL'} ({label})")
    return ok


def main() -> int:
    steps: list[tuple[str, list[str], dict | None]] = []

    # bundle-tests.yml step 1 — the marketable-Talent unit tests (incl. PII-clean + teasers).
    steps.append(("Bundle unit tests (pytest)",
                  [sys.executable, "-m", "pytest", "tests/", "-q"],
                  {"PYTHONPATH": "tests"}))

    # bundle-tests.yml step 2 — behavioral scenarios on the offline mock backend (if any).
    scenarios = sorted(glob.glob("skills/*/tests/scenarios/*.yaml", root_dir=REPO))
    if scenarios:
        steps.append((f"Behavioral scenarios ({len(scenarios)}, mock backend)",
                      [sys.executable, "skills/_shared/scripts/run_scenario.py",
                       "--backend", "mock", *scenarios], None))

    # talent-lint.yml — the publishable upgrade-safety + tool-claim lints over each bundle.
    # A bundle is any direct child of skills/ that ships an agent-profile.yaml (the bundle
    # marker) — infra skills without one (talent-authoring-standard, _shared, …) are skipped.
    bundles = sorted(os.path.dirname(p)
                     for p in glob.glob("skills/*/agent-profile.yaml", root_dir=REPO))
    if bundles:
        steps.append(("Talent upgrade-safety lint",
                      [sys.executable,
                       "skills/talent-authoring-standard/scripts/lint_upgrade_safe.py",
                       *bundles], None))
        steps.append(("Talent tool-claim lint",
                      [sys.executable,
                       "skills/talent-authoring-standard/scripts/lint_tools.py",
                       *bundles], None))

    failed = [label for label, argv, env in steps if not _run(label, argv, env)]
    print()
    if failed:
        print(f"\033[31m✗ {len(failed)} check(s) failed: {', '.join(failed)}\033[0m")
        print("  Commit blocked. Fix the above, or `git commit --no-verify` to bypass "
              "(CI will still gate the push).")
        return 1
    print(f"\033[32m✓ all {len(steps)} checks passed\033[0m")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
