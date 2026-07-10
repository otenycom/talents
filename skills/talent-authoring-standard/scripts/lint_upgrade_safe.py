#!/usr/bin/env python3
"""Talent build-time lint — upgrade-safety (D53) + lean-authoring (D57).

A Talent bundle is FULLY REPLACED on every converge/update-talents and is loaded by
a small runtime model whose context fills with every body it `skill_view`s, so it
must (a) carry ZERO per-tenant state, (b) keep `SKILL.md` lean with detail in
`references/`, and (c) only ever run commands that DON'T trip Hermes' runtime
approval gate. This static lint FAILS a bundle that:

UPGRADE-SAFETY (D53 — applies to every bundle):
  1. ships a tenant-state / data-plane artifact (``*.db``, ``profile.yaml``,
     ``.bundle_lang``, ``memory.md``, ``USER.md``, ``sessions.json``) inside the
     bundle — those belong in ``~/.hermes/data/<bot>/`` (D34), never delivered;
  2. embeds a secret (a bot-token-shaped string, an ``sk-`` key, an api-key literal);
  3. hardcodes a Telegram chat/user id in a routing/config ASSIGNMENT — ids are
     resolved at runtime from ``channel_directory.json``, never baked (check 5/D53).

LEAN-AUTHORING (D57 — sharp index, lean bodies, declared/approval-clean commands):
  4. a ``SKILL.md`` ``description`` over 60 chars — the cached skill index truncates
     it to 57+"…" (hermes ``skill_utils.extract_skill_description``), so anything
     past 60 never reaches the router that the model self-selects on; keep it sharp;
  5. a ``SKILL.md`` body over 20,000 chars — native authoring says split into
     ``references/`` past ~20k (and the hard cap is 100k); a fat body sits in context
     on every load (the food-tracker loop, D57);
  6. (Talent only — a bundle with ``required_artifacts.yaml``) a delivered command
     (in ``SKILL.md`` / ``references/*.md``) that would trip the runtime APPROVAL
     gate: improvised code via ``python -c``/``-e``/heredoc, a ``bash -c`` one-off,
     a ``curl | sh`` pipe, an unguarded ``DELETE``/``DROP``/``TRUNCATE`` — a Talent
     Talent must use DECLARED scripts (``python3 scripts/x.py``, ``sqlite3 db <
     scripts/init.sql``) so first-run never stalls on "Command Approval Required";
  7. (Talent only) an inline ``CREATE TABLE`` in any ``.md`` — the schema lives in
     ONE executable place (``scripts/*.sql``); ``.md`` documents columns, never DDL;
  8. (Talent only) a ``## First-run setup`` section inside a ``SKILL.md`` body — it
     belongs in ``references/first-run.md`` (pulled only when selfcheck = NOT-READY);
  9. (Talent only) a ``required_artifacts.yaml`` with no ``agent-profile.yaml`` — a
     publishable Talent declares its persona/routing profile.

PUBLISHED-COPY HYGIENE (Talent only — a Talent ships to tenants AND reads publicly in
the open catalog repo, so internal build refs are a leak):
 10. an internal-build artifact in ANY bundle file (incl. comments/docstrings): a
     decision ref ``Dnn`` (e.g. ``D30``), the internal product name ``HermesHost``,
     or internal lifecycle jargon (``M-Pilot`` / ``infra-proof`` / ``golden image``).
     Ship plain English; the "why" lives in ``skills/design/``, never in a bundle. A
     line carrying ``lint-ok:`` is an explicit, reviewed exception (use sparingly).
     NOTE: ``stub``/``baked`` are deliberately NOT banned — ``stubbed`` is the real
     selfcheck graceful-degrade contract (a code key) and ``baked`` is a valid
     ``delivery:`` value and ordinary food prose; a *stale tool claim* (a tool called
     absent that is in fact live in the fleet registry) is caught by the registry
     check that ships with the ``hh.tool`` index, not by a blunt word ban.

VERSIONING & MIGRATION SHAPE (Talent only — upgrade coherence):
 11. ``agent-profile.yaml`` carries a valid semver ``version:`` (MAJOR.MINOR.PATCH) — a
     label over the delivered commit, bumped on every change. (Stdlib regex; always runs.)
 12. a ``migrations.yaml`` (present only for a Talent with mutable live state) is
     well-shaped: a ``migrations:`` LIST, each entry a unique ``id`` with ``kind`` ∈
     {``sql``, ``checklist``}; a ``sql`` kind has a non-empty ``sql`` body, a
     ``checklist`` kind a ``ref``; sql migrations require a top-level ``db:``. (Structural
     check needs PyYAML — CI installs it; skipped where absent.) The CROSS-version rules (a
     new migration forces a MINOR/MAJOR bump; a shipped id is never renamed/renumbered)
     need prior state and live in ``check_upgrade_coherence()`` (run in CI / at delivery,
     and exposed on the CLI via ``--against <prior_bundle_dir>``).

NEUTRALIZE SAFETY (Talent only — a clone of real state must not fire a live action, P4):
 13. a Talent with an OUTBOUND action — it declares required cron jobs (a ``cron`` artifact
     with a non-empty ``jobs:`` list, e.g. a scheduled DM) or an external ``seam:`` in
     ``agent-profile.yaml`` (a ``/json/2/`` integration) — MUST ship a ``neutralize.yaml``,
     and it must be well-shaped: a ``steps:`` LIST, each a unique ``id`` with ``kind`` ∈
     {``sql``, ``crons``, ``checklist``}; a ``crons`` step lists jobs to ``disable:`` and
     between them they cover EVERY declared required cron (else a clone would still fire the
     uncovered one); a ``sql`` step has a non-empty ``sql`` body. (Needs PyYAML; CI installs
     it.) Without it, a disposable clone of a real tenant inherits live crons/seams and DMs
     the real owner or files a real form — the whole point of P4's fail-closed gate.

SCHEDULED-CRON COST POLICY (Talent only — a recurring cron is the fleet's biggest cost
footgun; an unbounded or costly-persona reminder loop drained ~20-28% of a pilot owner's
spend):
 14. every REQUIRED cron (the always-on ``jobs:`` schedule) carries a cost policy in
     ``agent-profile.yaml`` ``crons:`` — a ``model:`` and a positive ``max_turns:`` (an
     unbounded cron turn can loop and drain credits) — and a daily-or-more job pinned ABOVE
     the cheap ``lite`` tier ships a written ``model_justification:`` (default to ``lite``;
     justify anything above it). The ``crons:`` names must match the required job names (a
     typo'd policy never binds). (Needs PyYAML; CI installs it.) ``max_turns`` is declared +
     linted here even though a per-cron cap is only EMITTED to the scheduler once a deployed
     Hermes honors it — the authoring gate is the enforcement point until then.
 15. A Talent that declares a hardware need — ``requires: {substrate, min_tier}`` — keeps the
     two consistent: ``substrate`` ∈ {vm, container}, ``min_tier`` ∈ {lite, power, max}, and a
     ``substrate: vm`` need names ``min_tier: max`` (the cheapest tier that provides a dedicated
     VM, D204). The Talent declares a CAPABILITY, never a raw customer tier as its contract; the
     platform resolves the tier (storefront gate + runtime self-gate). (Needs PyYAML.)

SOFT (non-blocking — surfaced as ``WARN``, never FAILs the gate, ``checklist_warnings``):
  the checklist-first bar (D85, the airline-pilot rule). Every Oteny skill the weak
  Flash tier runs — a sold **Talent** OR a non-Talent **infra-default** skill it uses
  day to day — is authored as a verifiable do-list, not prose. Warn a skill whose
  SKILL.md set shows no dispatch/checklist SHAPE (a triage, a skill-map table, or a
  numbered protocol), and (Talent only) no negative safety guardrail. Harden to FAIL
  once the shape is crisply assertable across every shipped bundle.

This is a BUILD-TIME gate over OUR catalog (CI / the offline suite is the gate; the
deployer also lints the delivery set before shipping). Run before shipping/baking.

Usage:
    python3 lint_upgrade_safe.py <bundle_dir> [<bundle_dir> ...] [--json]
Exits non-zero if any bundle has a violation.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # the migration-SHAPE structural check needs PyYAML (CI installs it);
    yaml = None      # everything else — including the version check — is stdlib.

# Per-tenant state / data-plane artifacts that must NEVER ship in a delivered bundle.
_STATE_GLOBS = (
    "*.db", "*.sqlite", "*.sqlite3", "profile.yaml", ".bundle_lang",
    "memory.md", "USER.md", "sessions.json",
)
_TEXT_SUFFIXES = {".md", ".yaml", ".yml", ".py", ".txt", ".json", ".toml", ".sh", ".cfg",
                  ".template"}  # *.md.template / *.yaml.template ship too — scan them for leaks
_SKIP_DIRS = {"__pycache__", ".git"}

_SECRET_PATTERNS = [
    (re.compile(r"\b\d{6,12}:[A-Za-z0-9_-]{30,}\b"), "telegram-bot-token-shaped string"),
    (re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"), "sk- API key"),
    (re.compile(r'(?i)\bapi[_-]?key\s*[:=]\s*["\'][^"\']{16,}["\']'), "hardcoded api key"),
]
# A Telegram id (≥6 digits) baked into a routing/config assignment (key : value or
# key = value). Prose mentions of the field name (comments) are skipped by the caller.
_ID_ASSIGN = re.compile(
    r"(?i)\b(channel_chat_id|chat_id|user_id|owner_telegram\w*|allowed_users|"
    r"allowed_chats|home_channel|telegram_bot_token|telegram_allowed\w*|telegram_group\w*)"
    r'\b\s*[:=]\s*["\']?[+-]?\d{6,}'
)

# D57 lean-authoring thresholds.
_DESC_MAX = 60          # hermes skill_utils truncates a description past 60 chars
_BODY_MAX = 20_000      # native "split into references/ past ~20k" rule
_BODY_HARD_MAX = 100_000  # native MAX_SKILL_CONTENT_CHARS

# Commands a delivered Talent must NOT tell the agent to run, because they trip
# Hermes' runtime approval gate (tools/approval.py DANGEROUS_PATTERNS) — a Talent
# bot then stalls on "Command Approval Required" instead of self-bootstrapping
# (D57). The fix is always a DECLARED script. Mirrors the gate's own regexes so the
# lint flags exactly what would stall (declared `python3 scripts/x.py`, `sqlite3 db
# < x.sql`, `bash scripts/x.sh` and guarded `DELETE … WHERE` are clean).
_APPROVAL_TRIPWIRES = [
    (re.compile(r"\b(python[23]?|perl|ruby|node)\s+-[ec]\b"),
     "improvised code via -e/-c (use a declared script: python3 scripts/x.py)"),
    (re.compile(r"\b(python[23]?|perl|ruby|node)\s+<<"),
     "improvised code via heredoc (use a declared script)"),
    (re.compile(r"\b(bash|sh|zsh|ksh)\s+-[^\s]*c(\s|$)"),
     "shell -c one-off (use a declared script: bash scripts/x.sh)"),
    (re.compile(r"\b(curl|wget)\b.*\|\s*(?:[/\w]*/)?(?:ba)?sh\b"),
     "pipes remote content to a shell"),
    (re.compile(r"\bDELETE\s+FROM\b(?![^\n]*\bWHERE\b)"),
     "unguarded SQL DELETE (add a WHERE, or use a declared reset script)"),
    (re.compile(r"\bDROP\s+(TABLE|DATABASE)\b"), "SQL DROP"),
    (re.compile(r"\bTRUNCATE\s+(TABLE)?\s*\w"), "SQL TRUNCATE"),
]
_CREATE_TABLE = re.compile(r"(?i)\bCREATE\s+TABLE\b")
_FIRSTRUN_HEADING = re.compile(r"(?im)^#{1,6}\s+.*first-run setup")
# A delimited fenced-code body is where the agent copies commands from; but flagging
# only fences is brittle, so we scan whole lines and skip obvious prose (a markdown
# table cell describing the anti-pattern, or a comment) — see _is_prose_line.

# Soft checklist-first signals (D85, the airline-pilot bar). Vocabulary-INDEPENDENT on
# purpose: Flatbelly says "triage", Stocks says "Skill map" + numbered "Operating
# rules" — both comply, neither shares a keyword. So we assert the SHAPE (a triage, a
# skill-map dispatch row, or a numbered protocol), never a literal word or filename (a
# `checklists.md` requirement would false-positive Stocks). Negative-guardrail presence
# is Talent-only: a user-facing Talent states its prohibitions in prose, but a
# mechanical infra skill (index-reconciler) keeps its safety in code and is exempt.
_TRIAGE = re.compile(r"(?i)\btriage\b")
_DISPATCH_ROW = re.compile(r"(?im)^\s*\|[^\n]*\bload\b[^\n]*\|")  # a "… | Load |" routing-table row
_ORDERED_ITEM = re.compile(r"(?m)^\s{0,3}\d+\.\s")               # a markdown ordered-list item
_NEGATIVE = re.compile(r"(?i)\b(never|don'?t|do not|must not|avoid)\b")

# (10) Published-copy hygiene — internal-build artifacts that must never appear in a
# PUBLISHED Talent (it ships to a tenant AND reads publicly in the open catalog repo).
# Scanned over ALL lines incl. comments/docstrings (a `# … (D34)` ref or a "HermesHost"
# docstring is exactly the leak). Talent-only: the author-tier bundles (the standard,
# the how-to) legitimately name these patterns, and this rules file lives in one of
# them — so it never lints itself. A line carrying `lint-ok:` is a reviewed exception.
_INTERNAL_ARTIFACTS = [
    (re.compile(r"\bD\d{2,3}\b"), "internal decision ref (Dnn) — drop it; rationale lives in skills/design/"),
    (re.compile(r"HermesHost"), "internal product name 'HermesHost' (say 'Oteny' / 'your bot')"),
    (re.compile(r"(?i)\bM-?Pilot\b"), "internal milestone name 'M-Pilot'"),
    (re.compile(r"(?i)\binfra-?proof\b"), "internal jargon 'infra-proof'"),
    (re.compile(r"(?i)\bgolden[- ]image\b"), "internal infra term 'golden image'"),
]
_LINT_OK = "lint-ok"


def _read_description(skill_md_text: str) -> str | None:
    """Extract the frontmatter ``description`` (single-line, quote-stripped), or None.

    Stdlib only (the lint stays import-light): grab the first ``---``…``---`` block
    and the ``description:`` line within it. Our bundles use single-line quoted
    descriptions, which is exactly what the cached index reads.
    """
    if not skill_md_text.startswith("---"):
        return None
    end = skill_md_text.find("\n---", 3)
    fm = skill_md_text[3:end] if end != -1 else skill_md_text[3:]
    m = re.search(r"(?m)^description:\s*(.+?)\s*$", fm)
    if not m:
        return None
    return m.group(1).strip().strip("'").strip('"').strip()


# --------------------------------------------------------------------------- #
# versioning + migration shape (checks 11/12) + cross-version coherence         #
# --------------------------------------------------------------------------- #
_SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.\-]+)?$")
_PROFILE_VERSION = re.compile(r"(?m)^version:\s*(.+?)\s*$")


def read_profile_version(bundle: Path) -> str | None:
    """The Talent's semver from ``agent-profile.yaml`` (stdlib regex), or None."""
    prof = bundle / "agent-profile.yaml"
    if not prof.is_file():
        return None
    m = _PROFILE_VERSION.search(prof.read_text(errors="ignore"))
    if not m:
        return None
    raw = m.group(1).strip()
    raw = re.split(r"\s+#", raw, maxsplit=1)[0].strip()   # drop an inline YAML comment
    return raw.strip("'").strip('"')


