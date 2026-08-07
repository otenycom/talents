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
except ImportError:  # a COLD tenant's system python3 may lack PyYAML — _load_yaml
    yaml = None      # then falls back to the stdlib reader below (never a hard fail)


# UNREADABLE: a file that EXISTS but cannot be parsed (a read error, or a construct even
# the stdlib fallback can't handle). It is an ENVIRONMENT fault, NOT user state — the
# readiness verdict for it is UNKNOWN (never NOT-READY → never "onboard"). `read_yaml`
# returns this so a caller can tell "present but broken" from "absent" (genuine first-run).
class _Unreadable:
    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return "UNREADABLE"


UNREADABLE = _Unreadable()

# The greppable marker the belt emits (once) to STDERR when the pure-stdlib YAML fallback
# engages — i.e. this box's system python3 lacks PyYAML. Harvested by the instance-logs
# pipeline: a box repeatedly on the belt is a misbake signal (the floor didn't reach it).
# STDERR, not stdout, so it never pollutes a readiness script's parseable block.
_BELT_MARKER = "BELT:stdlib-yaml"
_belt_emitted = False


def _emit_belt_marker() -> None:
    global _belt_emitted
    if not _belt_emitted:
        _belt_emitted = True
        print(f"{_BELT_MARKER} (PyYAML absent — pure-stdlib YAML fallback engaged)",
              file=sys.stderr)


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
    if not path.exists():
        return None
    return _yaml_load_text(path.read_text())


def _yaml_load_text(text: str):
    """Parse the YAML our manifests + profile.yaml use. PyYAML when present; a
    pure-stdlib fallback otherwise, so a COLD tenant whose system python3 lacks
    PyYAML still gets a correct readiness verdict instead of the pip-install grind
    (the RuntimeError this replaces violated the "always exit 0" contract above and
    was measured looping 13 tenants / 64 sessions on prod)."""
    if yaml is not None:
        try:
            return yaml.safe_load(text)
        except Exception:
            # Belt-on-belt for the PyYAML path too: a present-but-malformed manifest/config must
            # degrade to None (→ handled as "missing/unparseable" downstream), never a raw
            # traceback that breaks the always-exit-0 contract.
            return None
    _emit_belt_marker()
    try:
        return _minimal_yaml_load(text)
    except Exception:
        # Belt on the belt: an unexpected construct must never re-introduce a hard
        # fail. None reads as "missing/unparseable" downstream → a clean NOT-READY
        # with a reason, never a traceback that invites a guess-and-loop.
        return None


def read_yaml(path: Path):
    """THREE-VALUED file read — the shared readiness belt every sibling script uses:

      * ``None``       — the file is absent OR empty (genuine "nothing here yet" → first-run);
      * ``UNREADABLE`` — the file EXISTS but cannot be parsed (a read error, or a construct
        even the stdlib fallback rejects) → an ENVIRONMENT fault, verdict UNKNOWN;
      * else           — the parsed object.

    This is what turns "can't read it" from "not there yet": PyYAML-absent is NOT unreadable
    (the stdlib fallback handles it, emitting the belt marker); only a genuine parse failure is.
    A caller must NEVER onboard/coach on ``UNREADABLE`` — it is not user state."""
    p = Path(path)
    if not p.exists():
        return None
    try:
        text = p.read_text()
    except OSError:
        return UNREADABLE
    if not text.strip():
        return None
    if yaml is not None:
        try:
            return yaml.safe_load(text)
        except Exception:
            return UNREADABLE   # PyYAML present but the file is genuinely malformed
    _emit_belt_marker()
    try:
        return _minimal_yaml_load(text)
    except Exception:
        return UNREADABLE


