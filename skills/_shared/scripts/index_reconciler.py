#!/usr/bin/env python3
"""index-reconciler — keep a tenant's routing index in sync with installed bots.

Generalises the proven live PoC (D33: backup → write quoted
``telegram.channel_prompts`` via ruamel → validate → restart → confirm a fresh
polling marker). The PoC hardcoded two prompts; this is **declaration-driven**:

  * each bot DECLARES its routing in ``agent-profile.yaml`` (a ``routing:`` block);
  * this reconciler scans those declarations + the live channel directory and
    reconciles ``config.yaml`` to match — add for new bots, remove for uninstalled
    ones, self-heal a drifted instance, all idempotent;
  * the apply step is pure config writes — no LLM judgement (declared-routing,
    D33).

Hard requirements learned live (D33 live-box findings, now enforced here):
  1. ``channel_prompts`` keys MUST be quoted strings (negative group ids parse as
     ints unquoted → ``prompts.get(str(chat.id))`` silently misses).
  2. Comment-preserving edits only — ruamel round-trip targeting ``telegram:``
     specifically (every platform section has its own ``channel_prompts``).
  3. ``channel_prompts`` load at gateway start → a restart + fresh polling marker
     is required to apply (handled by ``restart_and_verify``).

The diff/compute layer is pure and import-safe (no ruamel, no IO) so it is fully
unit-testable; ruamel is only needed for ``--apply``.

Usage:
    python3 index_reconciler.py                 # dry-run: print the plan
    python3 index_reconciler.py --apply         # write config (backup first)
    python3 index_reconciler.py --apply --restart   # also restart + verify gateway
    python3 index_reconciler.py --skills-root DIR --config PATH --channels PATH

Home roots honor the same env overrides as selfcheck (HH_HOME / HH_HERMES_HOME).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


# --------------------------------------------------------------------------- #
# paths                                                                        #
# --------------------------------------------------------------------------- #
def _home() -> Path:
    return Path(os.environ.get("HH_HOME") or Path.home())


def _hermes_home() -> Path:
    env = os.environ.get("HH_HERMES_HOME")
    return Path(env) if env else _home() / ".hermes"


def default_skills_root() -> Path:
    return _hermes_home() / "skills" / "talents"


def default_config() -> Path:
    return _hermes_home() / "config.yaml"


def default_channels() -> Path:
    return _hermes_home() / "channel_directory.json"


def default_soul() -> Path:
    return _hermes_home() / "SOUL.md"


def default_overrides_dir() -> Path:
    # D53 durable overrides live in the never-touched DATA plane (D34), so the
    # converge's atomic overlay swap never disturbs them.
    return _hermes_home() / "data" / "_overrides"


def default_intents() -> Path:
    # Owner per-group intents (auth enable/disable + the D57 `talent` routing override),
    # written off-VM by the control plane / capture path. Same file the group-auth path
    # reads. Absent on a fresh tenant → no overrides.
    return _hermes_home() / "data" / "group-access.json"


# --------------------------------------------------------------------------- #
# pure layer: declarations -> desired map -> diff                             #
# --------------------------------------------------------------------------- #
def load_declarations(skills_root: Path) -> list[dict]:
    """Scan ``<skills_root>/*/agent-profile.yaml`` for ``routing:`` blocks."""
    decls = []
    if not skills_root.exists():
        return decls
    for profile in sorted(skills_root.glob("*/agent-profile.yaml")):
        data = yaml.safe_load(profile.read_text()) if yaml else None
        routing = (data or {}).get("routing")
        if not routing:
            continue
        decls.append({
            "bot": (data or {}).get("bot") or profile.parent.name,
            "channel": routing.get("channel"),
            "channel_chat_id": routing.get("channel_chat_id"),
            "channel_prompt": routing.get("channel_prompt", "").strip(),
            "signature": routing.get("signature") or profile.parent.name,
        })
    return decls


def resolve_chat_id(decl: dict) -> str | None:
    """The chat-id a declaration is EXPLICITLY bound to, or None (D57).

    Name→channel_directory resolution is gone: a Talent named after its group no
    longer auto-binds (the hh-group-focus-hint plugin routes any-titled groups via the
    native index). Binding is now explicit only — a decl with a ``channel_chat_id``, or
    an owner override (handled in ``compute_desired``).
    """
    cid = decl.get("channel_chat_id")
    return str(cid) if cid not in (None, "") else None