def migration_ids(bundle: Path) -> list[str]:
    """Declared migration ids, in order ([] if no migrations.yaml / PyYAML absent)."""
    mig = bundle / "migrations.yaml"
    if yaml is None or not mig.is_file():
        return []
    try:
        data = yaml.safe_load(mig.read_text()) or {}
    except yaml.YAMLError:
        return []
    return [m.get("id") for m in data.get("migrations", [])
            if isinstance(m, dict) and m.get("id")]


def _version_findings(bundle: Path) -> list[str]:
    v = read_profile_version(bundle)
    if v is None:
        return ["agent-profile.yaml has no `version:` — a publishable Talent carries a "
                "semver (a label over the delivered commit; bump it on every change)"]
    if not _SEMVER.match(v):
        return [f"agent-profile.yaml version '{v}' is not valid semver (MAJOR.MINOR.PATCH)"]
    return []


def _migration_shape_findings(bundle: Path) -> list[str]:
    mig = bundle / "migrations.yaml"
    if not mig.is_file():
        return []          # migrations are optional (only mutable-state Talents need them)
    if yaml is None:
        return []          # the structural check needs PyYAML; CI installs it, so it runs there
    try:
        data = yaml.safe_load(mig.read_text()) or {}
    except yaml.YAMLError as e:
        return [f"migrations.yaml does not parse: {e}"]
    migs = data.get("migrations")
    if not isinstance(migs, list):
        return ["migrations.yaml has no `migrations:` list"]
    out: list[str] = []
    seen: set[str] = set()
    has_sql = False
    for i, m in enumerate(migs):
        if not isinstance(m, dict) or not m.get("id"):
            out.append(f"migrations[{i}] has no `id`")
            continue
        mid = m["id"]
        if mid in seen:
            out.append(f"migrations.yaml duplicate id '{mid}'")
        seen.add(mid)
        kind = m.get("kind")
        if kind not in ("sql", "checklist"):
            out.append(f"migration '{mid}': kind must be 'sql' or 'checklist' (got {kind!r})")
        elif kind == "sql":
            has_sql = True
            if not str(m.get("sql") or "").strip():
                out.append(f"migration '{mid}': kind sql but no `sql` body")
        elif kind == "checklist" and not m.get("ref"):
            out.append(f"migration '{mid}': kind checklist but no `ref` to references/migrations.md")
    if has_sql and not data.get("db"):
        out.append("migrations.yaml has sql migrations but no top-level `db:` (the runner "
                   "can't locate the db to apply them)")
    return out