# --------------------------------------------------------------------------- #
# minimal pure-stdlib YAML reader — FALLBACK ONLY (PyYAML absent).             #
# Covers exactly the subset selfcheck reads: block mappings (indent nesting),  #
# block sequences incl. list-of-maps, flow `[..]`/`{..}`, quote-aware comment  #
# stripping, and scalar typing (int/float/bool/null/quoted+bare str). NOT a    #
# general engine (no anchors/tags/multi-doc/block-scalars — our files use      #
# none). Verified byte-exact against PyYAML on every catalog manifest +        #
# profile.yaml (tests/test_selfcheck_stdlib_yaml.py).                          #
# --------------------------------------------------------------------------- #
def _minimal_yaml_load(text: str):
    lines = _y_lines(text)
    if not lines:
        return None
    value, idx = _y_block(lines, 0, lines[0][0])
    if idx != len(lines):
        raise ValueError(f"trailing content at logical line {idx}")
    return value


def _y_lines(text: str):
    out = []
    for raw in text.splitlines():
        stripped = _y_strip_comment(raw)
        if not stripped.strip():
            continue
        indent = len(stripped) - len(stripped.lstrip(" "))
        out.append((indent, stripped.strip()))
    return out


def _y_strip_comment(line: str) -> str:
    """Drop a trailing ``#`` comment, honoring quotes; ``#`` opens a comment only
    at line start or after whitespace (YAML rule), so ``a#b`` and URLs survive."""
    out = []
    quote = None
    prev_ws = True
    for ch in line:
        if quote:
            out.append(ch)
            if ch == quote:
                quote = None
            prev_ws = False
            continue
        if ch in ("'", '"'):
            quote = ch
            out.append(ch)
            prev_ws = False
            continue
        if ch == "#" and prev_ws:
            break
        out.append(ch)
        prev_ws = ch in (" ", "\t")
    return "".join(out)


def _y_block(lines, start, indent):
    if lines[start][1].startswith("- "):
        return _y_sequence(lines, start, indent)
    return _y_mapping(lines, start, indent)


def _y_sequence(lines, start, indent):
    items = []
    idx, n = start, len(lines)
    while idx < n:
        col, content = lines[idx]
        if col < indent:
            break
        if col > indent:
            raise ValueError(f"bad indent in sequence: {content!r}")
        if not content.startswith("-"):
            break
        rest = content[1:].lstrip(" ")
        if rest == "":
            child = idx + 1
            if child < n and lines[child][0] > indent:
                value, idx = _y_block(lines, child, lines[child][0])
                items.append(value)
                continue
            items.append(None)
            idx += 1
            continue
        item_col = col + (len(content) - len(rest))
        if _y_colon(rest) is not None:
            value, idx = _y_inline_mapping(lines, idx, item_col, rest)
            items.append(value)
        else:
            items.append(_y_scalar_or_flow(rest))
            idx += 1
    return items, idx


def _y_inline_mapping(lines, start, item_col, first_rest):
    mapping = {}
    key, val_text = _y_split_key(first_rest)
    idx, n = start + 1, len(lines)
    if val_text == "":
        if idx < n and lines[idx][0] > item_col:
            child, idx = _y_block(lines, idx, lines[idx][0])
            mapping[key] = child
        else:
            mapping[key] = None
    else:
        mapping[key] = _y_scalar_or_flow(val_text)
    while idx < n:
        col, content = lines[idx]
        if col != item_col or content.startswith("- ") or _y_colon(content) is None:
            break
        k, v = _y_split_key(content)
        if v == "":
            child = idx + 1
            if child < n and lines[child][0] > item_col:
                sub, idx = _y_block(lines, child, lines[child][0])
                mapping[k] = sub
                continue
            mapping[k] = None
            idx += 1
        else:
            mapping[k] = _y_scalar_or_flow(v)
            idx += 1
    return mapping, idx