def load_talent_overrides(intents_path: Path) -> dict[str, str]:
    """Read the owner's per-chat Talent binding ``{chat_id: slug}`` from the intents file.

    The owner can pin an ambiguous group to a specific Talent regardless of its title
    (D57 — drops the "group title must equal routing.channel" requirement). The file is
    the same per-group intents JSON the group-auth path uses
    (``~/.hermes/data/group-access.json``); an entry's ``talent`` field is the binding.
    Tolerant of empty / missing / malformed input (returns ``{}``).
    """
    if not intents_path.exists():
        return {}
    try:
        data = json.loads(intents_path.read_text())
    except (ValueError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, str] = {}
    for cid, val in data.items():
        slug = val.get("talent") if isinstance(val, dict) else None
        if isinstance(slug, str) and slug.strip():
            out[str(cid)] = slug.strip()
    return out


def compute_desired(
    decls: list[dict], overrides: dict[str, str] | None = None
) -> tuple[dict, list[dict]]:
    """Return (desired channel_prompts ``{chat_id_str: prompt}``, unresolved overrides).

    Two binding sources (D57), both keyed by chat-id, no title matching:
      * a declaration with an explicit ``channel_chat_id`` → its channel_prompt;
      * an owner override (``{chat_id: slug}``) → that Talent's channel_prompt (wins).
    An override naming a slug with no matching declaration (or no channel_prompt) is
    returned as ``unresolved`` (reported, never guessed).
    """
    by_bot = {d.get("bot"): d for d in decls}
    desired: dict[str, str] = {}
    unresolved: list[dict] = []
    for d in decls:
        if not d.get("channel_prompt"):
            continue
        chat_id = resolve_chat_id(d)
        if chat_id is not None:
            desired[chat_id] = d["channel_prompt"]
    for chat_id, slug in (overrides or {}).items():
        d = by_bot.get(slug)
        if d and d.get("channel_prompt"):
            desired[str(chat_id)] = d["channel_prompt"]
        else:
            unresolved.append({"bot": slug, "chat_id": str(chat_id)})
    return desired, unresolved


def diff(current: dict, desired: dict) -> dict:
    """Classify each chat id into add / update / remove / keep."""
    current = {str(k): v for k, v in (current or {}).items()}
    add = {k: v for k, v in desired.items() if k not in current}
    update = {k: v for k, v in desired.items() if k in current and current[k] != v}
    remove = {k: current[k] for k in current if k not in desired}
    keep = {k: v for k, v in desired.items() if k in current and current[k] == v}
    return {"add": add, "update": update, "remove": remove, "keep": keep}


def has_changes(plan: dict) -> bool:
    return bool(plan["add"] or plan["update"] or plan["remove"])


# --------------------------------------------------------------------------- #
# SOUL DM-hints — REMOVED (D57). DM routing is native (the one-line skill index +    #
# `skill_view`), so a hand-written "shared-DM routing hints" block is redundant and  #
# just bloats the always-injected SOUL. We no longer WRITE this block; we only strip #
# a stale one left by a pre-D57 tenant so converge cleans it up.                      #
# --------------------------------------------------------------------------- #
SOUL_START = "<!-- reconciler:dm-hints:start -->"
SOUL_END = "<!-- reconciler:dm-hints:end -->"


def remove_soul_hints(soul_text: str) -> str:
    """Strip a stale reconciler-managed DM-hints block (pre-D57 cleanup); else no-op."""
    if SOUL_START in soul_text and SOUL_END in soul_text:
        pre = soul_text.split(SOUL_START)[0]
        post = soul_text.split(SOUL_END, 1)[1]
        return (pre.rstrip("\n") + "\n" + post.lstrip("\n")).rstrip("\n") + "\n"
    return soul_text


# --------------------------------------------------------------------------- #
# SOUL group-guard (managed between markers, idempotent) — D36 A+              #
# --------------------------------------------------------------------------- #
# A static cross-cutting scope rule: a group's OWN skill (and all its data) is open
# to everyone in the group — that is the group's purpose (a coach/dietician invited
# into a weight group is meant to see the food & weight data). The boundary applies
# only to a GUEST asking OUTSIDE the group's topic — they must not pull a different
# skill's data or browse the instance. The OWNER is never restricted. Best-effort
# (LLM-enforced); the rock-solid path is a dedicated scoped instance (D37). Needs
# shared group sessions (group_sessions_per_user false) so the model sees a
# `[SenderName]` prefix and can tell the owner from a guest.
GUARD_START = "<!-- reconciler:group-guard:start -->"
GUARD_END = "<!-- reconciler:group-guard:end -->"