# (14) Scheduled-cron cost policy. Persona cost ladder (cheapest first) — a daily-or-more
# cron pinned above the cheap `lite` tier is the recurring-cost footgun (an unpinned or
# costly-persona reminder loop drained ~20-28% of a pilot owner's spend). `lite` is the
# floor; anything above it on a daily+ schedule must be justified in writing.
_PERSONA_RANK = {"lite": 0, "assistant": 1, "researcher": 2, "builder": 2}
_DAILY_OR_MORE = {"minutely", "hourly", "daily"}   # frequency tokens that fire >= daily


def required_cron_jobs(bundle: Path) -> list[str]:
    """Declared REQUIRED cron job names (the ``cron`` artifact's ``jobs:`` list) — the
    outbound DM schedule a clone must NOT inherit. [] if no required_artifacts / PyYAML
    absent / no cron artifact. Gated jobs (only live if the owner opts in) are not
    *required*, so they don't force a neutralize.yaml — they are caught by the clone
    path's universal cron-disable + the boot canary."""
    man = bundle / "required_artifacts.yaml"
    if yaml is None or not man.is_file():
        return []
    try:
        data = yaml.safe_load(man.read_text()) or {}
    except yaml.YAMLError:
        return []
    for a in data.get("artifacts", []):
        if isinstance(a, dict) and a.get("kind") == "cron":
            return [j for j in (a.get("jobs") or []) if j]
    return []