def _y_mapping(lines, start, indent):
    mapping = {}
    idx, n = start, len(lines)
    while idx < n:
        col, content = lines[idx]
        if col < indent:
            break
        if col > indent:
            raise ValueError(f"bad indent in mapping: {content!r}")
        if content.startswith("- ") or _y_colon(content) is None:
            raise ValueError(f"expected 'key: value': {content!r}")
        key, val_text = _y_split_key(content)
        if val_text == "":
            child = idx + 1
            if child < n and lines[child][0] > indent:
                value, idx = _y_block(lines, child, lines[child][0])
                mapping[key] = value
                continue
            if child < n and lines[child][1].startswith("- ") and \
                    lines[child][0] == indent:
                value, idx = _y_sequence(lines, child, indent)
                mapping[key] = value
                continue
            mapping[key] = None
            idx += 1
        else:
            mapping[key] = _y_scalar_or_flow(val_text)
            idx += 1
    return mapping, idx


def _y_colon(content: str):
    """Index of the ``: ``/``:``-EOL key separator (quote-aware), or None."""
    quote = None
    for i, ch in enumerate(content):
        if quote:
            if ch == quote:
                quote = None
            continue
        if ch in ("'", '"'):
            quote = ch
            continue
        if ch == ":" and (i + 1 == len(content) or content[i + 1] == " "):
            return i
    return None


def _y_split_key(content: str):
    i = _y_colon(content)
    return _y_scalar(content[:i].strip()), content[i + 1:].strip()


def _y_scalar_or_flow(text: str):
    text = text.strip()
    if text[:1] in ("[", "{"):
        return _y_flow(text)
    return _y_scalar(text)


def _y_scalar(text: str):
    text = text.strip()
    if text in ("", "~", "null", "Null", "NULL"):
        return None
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ("'", '"'):
        inner = text[1:-1]
        return inner.replace("''", "'") if text[0] == "'" else _y_unescape(inner)
    low = text.lower()
    if low in ("true", "false"):
        return low == "true"
    body = text[1:] if text[:1] in "+-" else text
    if body.isdigit():
        return int(text)
    if _y_is_float(text):
        return float(text)
    return text


def _y_is_float(text: str) -> bool:
    body = text[1:] if text[:1] in "+-" else text
    if "e" in body.lower():
        try:
            float(text)
            return True
        except ValueError:
            return False
    if body.count(".") == 1 and body != ".":
        a, b = body.split(".")
        return (a.isdigit() or a == "") and (b.isdigit() or b == "") and \
            (a.isdigit() or b.isdigit())
    return False


def _y_unescape(inner: str) -> str:
    out, i = [], 0
    while i < len(inner):
        ch = inner[i]
        if ch == "\\" and i + 1 < len(inner):
            out.append({"n": "\n", "t": "\t", '"': '"', "\\": "\\",
                        "/": "/"}.get(inner[i + 1], inner[i + 1]))
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _y_flow(text: str):
    value, rest = _y_read_flow(text, 0)
    if rest.strip():
        raise ValueError(f"trailing flow content: {rest!r}")
    return value


def _y_read_flow(text, i):
    i = _y_ws(text, i)
    if text[i] == "[":
        return _y_flow_seq(text, i)
    if text[i] == "{":
        return _y_flow_map(text, i)
    return _y_flow_scalar(text, i)


def _y_flow_seq(text, i):
    i += 1
    items = []
    i = _y_ws(text, i)
    if i < len(text) and text[i] == "]":
        return [], text[i + 1:]
    while True:
        val, rest = _y_read_flow(text, i)
        items.append(val)
        i = _y_ws(text, len(text) - len(rest))
        if i >= len(text):
            raise ValueError("unterminated flow sequence")
        if text[i] == ",":
            i = _y_ws(text, i + 1)
            if text[i] == "]":
                return items, text[i + 1:]
            continue
        if text[i] == "]":
            return items, text[i + 1:]
        raise ValueError(f"bad flow sequence near {text[i:]!r}")