GROUP_GUARD_BODY = (
    "## Group scope (reconciler-managed — do not hand-edit)\n"
    "Every group has a topic — the Talent it is for. Infer it from the group's name "
    "(the hh-group-focus-hint plugin injects the live group title into each message) "
    "and what members discuss, then match it to the loaded Talents by their skill "
    "descriptions. These rules apply to GROUP messages only — DMs are unrestricted.\n"
    "- When the group clearly matches ONE Talent, ACT AS that Talent: load it, answer "
    "in its voice, and tailor every reply — including how you introduce yourself — to "
    "that Talent; do NOT enumerate your other Talents. Stay yourself (the owner's "
    "OtenyBot, by your own bot name) using that Talent — the Talent is a capability, "
    "not your identity. If the group's name is generic or matches nothing, answer "
    "normally as the owner's OtenyBot.\n"
    "- The group's OWN skill and ALL of that skill's data are OPEN to everyone in "
    "the group — share them freely. A weight/health group sees the food & weight "
    "data; a stocks group sees the portfolio. That is the group's purpose (a coach "
    "or dietician invited into the group is meant to see it).\n"
    "- The bot's OWNER — the person who set up this bot (named in the skill "
    "profiles; the only person served in private DM) — is NEVER restricted: answer "
    "the owner anything, in any group.\n"
    "- Any OTHER member is a guest. For a guest, stay within THIS group's topic: do "
    "NOT use a different skill's data, and do NOT browse the instance (listing "
    "files/folders, reading arbitrary paths, dumping other databases), to answer "
    "them. If a guest asks outside this group's topic, briefly decline and suggest "
    "they ask the owner (or use their own bot)."
)


def render_group_guard_block() -> str:
    return f"{GUARD_START}\n{GROUP_GUARD_BODY}\n{GUARD_END}"


def upsert_group_guard(soul_text: str) -> str:
    block = render_group_guard_block()
    if GUARD_START in soul_text and GUARD_END in soul_text:
        pre = soul_text.split(GUARD_START)[0]
        post = soul_text.split(GUARD_END, 1)[1]
        return pre + block + post
    sep = "" if soul_text.endswith("\n") else "\n"
    return soul_text + f"{sep}\n{block}\n"


# --------------------------------------------------------------------------- #
# SOUL per-tenant override (managed between markers, idempotent) — D53          #
# --------------------------------------------------------------------------- #
# SOUL.md is ALWAYS-INJECTED identity (Hermes prepends it every turn), so a
# per-tenant customization can't be a sibling file the model "might read" — it must
# be present in the SOUL itself. D53: the control plane writes only base + rendered
# artifacts; the durable per-tenant override lives in the never-touched DATA plane
# (`~/.hermes/data/_overrides/`), and the reconciler INLINES it here as a third
# managed block at converge — so converge can overwrite SOUL.md fearlessly every
# upgrade while the customization persists. Two durable sources (D53): the
# OPERATOR override (`soul-override.operator.md`, delivered by the control plane from
# the Odoo `soul_override` field — survives a full VM rebuild) and the OWNER/agent
# override (`soul-override.md`, agent-writable on the VM). Both are consolidated,
# precedence-labelled, into ONE block — delta-only by discipline (corrections +
# additions, never a copy of the base).
OVERRIDE_START = "<!-- reconciler:soul-override:start -->"
OVERRIDE_END = "<!-- reconciler:soul-override:end -->"

# Anti-nesting guard (D53): an override must never (re)inject a managed block — strip
# any reconciler markers from override content so there is no "override of an override".
_ALL_MARKERS = (
    (SOUL_START, SOUL_END), (GUARD_START, GUARD_END), (OVERRIDE_START, OVERRIDE_END),
)


def _strip_reconciler_markers(text: str) -> str:
    for start, end in _ALL_MARKERS:
        while start in text and end in text:
            text = text.split(start)[0] + text.split(end, 1)[1]
    return text.strip()