def _has_external_seam(bundle: Path) -> bool:
    """True if the Talent declares an external ``/json/2/`` seam in agent-profile.yaml (a
    business bot like the CrewRadar HR bot). A clone must repoint it at staging, so the
    Talent must ship a neutralize.yaml. Detection is an explicit ``seam:`` block — never a
    guess — so a self-contained Talent (flatbelly owns its own db) is not falsely flagged."""
    prof = bundle / "agent-profile.yaml"
    if yaml is None or not prof.is_file():
        return False
    try:
        data = yaml.safe_load(prof.read_text()) or {}
    except yaml.YAMLError:
        return False
    return bool(data.get("seam"))


# Check 15 — the hardware-requirement (`requires:`) block. A Talent declares a CAPABILITY it
# needs (a substrate), never a raw customer tier as its contract; min_tier is the resolved
# cheapest tier that provides it, kept honest here. D204: max → dedicated VM.
_REQUIRES_SUBSTRATES = {"vm", "container"}
_REQUIRES_MIN_TIERS = {"lite", "power", "max"}
_SUBSTRATE_MIN_TIER = {"vm": "max"}   # the cheapest subscription tier that provides a substrate


def _requires_findings(bundle: Path) -> list[str]:
    """(15) A ``requires: {substrate, min_tier}`` block must be internally consistent: substrate
    ∈ {vm, container}, min_tier ∈ {lite, power, max}, and a ``substrate: vm`` need must name
    ``min_tier: max`` (the cheapest tier that provides a VM today, D204) — so the storefront gate
    + the runtime self-gate resolve to a plan that actually delivers the capability. Needs PyYAML
    (CI installs it); a bundle without the block is unaffected."""
    prof = bundle / "agent-profile.yaml"
    if yaml is None or not prof.is_file():
        return []
    try:
        data = yaml.safe_load(prof.read_text()) or {}
    except yaml.YAMLError:
        return []
    req = data.get("requires")
    if req is None:
        return []
    if not isinstance(req, dict):
        return ["agent-profile.yaml: `requires` must be a mapping, e.g. "
                "requires: {substrate: vm, min_tier: max}"]
    findings: list[str] = []
    substrate = req.get("substrate")
    min_tier = req.get("min_tier")
    if substrate is not None and substrate not in _REQUIRES_SUBSTRATES:
        findings.append(f"agent-profile.yaml: requires.substrate {substrate!r} is not one of "
                        f"{sorted(_REQUIRES_SUBSTRATES)}")
    if min_tier is not None and min_tier not in _REQUIRES_MIN_TIERS:
        findings.append(f"agent-profile.yaml: requires.min_tier {min_tier!r} is not one of "
                        f"{sorted(_REQUIRES_MIN_TIERS)}")
    need = _SUBSTRATE_MIN_TIER.get(substrate)
    if need and min_tier != need:
        findings.append(
            f"agent-profile.yaml: requires.substrate: {substrate} needs min_tier: {need} (the "
            f"cheapest tier that provides it, D204) but min_tier is {min_tier!r} — set "
            f"min_tier: {need} so the purchase-gate resolves to a plan that delivers the VM")
    if substrate is None and min_tier is not None:
        findings.append("agent-profile.yaml: requires.min_tier without requires.substrate — "
                        "declare the capability (the substrate) the tier stands for")
    return findings