def _y_flow_map(text, i):
    i += 1
    mapping = {}
    i = _y_ws(text, i)
    if i < len(text) and text[i] == "}":
        return {}, text[i + 1:]
    while True:
        key, rest = _y_flow_scalar(text, i, stop=":,}")
        i = _y_ws(text, len(text) - len(rest))
        if i >= len(text) or text[i] != ":":
            raise ValueError(f"expected ':' in flow map near {text[i:]!r}")
        i = _y_ws(text, i + 1)
        val, rest = _y_read_flow(text, i)
        mapping[key] = val
        i = _y_ws(text, len(text) - len(rest))
        if i >= len(text):
            raise ValueError("unterminated flow mapping")
        if text[i] == ",":
            i = _y_ws(text, i + 1)
            if text[i] == "}":
                return mapping, text[i + 1:]
            continue
        if text[i] == "}":
            return mapping, text[i + 1:]
        raise ValueError(f"bad flow mapping near {text[i:]!r}")


def _y_flow_scalar(text, i, stop=",]}"):
    i = _y_ws(text, i)
    if i < len(text) and text[i] in ("'", '"'):
        quote = text[i]
        j, buf = i + 1, []
        while j < len(text):
            if text[j] == quote:
                if quote == "'" and j + 1 < len(text) and text[j + 1] == "'":
                    buf.append("'")
                    j += 2
                    continue
                break
            buf.append(text[j])
            j += 1
        raw = "".join(buf)
        val = raw.replace("''", "'") if quote == "'" else _y_unescape(raw)
        return val, text[j + 1:]
    j = i
    while j < len(text) and text[j] not in stop:
        j += 1
    return _y_scalar(text[i:j].strip()), text[j:]


def _y_ws(text, i):
    while i < len(text) and text[i] in (" ", "\t"):
        i += 1
    return i


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
def _r(kind, ok, reason="", remediation="", blocking=True, unknown=False, **extra):
    # `unknown=True` marks an ENVIRONMENT fault (a present-but-unreadable file, a corrupt db):
    # the verdict is UNKNOWN, never NOT-READY — the triage must report it and stop, never
    # onboard/coach from an assumed-first-run. Kept distinct from `ok`/`blocking` so a caller
    # can partition user-state gaps (NOT-READY) from env faults (UNKNOWN).
    d = {"kind": kind, "ok": bool(ok), "reason": reason,
         "remediation": remediation, "blocking": blocking, "unknown": bool(unknown)}
    d.update(extra)
    return d