def load_soul_override(overrides_dir: Path) -> str:
    """Consolidated, precedence-labelled override text from the DATA-plane files.

    Reads the operator override first (control-plane authority), then the
    owner/agent override; strips any reconciler markers (anti-nesting guard) and
    returns one combined string, '' when neither file has content.
    """
    parts: list[tuple[str, str]] = []
    for fname, label in (
        ("soul-override.operator.md", "Operator"),
        ("soul-override.md", "Owner"),
    ):
        p = overrides_dir / fname
        if p.exists():
            body = _strip_reconciler_markers(p.read_text())
            if body:
                parts.append((label, body))
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0][1]
    return "\n\n".join(f"### {label} override\n{body}" for label, body in parts)


def render_soul_override_block(text: str) -> str:
    body = (text or "").strip()
    if not body:
        return ""  # no override → no block (upsert removes any stale one)
    return (
        f"{OVERRIDE_START}\n"
        "## Owner customizations (reconciler-managed — edit the override file, not here)\n"
        "These take precedence over the base identity above where they conflict.\n"
        f"{body}\n{OVERRIDE_END}"
    )


def upsert_soul_override(soul_text: str, text: str) -> str:
    """Idempotent upsert of the soul-override block; removes it when text is empty."""
    block = render_soul_override_block(text)
    if OVERRIDE_START in soul_text and OVERRIDE_END in soul_text:
        pre = soul_text.split(OVERRIDE_START)[0]
        post = soul_text.split(OVERRIDE_END, 1)[1]
        if not block:  # override cleared → drop the block, collapse the gap
            return (pre.rstrip("\n") + "\n" + post.lstrip("\n")).rstrip("\n") + "\n"
        return pre + block + post
    if not block:
        return soul_text
    sep = "" if soul_text.endswith("\n") else "\n"
    return soul_text + f"{sep}\n{block}\n"


# --------------------------------------------------------------------------- #
# apply layer (ruamel — comment/order preserving, quoted string keys)         #
# --------------------------------------------------------------------------- #
def apply_config(config_path: Path, desired: dict, *,
                 platform: str = "telegram", set_curator_guard: bool = False) -> Path:
    """Write the desired channel_prompts into ``config.yaml`` and return backup path."""
    from ruamel.yaml import YAML
    from ruamel.yaml.scalarstring import DoubleQuotedScalarString as DQ

    y = YAML()
    y.preserve_quotes = True
    y.width = 4096  # never wrap long prompt strings
    data = y.load(config_path.read_text())

    section = data.get(platform)
    if section is None:
        raise SystemExit(f"no '{platform}:' section in {config_path} — aborting, no change")

    # quoted string keys — the single easiest way to ship a silently-broken config
    section["channel_prompts"] = {DQ(str(k)): v for k, v in desired.items()}

    if set_curator_guard:
        cur = data.get("curator")
        if isinstance(cur, dict):
            cur["prune_builtins"] = False
        else:
            data["curator"] = {"prune_builtins": False}

    ts = os.environ.get("HH_FAKE_TS")  # tests can pin the timestamp
    if not ts:
        ts = time.strftime("%Y%m%d_%H%M%S", time.localtime())
    backup = config_path.with_name(config_path.name + f".bak.reconciler_{ts}")
    backup.write_text(config_path.read_text())
    with config_path.open("w") as fh:
        y.dump(data, fh)

    # validate the round-trip with a plain loader: keys MUST be strings
    reloaded = yaml.safe_load(config_path.read_text())
    cp = (reloaded.get(platform) or {}).get("channel_prompts") or {}
    bad = [k for k in cp if not isinstance(k, str)]
    if bad:
        config_path.write_text(backup.read_text())  # roll back
        raise SystemExit(f"validation failed: non-string keys {bad}; rolled back from {backup}")
    return backup