def _neutralize_findings(bundle: Path) -> list[str]:
    """(13) An outbound-action Talent MUST ship a well-shaped neutralize.yaml that covers
    every declared required cron. A self-contained Talent with no outbound action needs
    none; a neutralize.yaml that IS present is shape-checked regardless."""
    neu = bundle / "neutralize.yaml"
    required = required_cron_jobs(bundle)
    needs = bool(required) or _has_external_seam(bundle)
    if not neu.is_file():
        if needs:
            why = "required cron jobs" if required else "an external seam"
            return [f"declares an outbound action ({why}) but ships no neutralize.yaml — a "
                    "clone of this Talent's real state would inherit it and fire a live "
                    "action; ship neutralize.yaml (kind: crons disables every declared job, "
                    "kind: sql repoints the seam) — P4 fail-closed gate"]
        return []
    if yaml is None:
        return []          # the structural check needs PyYAML; CI installs it
    try:
        data = yaml.safe_load(neu.read_text()) or {}
    except yaml.YAMLError as e:
        return [f"neutralize.yaml does not parse: {e}"]
    steps = data.get("steps")
    if not isinstance(steps, list):
        return ["neutralize.yaml has no `steps:` list"]
    out: list[str] = []
    seen: set[str] = set()
    disabled: set[str] = set()
    has_sql = False
    for i, s in enumerate(steps):
        if not isinstance(s, dict) or not s.get("id"):
            out.append(f"neutralize.yaml steps[{i}] has no `id`")
            continue
        sid = s["id"]
        if sid in seen:
            out.append(f"neutralize.yaml duplicate step id '{sid}'")
        seen.add(sid)
        kind = s.get("kind")
        if kind not in ("sql", "crons", "checklist"):
            out.append(f"neutralize step '{sid}': kind must be sql|crons|checklist (got {kind!r})")
        elif kind == "sql":
            has_sql = True
            if not str(s.get("sql") or "").strip():
                out.append(f"neutralize step '{sid}': kind sql but no `sql` body")
        elif kind == "crons":
            names = ((s.get("crons") or {}).get("disable")) or []
            if not names:
                out.append(f"neutralize step '{sid}': kind crons but lists no jobs to disable")
            disabled |= {n for n in names if n}
        elif kind == "checklist" and not s.get("ref"):
            out.append(f"neutralize step '{sid}': kind checklist but no `ref` to references/neutralize.md")
    if has_sql and not (data.get("db") or any(
            isinstance(s, dict) and s.get("db") for s in steps)):
        out.append("neutralize.yaml has sql steps but no `db:` (top-level or per-step)")
    uncovered = [j for j in required if j not in disabled]
    if uncovered:
        out.append(f"neutralize.yaml does not disable every required cron: {uncovered} "
                   "still live — a clone would fire them (add them to a `crons` step's disable list)")
    return out