def check_sqlite_db(a):
    path = expand(a["path"])
    want = list(a.get("must_have_tables", []))
    if not path.exists():
        return _r("sqlite_db", False, f"db missing at {path}",
                  "first-run §data: CREATE TABLE IF NOT EXISTS … (inline schema)")
    try:
        con = sqlite3.connect(str(path))
        try:
            have = {r[0] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
        finally:
            con.close()
    except sqlite3.Error as e:
        # Present but UNREADABLE (corrupt / locked): an environment fault, not "no db yet".
        # UNKNOWN → the triage reports it and stops; it must NOT re-create the db over data.
        return _r("sqlite_db", False, f"db present but UNREADABLE at {path} ({e})",
                  "environment fault: report the unreadable db; do NOT re-create it",
                  unknown=True)
    missing = [t for t in want if t not in have]
    if missing:
        return _r("sqlite_db", False, f"tables missing: {missing}",
                  "first-run §data: CREATE TABLE IF NOT EXISTS for the missing tables")
    return _r("sqlite_db", True, f"{path.name} has {len(want)} required tables")


def check_profile(a):
    path = expand(a["path"])
    req = list(a.get("required_fields", []))
    data = read_yaml(path)
    if data is UNREADABLE:
        # The file is THERE but unparseable — an environment fault (e.g. a genuinely
        # corrupt profile), NOT a fresh tenant. UNKNOWN, never NOT-READY: re-running the
        # intake would overwrite a real (unreadable) profile. This is the exact link that
        # turned the hh00046 env failure into a false onboarding.
        return _r("profile", False, f"profile present but UNREADABLE at {path}",
                  "environment fault: report the unreadable profile; do NOT re-run intake",
                  unknown=True)
    if not data:  # None (absent/empty) → genuine first-run
        return _r("profile", False, f"profile missing at {path}",
                  "first-run §profile: run the intake → write profile.yaml")
    if not isinstance(data, dict):
        # Present + parseable but the WRONG SHAPE (a list/scalar, not a mapping) — an authoring/
        # environment fault, not user state. UNKNOWN (never crash on `data.get`, never onboard).
        return _r("profile", False,
                  f"profile at {path} is not a mapping (got {type(data).__name__})",
                  "environment fault: the profile is malformed (not a key:value mapping); report it",
                  unknown=True)
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
    # A tools artifact may be declared `blocking: false` when its files are BUILT BY THE
    # TENANT'S AGENT during first-run (e.g. odoo-website's ~/odoo-site venv) rather than
    # shipped in the bundle — such files are first-run progress, never a delivery gate.
    blocking = a.get("blocking", True)
    missing = [name for name, fp in present_if_file.items() if not expand(fp).exists()]
    detail = {"available": [n for n in present_if_file if n not in missing],
              "stubbed": stubbed, "missing": missing}
    if missing:
        return _r("tools", False, f"required tool files missing: {missing}",
                  "deliver the bot bundle (overlay/bake) before first-run" if blocking
                  else "first-run builds these; the SKILL.md setup section drives toward READY",
                  blocking=blocking, **detail)
    note = "required tools present"
    if stubbed:
        note += f"; stubbed (degraded): {stubbed}"
    return _r("tools", True, note, blocking=False, **detail)


CHECKERS = {
    "sqlite_db": check_sqlite_db,
    "profile": check_profile,
    "memory": check_memory,
    "routing": check_routing,
    "cron": check_cron,
    "tools": check_tools,
}


def run(manifest_path: Path) -> dict:
    manifest = _load_yaml(manifest_path)
    if manifest is None:
        raise SystemExit(f"manifest not found: {manifest_path}")
    results = []
    for a in manifest.get("artifacts", []):
        kind = a.get("kind")
        checker = CHECKERS.get(kind)
        if checker is None:
            results.append(_r(kind or "?", False, f"unknown artifact kind '{kind}'",
                              blocking=False))
            continue
        results.append(checker(a))
    # Partition the failing blocking artifacts into ENV faults (UNKNOWN) and user-state
    # gaps (NOT-READY). An UNKNOWN present means we cannot trust the readiness computation —
    # ready is False AND the verdict is UNKNOWN (report-and-stop), never NOT-READY (onboard).
    unknown = [r for r in results if not r["ok"] and r.get("unknown")]
    missing = [r for r in results if not r["ok"] and r["blocking"] and not r.get("unknown")]
    return {
        "bot": manifest.get("bot"),
        "ready": len(missing) == 0 and len(unknown) == 0,
        "missing": missing,
        "unknown": unknown,
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
    # UNKNOWN wins the top-line verdict: an environment fault means we cannot judge
    # readiness at all. Report it and STOP — never fall through to NOT-READY (which the
    # triage reads as "first-run → onboard"). This is the three-valued contract (D-g).
    if report.get("unknown"):
        unknown = [f"{u['kind']}({u['reason']})" for u in report["unknown"]]
        print("UNKNOWN: env=" + json.dumps(unknown))
        for u in report["unknown"]:
            print(f"  - {u['kind']}: {u['reason']}  ->  {u['remediation']}")
        print("  => environment fault, NOT first-run. Do NOT onboard or coach; "
              "report this and stop.")
    elif report["ready"]:
        print("READY")
    else:
        missing = [f"{m['kind']}({m['reason']})" for m in report["missing"]]
        print("NOT-READY: missing=" + json.dumps(missing))
        for m in report["missing"]:
            print(f"  - {m['kind']}: {m['reason']}  ->  {m['remediation']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
