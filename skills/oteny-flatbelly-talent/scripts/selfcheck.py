#!/usr/bin/env python3
"""selfcheck — the deterministic first-run judge for an Oteny Talent.

ONE reusable bootstrap interpreter, keyed on each bot's
``required_artifacts.yaml`` manifest (the first-run contract; "one reusable
bootstrap workflow"). The manifest *is* the setup goal; this script walks it and
answers the single question the mechanical first-run section opens with:

    "is setup already complete?"

It is pure, file-based, and side-effect-free (read-only) so it is cheap to run on
every later load and fully unit-testable offline. Every artifact check resolves
to a file/dir/row that either exists or does not — no LLM judgement, no network.

Usage (the bundle ships an identical copy at ``<bot>/scripts/selfcheck.py``):

    python3 selfcheck.py                 # READY  | NOT-READY: missing=[...]
    python3 selfcheck.py --json          # {"ready": bool, "missing": [...], ...}
    python3 selfcheck.py --manifest PATH # override manifest location

By default the manifest is found at ``<script_dir>/../required_artifacts.yaml``.

Home roots are resolved through env overrides so tests (and a relocated overlay)
can point it at a sandbox:
    HH_HOME         -> stand-in for $HOME          (default: Path.home())
    HH_HERMES_HOME  -> stand-in for ~/.hermes      (default: $HOME/.hermes)

Exit code is always 0 when the check ran (so the LLM's terminal call never looks
like a failure); readiness is signalled in the output, not the exit code.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - PyYAML is always present on Hermes
    yaml = None


# --------------------------------------------------------------------------- #
# path resolution (env-overridable so tests are hermetic)                      #
# --------------------------------------------------------------------------- #
def _home() -> Path:
    return Path(os.environ.get("HH_HOME") or Path.home())


def _hermes_home() -> Path:
    # HH_HERMES_HOME is the test override; HERMES_HOME is Hermes's own (profile-aware,
    # bridged into tool subprocesses) — honor it so per-bot data under the hermes home
    # follows a profile relocation. Falls back to $HOME/.hermes.
    env = os.environ.get("HH_HERMES_HOME") or os.environ.get("HERMES_HOME")
    return Path(env) if env else _home() / ".hermes"


def expand(p: str) -> Path:
    """Expand a manifest path. ``~/.hermes/...`` -> hermes home; ``~/...`` -> home."""
    if p.startswith("~/.hermes/"):
        return _hermes_home() / p[len("~/.hermes/"):]
    if p == "~/.hermes":
        return _hermes_home()
    if p.startswith("~/"):
        return _home() / p[2:]
    return Path(p).expanduser()


def _load_yaml(path: Path):
    if yaml is None:
        raise RuntimeError("PyYAML is required to read manifests/config")
    if not path.exists():
        return None
    with path.open() as fh:
        return yaml.safe_load(fh)


def _is_empty(v) -> bool:
    """A required field is 'empty' if unset or a template sentinel (0 / '' / [])."""
    if v is None:
        return True
    if isinstance(v, str) and not v.strip():
        return True
    if isinstance(v, (list, dict)) and len(v) == 0:
        return True
    if isinstance(v, (int, float)) and v == 0:
        return True
    return False


# --------------------------------------------------------------------------- #
# per-kind checkers — each returns a result dict                               #
# --------------------------------------------------------------------------- #
def _r(kind, ok, reason="", remediation="", blocking=True, **extra):
    d = {"kind": kind, "ok": bool(ok), "reason": reason,
         "remediation": remediation, "blocking": blocking}
    d.update(extra)
    return d


def check_sqlite_db(a):
    path = expand(a["path"])
    want = list(a.get("must_have_tables", []))
    if not path.exists():
        return _r("sqlite_db", False, f"db missing at {path}",
                  "first-run §data: CREATE TABLE IF NOT EXISTS … (inline schema)")
    con = sqlite3.connect(str(path))
    try:
        have = {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        con.close()
    missing = [t for t in want if t not in have]
    if missing:
        return _r("sqlite_db", False, f"tables missing: {missing}",
                  "first-run §data: CREATE TABLE IF NOT EXISTS for the missing tables")
    return _r("sqlite_db", True, f"{path.name} has {len(want)} required tables")


def check_profile(a):
    path = expand(a["path"])
    req = list(a.get("required_fields", []))
    data = _load_yaml(path)
    if data is None:
        return _r("profile", False, f"profile missing at {path}",
                  "first-run §profile: run the intake → write profile.yaml")
    empty = [f for f in req if _is_empty(data.get(f))]
    if empty:
        return _r("profile", False, f"fields unset: {empty}",
                  "first-run §profile: ask the intake questions for the unset fields")
    return _r("profile", True, "all required profile fields set")


def check_memory(a):
    # Generic file-presence check reused for BOTH the shared identity USER.md and a
    # per-bot domain memory.md (the domain-memory split). The manifest supplies label /
    # blocking / remediation, so one checker serves both kinds of memory file.
    path = expand(a["path"])
    label = a.get("label", path.name)
    blocking = a.get("blocking", True)
    remediation = a.get(
        "remediation", "first-run §profile: render this memory file from profile.yaml")
    if path.exists() and path.stat().st_size > 0:
        return _r("memory", True, f"{label} present ({path.name})", blocking=blocking)
    return _r("memory", False, f"{label} missing/empty at {path}", remediation,
              blocking=blocking)


def check_localized_bundle(a):
    profile = _load_yaml(expand(a["profile_path"]))
    field = a.get("matches_profile_field", "language")
    if profile is None or _is_empty(profile.get(field)):
        return _r("localized_bundle", False, "profile.language unknown yet",
                  "first-run §profile must run before localization can be judged")
    want = str(profile[field]).strip()
    marker = expand(a["language_marker"])
    have = marker.read_text().strip() if marker.exists() else a.get("base_language", "")
    if have == want:
        return _r("localized_bundle", True, f"bundle speaks '{want}'")
    return _r("localized_bundle", False,
              f"bundle language '{have}' != profile.language '{want}'",
              "first-run §localized_bundle: invoke skill-translator into profile.language")


def check_routing(a):
    # DM routing is NATIVE: only a one-line `name: description` index sits in the
    # cached prompt and the model self-selects the matching Talent via `skill_view`, so a
    # DM-first bot needs NO SOUL signature and NO channel_prompt — it auto-satisfies.
    # Group routing is handled by the hh-group-focus-hint plugin (injects the live group
    # title) + the native index. Only a bot that declares a REQUIRED group binding
    # (`requires_channel_prompt: true`, or an explicit `channel_chat_id`) asserts that
    # its channel_prompt is registered.
    require = a.get("requires_channel_prompt") or a.get("channel_chat_id")
    if not require:
        return _r("routing", True,
                  "DM routing via the native skill index (no binding required)")
    cfg = _load_yaml(expand(a["config_path"]))
    sig = a.get("signature", "")
    platform = a.get("platform", "telegram")
    prompts = (((cfg or {}).get(platform) or {}).get("channel_prompts") or {})
    if any(sig in str(v) for v in prompts.values()):
        return _r("routing", True, f"channel_prompt registered (sig '{sig}')")
    return _r("routing", False,
              f"required group channel_prompt carrying signature '{sig}' not registered",
              "first-run §routing: bind the group (channel_chat_id / owner override) "
              "then invoke index-reconciler --apply")


def check_cron(a):
    jobs_path = expand(a["jobs_path"])
    required = list(a.get("jobs", []))
    if not required:
        # nothing required for this bot (e.g. stock watcher is tool-gated off)
        gated = a.get("gated_jobs", [])
        note = f"{len(gated)} job(s) tool-gated off" if gated else "no crons required"
        return _r("cron", True, note, blocking=False)
    data = _load_yaml(jobs_path) if jobs_path.suffix in (".yaml", ".yml") else (
        json.loads(jobs_path.read_text()) if jobs_path.exists() else None)
    names = {j.get("name") for j in (data or {}).get("jobs", [])}
    missing = [n for n in required if n not in names]
    if missing:
        return _r("cron", False, f"crons not registered: {missing}",
                  "first-run §cron: register the jobs list-first (create if absent)")
    return _r("cron", True, f"{len(required)} cron job(s) registered")


def check_tools(a):
    present_if_file = a.get("present_if_file", {}) or {}
    stubbed = list(a.get("stubbed", []))
    missing = [name for name, fp in present_if_file.items() if not expand(fp).exists()]
    detail = {"available": [n for n in present_if_file if n not in missing],
              "stubbed": stubbed, "missing": missing}
    if missing:
        return _r("tools", False, f"required tool files missing: {missing}",
                  "deliver the bot bundle (overlay/bake) before first-run",
                  **detail)
    note = "required tools present"
    if stubbed:
        note += f"; stubbed (degraded): {stubbed}"
    return _r("tools", True, note, blocking=False, **detail)


CHECKERS = {
    "sqlite_db": check_sqlite_db,
    "profile": check_profile,
    "memory": check_memory,
    "localized_bundle": check_localized_bundle,
    "routing": check_routing,
    "cron": check_cron,
    "tools": check_tools,
}


def run(manifest_path: Path) -> dict:
    manifest = _load_yaml(manifest_path)
    if manifest is None:
        raise SystemExit(f"manifest not found: {manifest_path}")
    base_lang = manifest.get("base_language")
    results = []
    for a in manifest.get("artifacts", []):
        kind = a.get("kind")
        checker = CHECKERS.get(kind)
        if checker is None:
            results.append(_r(kind or "?", False, f"unknown artifact kind '{kind}'",
                              blocking=False))
            continue
        if kind == "localized_bundle":
            a = {**a, "base_language": a.get("base_language", base_lang)}
        results.append(checker(a))
    missing = [r for r in results if not r["ok"] and r["blocking"]]
    return {
        "bot": manifest.get("bot"),
        "ready": len(missing) == 0,
        "missing": missing,
        "artifacts": results,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Oteny Talent first-run selfcheck")
    default_manifest = Path(__file__).resolve().parent.parent / "required_artifacts.yaml"
    ap.add_argument("--manifest", default=str(default_manifest))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    report = run(Path(args.manifest))
    if args.json:
        print(json.dumps(report, indent=2))
        return 0
    if report["ready"]:
        print("READY")
    else:
        missing = [f"{m['kind']}({m['reason']})" for m in report["missing"]]
        print("NOT-READY: missing=" + json.dumps(missing))
        for m in report["missing"]:
            print(f"  - {m['kind']}: {m['reason']}  ->  {m['remediation']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