def _cron_policy_entries(bundle: Path) -> list[dict]:
    """The per-job cron cost policy declared in agent-profile.yaml's ``crons:`` list
    ([] if none / PyYAML absent). Each entry: ``name`` + ``frequency`` + ``model`` +
    ``max_turns`` (+ optional ``model_justification`` / ``expected_cost``)."""
    prof = bundle / "agent-profile.yaml"
    if yaml is None or not prof.is_file():
        return []
    try:
        data = yaml.safe_load(prof.read_text()) or {}
    except yaml.YAMLError:
        return []
    crons = data.get("crons")
    return [c for c in crons if isinstance(c, dict)] if isinstance(crons, list) else []


def _cron_policy_findings(bundle: Path) -> list[str]:
    """(14) Scheduled-cron cost policy. Every REQUIRED cron (the always-on ``jobs:``
    schedule, same scope as the neutralize gate — gated opt-in jobs are out of scope)
    must carry a cost policy in agent-profile.yaml ``crons:``: a ``model:`` and a positive
    ``max_turns:`` (an unbounded cron turn can loop and drain credits). A daily-or-more job
    pinned ABOVE the cheap ``lite`` tier must ship a written ``model_justification:`` (a
    costly persona on a recurring schedule is the cron cost footgun — default to ``lite``,
    justify anything above it). Also cross-checks that the ``crons:`` policy names match the
    required job names (a typo'd policy never binds to a real job)."""
    if yaml is None:
        return []          # needs PyYAML to read the policy; CI installs it, so it runs there
    required = required_cron_jobs(bundle)
    policy = {c["name"]: c for c in _cron_policy_entries(bundle) if c.get("name")}
    out: list[str] = []
    for name in required:
        c = policy.get(name)
        if c is None:
            out.append(f"cron '{name}': no cost policy in agent-profile.yaml `crons:` — every "
                       "scheduled cron must declare `model:` + a positive `max_turns:` (an "
                       "unbounded cron can loop and drain credits)")
            continue
        mt = c.get("max_turns")
        if not isinstance(mt, int) or mt <= 0:
            out.append(f"cron '{name}': no positive `max_turns:` — bound the turn (an "
                       "unbounded cron can loop and drain credits)")
        freq = str(c.get("frequency") or "").strip().lower()
        model = str(c.get("model") or "assistant").strip().lower()
        if (freq in _DAILY_OR_MORE
                and _PERSONA_RANK.get(model, 1) > _PERSONA_RANK["lite"]
                and not str(c.get("model_justification") or "").strip()):
            out.append(f"cron '{name}': {freq} job pinned to '{model}' (above `lite`) with no "
                       "`model_justification:` — a costly persona on a daily+ schedule is a "
                       "recurring cost; pin `lite` or justify it in writing")
    for name in policy:
        if name not in required:
            out.append(f"agent-profile.yaml `crons:` names '{name}' with no matching required "
                       "cron in required_artifacts.yaml (name drift — the policy never binds)")
    return out


def _semver_tuple(v: str | None):
    if not v or not _SEMVER.match(v):
        return None
    core = v.split("+")[0].split("-")[0]
    return tuple(int(x) for x in core.split("."))


def check_upgrade_coherence(prev: dict, cur: dict) -> list[str]:
    """Cross-VERSION coherence between a prior published bundle state and the current one.

    ``prev`` / ``cur`` are ``{"version": "<semver>", "migration_ids": [<id>, ...]}``. Catches
    a renumbered/renamed/removed shipped migration id (ids are append-only) and a new
    migration shipped WITHOUT a MINOR/MAJOR bump (the forgotten-bump footgun). Pure — wired
    into CI / at delivery, where the prior state is read from the merge base or the live
    delivered commit. Returns [] when coherent."""
    out: list[str] = []
    cv = _semver_tuple(cur.get("version"))
    if cv is None:
        return [f"current version '{cur.get('version')}' is not valid semver"]
    pv = _semver_tuple(prev.get("version"))
    if pv is None:
        return out  # first publish (or no prior) — nothing to compare against
    pids = list(prev.get("migration_ids") or [])
    cids = list(cur.get("migration_ids") or [])
    append_only = cids[:len(pids)] == pids
    if not append_only:
        out.append("migrations are not append-only: a shipped id was renamed, renumbered, "
                   f"or removed (was {pids}, now {cids}) — never mutate a shipped id")
    new_ids = cids[len(pids):] if append_only else [i for i in cids if i not in pids]
    if new_ids:
        if cv <= pv:
            out.append(f"new migration(s) {new_ids} added without a version bump "
                       f"({prev.get('version')} -> {cur.get('version')}): bump MINOR or MAJOR")
        elif (cv[0], cv[1]) == (pv[0], pv[1]):
            out.append(f"new migration(s) {new_ids} need a MINOR or MAJOR bump, not just "
                       f"PATCH ({prev.get('version')} -> {cur.get('version')})")
    return out


