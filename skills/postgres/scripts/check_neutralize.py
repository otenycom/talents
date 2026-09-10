#!/usr/bin/env python3
"""check_neutralize — the fail-closed boot gate for a cloned Oteny Talent.

This is the neutralize analog of the selfcheck boot gate, but with the OPPOSITE
exit-code contract: it is run by the CONTROL PLANE right before a clone's gateway is
allowed to start, and it must **refuse to serve** (non-zero exit) unless every declared
neutralize step is recorded applied in the data-plane marker. A silent neutralize miss
at scale would fire thousands of real emails / government filings, so the gate is
fail-closed: marker missing, manifest unreadable, or any step still pending ⇒ NOT-READY.

It reads the same ``neutralize.yaml`` + ``~/.hermes/data/<bot>/neutralize.json`` marker
as ``neutralize.py`` (which it imports by path, exactly like ``preflight.py`` imports
``migrate.py``), so there is one source of truth for "is this clone de-fanged?".

Usage (the bundle ships an identical copy at ``<bot>/scripts/check_neutralize.py``):

    python3 check_neutralize.py                 # READY (exit 0) | NOT-READY: ... (exit 3)
    python3 check_neutralize.py --json          # {"ready": bool, "pending": [...]}
    python3 check_neutralize.py --manifest PATH # override neutralize.yaml location

A Talent with NO neutralize.yaml (no outbound action to disarm) is trivially READY — the
gate only bites a Talent that *declares* steps. The companion lint
(``lint_upgrade_safe``) is what forces an outbound-action Talent to ship a neutralize.yaml
in the first place, so "no manifest" can never silently mean "nothing to neutralize" for a
Talent that actually has live actions.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

EXIT_NOT_READY = 3  # fail-closed: a non-zero the converge/clone path can `&&`-gate on


def _load_neutralize():
    """Import the sibling neutralize.py (bundle copy wins) by path — one source of truth."""
    here = Path(__file__).resolve().parent
    cand = here / "neutralize.py"
    spec = importlib.util.spec_from_file_location("neutralize_gate_impl", cand)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _default_manifest() -> Path:
    return Path(__file__).resolve().parent.parent / "neutralize.yaml"


def run(manifest_path: Path) -> dict:
    neu = _load_neutralize()
    manifest = neu.load_manifest(manifest_path)
    bot = manifest.get("bot") or ""
    declared = neu.declared(manifest)
    pend = neu.pending_for(manifest_path)
    has_manifest = manifest_path.exists()
    return {
        "bot": bot,
        "ready": len(pend) == 0,
        "has_manifest": has_manifest,
        "declared": [s["id"] for s in declared],
        "pending": [{"id": s["id"], "kind": s.get("kind", "checklist"),
                     "ref": s.get("ref")} for s in pend],
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Oteny Talent fail-closed neutralize boot gate")
    ap.add_argument("--manifest", default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    manifest_path = Path(args.manifest) if args.manifest else _default_manifest()
    try:
        report = run(manifest_path)
    except Exception as e:  # any error reading the manifest/marker is fail-closed
        report = {"bot": "", "ready": False, "has_manifest": manifest_path.exists(),
                  "declared": [], "pending": [], "error": f"{type(e).__name__}: {e}"}

    if args.json:
        print(json.dumps(report, indent=2))
    elif report["ready"]:
        print("READY")
    else:
        pend = [f"{p['id']}({p['kind']})" for p in report["pending"]]
        print("NOT-READY: neutralize incomplete pending=" + json.dumps(pend)
              + (f" error={report['error']}" if report.get("error") else ""))
    return 0 if report["ready"] else EXIT_NOT_READY


if __name__ == "__main__":
    sys.exit(main())