def restart_and_verify(log_path: Path | None = None, *, timeout: int = 60) -> bool:
    """Restart the gateway and confirm a *fresh* polling marker (best-effort).

    Returns True if a new 'Connected to Telegram (polling mode)' marker appears.
    Tries the live box's USER unit first (D33 live-box finding).
    """
    log_path = log_path or (_hermes_home() / "logs" / "gateway.log")
    marker = "Connected to Telegram (polling mode)"

    def count() -> int:
        try:
            return log_path.read_text(errors="ignore").count(marker)
        except FileNotFoundError:
            return 0

    before = count()
    env = {**os.environ, "XDG_RUNTIME_DIR": f"/run/user/{os.getuid()}"}
    for cmd in (["systemctl", "--user", "restart", "hermes-gateway"],
                ["systemctl", "restart", "hermes-gateway"]):
        try:
            subprocess.run(cmd, check=True, env=env, capture_output=True, timeout=30)
            break
        except Exception:
            continue
    else:
        print("WARN: could not restart gateway via systemctl", file=sys.stderr)
        return False

    deadline = time.time() + timeout
    while time.time() < deadline:
        if count() > before:
            return True
        time.sleep(2)
    return False


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #
def _current_prompts(config_path: Path, platform: str) -> dict:
    if not config_path.exists():
        return {}
    data = yaml.safe_load(config_path.read_text()) or {}
    return ((data.get(platform) or {}).get("channel_prompts") or {})


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="HermesHost routing index-reconciler")
    ap.add_argument("--skills-root", default=str(default_skills_root()))
    ap.add_argument("--config", default=str(default_config()))
    ap.add_argument("--intents", default=str(default_intents()),
                    help="owner per-group intents (D57 talent routing overrides)")
    ap.add_argument("--soul", default=str(default_soul()))
    ap.add_argument("--overrides-dir", default=str(default_overrides_dir()))
    ap.add_argument("--platform", default="telegram")
    ap.add_argument("--apply", action="store_true", help="write changes (backup first)")
    ap.add_argument("--restart", action="store_true", help="restart + verify gateway after apply")
    ap.add_argument("--set-curator-guard", action="store_true",
                    help="set curator.prune_builtins:false (only needed if baking)")
    ap.add_argument("--no-soul", action="store_true", help="skip SOUL block management")
    # Accepted-but-ignored (D57): name→channel_directory resolution is gone — groups
    # route via the focus-hint plugin + native index, bind by chat-id only.
    ap.add_argument("--channels", default=str(default_channels()), help=argparse.SUPPRESS)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    skills_root = Path(args.skills_root)
    config_path = Path(args.config)

    decls = load_declarations(skills_root)
    overrides = load_talent_overrides(Path(args.intents))
    desired, unresolved = compute_desired(decls, overrides)
    current = _current_prompts(config_path, args.platform)
    plan = diff(current, desired)

    report = {
        "bots": [d["bot"] for d in decls],
        "overrides": overrides,
        "unresolved": [u["bot"] for u in unresolved],
        "plan": {k: list(plan[k].keys()) for k in plan},
        "changes": has_changes(plan),
        "applied": False,
    }

    if not args.json:
        print(f"bots declaring routing: {report['bots'] or '(none)'}")
        if overrides:
            print(f"owner talent overrides: {overrides}")
        if unresolved:
            print(f"⚠️  unresolved overrides (slug has no Talent): {report['unresolved']}")
        for action in ("add", "update", "remove", "keep"):
            for cid in plan[action]:
                print(f"  {action.upper():6} {cid}")
        if not has_changes(plan):
            print("no channel_prompt changes.")

    if args.apply:
        cp_changed = has_changes(plan)
        if cp_changed:
            backup = apply_config(config_path, desired, platform=args.platform,
                                  set_curator_guard=args.set_curator_guard)
            report["backup"] = str(backup)
        # Manage the SOUL blocks on EVERY apply (idempotent): the static group safety
        # boundary (D36 A+) and the per-tenant override inlined from the DATA-plane
        # files (D53), and CLEAN UP a stale pre-D57 dm-hints block. DM routing is native
        # now (no dm-hints written). Write only when the text actually changes.
        soul_changed = False
        override_applied = False
        if not args.no_soul and Path(args.soul).exists():
            soul = Path(args.soul)
            current_soul = soul.read_text()
            override_text = load_soul_override(Path(args.overrides_dir))
            override_applied = bool(override_text)
            updated = upsert_soul_override(
                upsert_group_guard(remove_soul_hints(current_soul)), override_text
            )
            if updated != current_soul:
                soul.write_text(updated)
                soul_changed = True
        report["applied"] = bool(cp_changed or soul_changed)
        report["soul_updated"] = soul_changed
        report["soul_override_applied"] = override_applied
        if args.restart and (cp_changed or soul_changed):
            ok = restart_and_verify()
            report["restart_ok"] = ok
            if not args.json:
                print("gateway: fresh polling marker " + ("confirmed ✓" if ok else "NOT seen ✗"))
        if not args.json:
            if cp_changed:
                print(f"applied. backup: {report['backup']}")
            elif soul_changed:
                print("applied SOUL blocks (no channel_prompt changes).")

    if args.json:
        print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