def _is_comment_line(line: str) -> bool:
    """A line that documents rather than executes — a comment or a blockquote.

    Command-hygiene (tripwires + CREATE TABLE) is additionally gated to ``` fenced
    code blocks, so a runnable command belongs in a fence; put recipes there, not in a
    table cell or inline prose, and the lint reasons about them correctly.
    """
    s = line.lstrip()
    return s.startswith("#") or s.startswith(">")


def lint_bundle(bundle: Path) -> list[str]:
    """Return a list of build-time violations for one bundle dir ('' = clean)."""
    findings: list[str] = []
    is_talent = (bundle / "required_artifacts.yaml").is_file()

    # (1) shipped tenant-state / data-plane artifacts.
    for pat in _STATE_GLOBS:
        for p in bundle.rglob(pat):
            if _SKIP_DIRS & set(p.parts):
                continue
            findings.append(
                f"ships tenant-state artifact {p.relative_to(bundle)} "
                "(belongs in the data plane ~/.hermes/data/<bot>/, never delivered)"
            )

    # (9) a Talent declares its persona/routing profile.
    if is_talent and not (bundle / "agent-profile.yaml").is_file():
        findings.append(
            "declares required_artifacts.yaml (a Talent) but has no agent-profile.yaml "
            "(a publishable Talent needs its persona/routing profile)"
        )

    # (11)+(12) versioning + migration shape — Talent only. The version check needs the
    # profile to exist (the (9) finding already covers its absence), so guard on it.
    if is_talent and (bundle / "agent-profile.yaml").is_file():
        findings += _version_findings(bundle)
    if is_talent:
        findings += _migration_shape_findings(bundle)
        findings += _neutralize_findings(bundle)   # (13) outbound-action Talent must de-fang clones
        findings += _cron_policy_findings(bundle)  # (14) scheduled-cron cost policy
        findings += _requires_findings(bundle)     # (15) requires: substrate↔min_tier consistency

    for p in sorted(bundle.rglob("*")):
        if not p.is_file() or p.suffix not in _TEXT_SUFFIXES or _SKIP_DIRS & set(p.parts):
            continue
        rel = p.relative_to(bundle)
        text = p.read_text(errors="ignore")
        is_md = p.suffix == ".md"
        is_skill_md = p.name == "SKILL.md"

        # (2) embedded secrets — every file.
        for rx, label in _SECRET_PATTERNS:
            if rx.search(text):
                findings.append(f"{rel}: embeds a {label}")

        # (4)+(5) SKILL.md description + body size — every bundle.
        if is_skill_md:
            desc = _read_description(text)
            if desc is not None and len(desc) > _DESC_MAX:
                findings.append(
                    f"{rel}: description is {len(desc)} chars (>{_DESC_MAX}); the skill "
                    "index truncates it — keep the router trigger sharp and ≤60"
                )
            if len(text) > _BODY_HARD_MAX:
                findings.append(f"{rel}: {len(text)} chars exceeds the native hard cap "
                                f"of {_BODY_HARD_MAX}")
            elif len(text) > _BODY_MAX:
                findings.append(
                    f"{rel}: {len(text)} chars (>{_BODY_MAX}) — split detail into "
                    "references/ (native authoring rule); a fat body sits in context "
                    "on every load"
                )

        # (10) published-copy hygiene — Talent only; scans EVERY line (incl. comments
        # and docstrings, where the leaks hide), with a `lint-ok:` per-line escape.
        if is_talent:
            for ln, line in enumerate(text.splitlines(), 1):
                if _LINT_OK in line:
                    continue
                for rx, label in _INTERNAL_ARTIFACTS:
                    if rx.search(line):
                        findings.append(f"{rel}:{ln}: published-copy leak — {label}")

        # (8) first-run must live in references/, not a SKILL.md body — Talent only.
        if is_talent and is_skill_md and _FIRSTRUN_HEADING.search(text):
            findings.append(
                f"{rel}: a '## First-run setup' section in the body — move it to "
                "references/first-run.md (pulled only when selfcheck = NOT-READY)"
            )

        in_fence = False  # command-hygiene only fires inside ``` fenced code blocks
        for ln, line in enumerate(text.splitlines(), 1):
            if is_md and line.lstrip().startswith("```"):
                in_fence = not in_fence
                continue
            if _is_comment_line(line):  # a comment / blockquote documents, never runs
                continue
            # (3) hardcoded Telegram id in an assignment — every file.
            if _ID_ASSIGN.search(line):
                findings.append(
                    f"{rel}:{ln}: hardcodes a Telegram id in a routing/config "
                    "assignment (resolve ids at runtime, never bake them)"
                )

            # (6)+(7) command hygiene — Talent, only inside a fenced code block (where
            # the agent copies commands from). An inline-backtick MENTION of an
            # anti-pattern in prose ("never run `python3 -c`") is guidance, not a
            # runnable command, so it is exempt.
            if is_talent and is_md and in_fence:
                for rx, label in _APPROVAL_TRIPWIRES:
                    if rx.search(line):
                        findings.append(f"{rel}:{ln}: {label}")
                if _CREATE_TABLE.search(line):
                    findings.append(
                        f"{rel}:{ln}: inline CREATE TABLE — the schema lives once in "
                        "scripts/*.sql (run via `sqlite3 db < scripts/init.sql`); "
                        "document columns in prose, not DDL"
                    )
    return findings


def _skill_md_texts(bundle: Path) -> list[str]:
    """Every SKILL.md body in the bundle (umbrella + child skills); pycache skipped."""
    return [
        p.read_text(errors="ignore")
        for p in sorted(bundle.rglob("SKILL.md"))
        if not _SKIP_DIRS & set(p.parts)
    ]


def checklist_warnings(bundle: Path) -> list[str]:
    """SOFT, non-blocking checklist-first signals (D85) — kept OUT of ``lint_bundle`` so
    the FAIL gate is untouched. Covers every skill the weak Flash tier runs (a Talent OR
    an infra-default operational skill); a bundle with no SKILL.md (shared assets) is
    exempt. Returns [] for a clean bundle."""
    texts = _skill_md_texts(bundle)
    if not texts:
        return []
    blob = "\n".join(texts)
    warnings: list[str] = []
    has_shape = bool(
        _TRIAGE.search(blob)
        or _DISPATCH_ROW.search(blob)
        or len(_ORDERED_ITEM.findall(blob)) >= 3
    )
    if not has_shape:
        warnings.append(
            "no checklist-first shape in any SKILL.md (a master triage, a skill-map "
            "dispatch table, or a numbered protocol) — author every task as a verifiable "
            "do-list, not prose (the airline-pilot bar, D85)"
        )
    # Negative guardrails: Talent-only — a mechanical infra skill keeps its safety in code.
    if (bundle / "required_artifacts.yaml").is_file() and not _NEGATIVE.search(blob):
        warnings.append(
            "a Talent with no negative guardrails (never/don't/avoid) in any SKILL.md — "
            "state the hard prohibitions, placed last so the weak model reads them most "
            "recently (D85)"
        )
    return warnings


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Talent upgrade-safety lint (D53 check 12)")
    ap.add_argument("bundles", nargs="+", help="bundle directories to lint")
    ap.add_argument("--against", default=None,
                    help="a prior bundle dir to check version/migration coherence against "
                         "(single bundle only; CI/at-delivery passes the merge-base copy)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    report: dict[str, list[str]] = {}
    warns: dict[str, list[str]] = {}
    ok = True
    for b in args.bundles:
        bp = Path(b)
        violations = lint_bundle(bp)
        report[bp.name] = violations
        warns[bp.name] = checklist_warnings(bp)  # soft (D85) — does NOT affect exit code
        if violations:
            ok = False

    # Cross-version coherence (a new migration forces a bump; a shipped id is never
    # renamed/renumbered). Needs the prior bundle state — passed via --against.
    if args.against and len(args.bundles) == 1:
        bp = Path(args.bundles[0])
        prior = Path(args.against)
        coh = check_upgrade_coherence(
            {"version": read_profile_version(prior), "migration_ids": migration_ids(prior)},
            {"version": read_profile_version(bp), "migration_ids": migration_ids(bp)},
        )
        report[bp.name] = report.get(bp.name, []) + coh
        if coh:
            ok = False

    # Cross-bundle sub-skill uniqueness (check 16). Hermes resolves skills by BARE
    # directory name across the whole delivered tree and REFUSES a name matching more
    # than one dir — so two bundles each shipping e.g. `onboarding/` break every
    # dual-Talent tenant (the 2026-07-10 travel-intake incident). Sub-skill dir names
    # must be globally unique across the linted set; prefix with the Talent's domain.
    if len(args.bundles) > 1:
        owners: dict[str, list[str]] = {}
        for b in args.bundles:
            bp = Path(b)
            for md in sorted(bp.rglob("SKILL.md")):
                sub = md.parent
                if sub == bp or any(part.startswith(".") for part in sub.parts):
                    continue
                owners.setdefault(sub.name, []).append(f"{bp.name}/{sub.relative_to(bp)}")
        for name, paths in sorted(owners.items()):
            if len(paths) > 1:
                ok = False
                for p in paths:
                    bundle = p.split("/", 1)[0]
                    report.setdefault(bundle, []).append(
                        f"cross-bundle sub-skill name collision: {name!r} also shipped by "
                        f"{[q for q in paths if not q.startswith(bundle + '/')]} — bare-name "
                        f"skill lookup refuses duplicates; rename with a Talent prefix")

    if args.json:
        print(json.dumps({"ok": ok, "violations": report, "warnings": warns}, indent=2))
    else:
        for name, violations in report.items():
            if violations:
                print(f"FAIL {name}:")
                for v in violations:
                    print(f"  - {v}")
            else:
                print(f"PASS {name}")
            for w in warns[name]:
                print(f"  WARN: {w}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
