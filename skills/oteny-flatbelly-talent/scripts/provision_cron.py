#!/usr/bin/env python3
"""provision_cron — the deterministic cron *planner* for OtenyFlatBellyTalent.

Hermes registers cron jobs through its ``cronjob`` tool (which updates both
``~/.hermes/cron/jobs.json`` and the in-process scheduler), so this script does NOT
write jobs itself — it computes the tz-correct schedule and emits the exact job specs
the first-run section feeds to the ``cronjob`` tool, **list-first** (only the jobs not
already present). Keeping the schedule math in a script (not the LLM) is the
deterministic backbone; the LLM only executes the registration.

Reads ``~/.hermes/data/oteny-flatbelly-talent/profile.yaml`` for ``timezone`` and ``reminders``, and the
Talent's own ``agent-profile.yaml`` ``crons:`` block for the per-job cost policy (model +
max_turns). Prints a human plan, or ``--json`` with ``to_create`` (full specs) + ``existing``.

Timezone: Hermes' scheduler evaluates a cron expression in the tenant's CONFIGURED
timezone (config.yaml ``timezone:`` → ``hermes_time.now()`` → the croniter base), NOT
UTC. So the schedule is the local wall-clock time verbatim — no conversion. The prior
UTC conversion fired reminders off by the tenant's UTC offset (2 h early in CEST summer);
writing local wall-clock is DST-invariant (08:00 local stays 08:00 local year-round).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path


def _belt():
    """The shared readiness belt (``selfcheck.read_yaml``), loaded from the sibling
    ``selfcheck.py`` by path — the ONE stdlib-first YAML reader every readiness script
    shares, so a cold tenant whose system python3 lacks PyYAML still reads profile.yaml +
    config.yaml (correct reminder times + model/provider) instead of silently using
    defaults. (agent-profile.yaml's block scalars stay parseable only with PyYAML present;
    the belt degrades that read to an empty policy on a cold box — same as before.)"""
    import importlib.util

    p = Path(__file__).resolve().parent / "selfcheck.py"
    spec = importlib.util.spec_from_file_location("oteny_readiness_belt", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


DEFAULT_PROFILE = os.path.expanduser("~/.hermes/data/oteny-flatbelly-talent/profile.yaml")
DEFAULT_JOBS = os.path.expanduser("~/.hermes/cron/jobs.json")
DEFAULT_CONFIG = os.path.expanduser("~/.hermes/config.yaml")
# The Talent's own manifest (bundle root, beside this scripts/ dir) — the single source
# of the per-job cron cost policy the lint enforces and this planner emits from.
DEFAULT_AGENT_PROFILE = Path(__file__).resolve().parent.parent / "agent-profile.yaml"

# Cron jobs MUST pin their model + provider. Hermes' cron scheduler resolves an
# un-pinned job's model from config.yaml's `model.default` (NOT `model.model`, the
# key the interactive path reads), so a job created without a model sends an empty
# model and the router 400s ("Invalid model name passed in model="). We read the
# tenant's real model/provider from config.yaml and emit them on every spec; these
# constants are only a last-resort fallback if config.yaml can't be read.
#
# The fallback model is the `assistant` PERSONA ALIAS, never the raw OpenRouter slug
# (`~google/gemini-flash-latest`). A tenant can only request the router's persona
# aliases (assistant/builder/researcher) — the metering proxy/router rejects
# anything else with HTTP 400 `unknown model '~google/gemini-flash-latest'`, which is
# exactly how cron jobs fail when pinned to the raw slug.
_FALLBACK_MODEL = "assistant"
_FALLBACK_PROVIDER = "router"


def read_model_provider(config_path: str = DEFAULT_CONFIG) -> tuple[str, str]:
    """(model, provider) the cron jobs must pin — from config.yaml's `model:` block.

    Falls back to the known router defaults if config.yaml is absent/unreadable so a
    spec always carries a working model+provider (an un-pinned cron job is the bug).
    """
    belt = _belt()
    data = belt.read_yaml(Path(config_path))
    cfg = data if isinstance(data, dict) else {}
    mc = cfg.get("model", {})
    if isinstance(mc, dict):
        return (mc.get("model") or _FALLBACK_MODEL,
                mc.get("provider") or _FALLBACK_PROVIDER)
    return _FALLBACK_MODEL, _FALLBACK_PROVIDER


def local_cron(local_hh: int, local_mm: int, dow: int | None = None) -> str:
    """Return a 5-field cron expr in the tenant's LOCAL wall-clock.

    Hermes' scheduler evaluates the expression in the tenant's configured timezone
    (config.yaml ``timezone:`` → ``hermes_time.now()`` → the croniter base), NOT UTC, so
    the schedule IS the local time verbatim — no conversion. The prior UTC conversion
    fired reminders off by the tenant's UTC offset; local wall-clock is DST-invariant.

    ``dow``: cron day-of-week (0=Sun) for weekly jobs; None for daily.
    """
    if dow is None:
        return f"{local_mm} {local_hh} * * *"
    return f"{local_mm} {local_hh} * * {dow}"


def read_cron_policy(profile_path=DEFAULT_AGENT_PROFILE) -> dict:
    """Per-job cron cost policy from agent-profile.yaml's ``crons:`` block, keyed by job
    name: ``{name: {model, max_turns, expected_cost, ...}}`` ({} if absent/unreadable).

    This is the SAME source the build-time lint enforces, so the emitted model/max_turns
    can never drift from the declared+linted policy (talent-model-steering W4/W5).
    """
    belt = _belt()
    parsed = belt.read_yaml(Path(profile_path))
    data = parsed if isinstance(parsed, dict) else {}
    out = {}
    for c in (data.get("crons") or []):
        if isinstance(c, dict) and c.get("name"):
            out[c["name"]] = c
    return out


def _hhmm(s, default):
    try:
        hh, mm = str(s).split(":")
        return int(hh), int(mm)
    except Exception:
        return default


def build_specs(profile: dict, ref: datetime | None = None,
                model: str | None = None, provider: str | None = None,
                cron_policy: dict | None = None,
                emit_max_turns: bool = False) -> list[dict]:
    """The cron job specs. Per-job model + max_turns come from the Talent's ``crons:``
    policy (agent-profile.yaml) — the reminders are cheap ``lite`` pings regardless of the
    owner's chat persona (W3/W5). ``model``/``provider`` (from config.yaml) are the fallback
    for any job the policy doesn't pin. ``max_turns`` is EMITTED only when ``emit_max_turns``
    (a deployed Hermes that honors a per-cron cap, W6) — otherwise it stays declared+linted.
    """
    tz = profile.get("timezone") or "Europe/Amsterdam"
    rem = profile.get("reminders") or {}
    m_hh, m_mm = _hhmm(rem.get("morning", "08:00"), (8, 0))
    e_hh, e_mm = _hhmm(rem.get("evening", "20:00"), (20, 0))
    # weekly dashboard default Sunday 12:00 local
    w_hh, w_mm = _hhmm(str(rem.get("weekly_dashboard", "12:00")).split()[-1], (12, 0))
    # Every job pins model+provider — an un-pinned cron job sends an empty model
    # to the router and 400s (the scheduler reads model.default, not model.model).
    model = model or _FALLBACK_MODEL
    provider = provider or _FALLBACK_PROVIDER
    if cron_policy is None:
        cron_policy = read_cron_policy()

    def _spec(name, schedule, local, skills, prompt, **extra):
        pol = cron_policy.get(name, {})
        spec = {
            "name": name,
            "schedule": schedule,
            "local": local,
            "skills": skills,
            # W3/W5: the Talent's declared per-job persona (cheap `lite`) wins over the
            # owner's chat model; falls back to the config.yaml model if unpinned.
            "model": pol.get("model") or model,
            "provider": provider,
            "prompt": prompt,
        }
        spec.update(extra)
        # Per-job tool surface — the policy (agent-profile.yaml `crons:`) is the single
        # source. EVERY job must pin it: an omitted list falls back to the tenant's
        # platform_toolsets.cron cap, which is how the 2026-07-02 runaway happened (no
        # terminal + a skill demanding script execution = an impossible task the model
        # flailed on for 90 iterations). A reminder pins `[no_mcp]` = ZERO tools (a
        # literal [] is falsy upstream and would fall back; `no_mcp` passes the
        # truthiness gate and the MCP-merge strips it, leaving a true empty allowlist).
        ets = pol.get("enabled_toolsets")
        if isinstance(ets, list) and ets:
            spec["enabled_toolsets"] = [str(t) for t in ets]
        # W6: emit the per-cron cap only where a deployed Hermes honors it (no released
        # version does yet), so an older gateway never gets an unknown `max_turns` field.
        mt = pol.get("max_turns")
        if emit_max_turns and isinstance(mt, int) and mt > 0:
            spec["max_turns"] = mt
        return spec

    # The daily reminders are the ORIGINAL rich "day so far" status summaries
    # (v1.2.0 restore): the cron loads food-tracker, runs preflight + a fresh DB
    # read, opens with the grounded summary, and asks only for what's missing —
    # per the skill's "Daily reminder role". They were temporarily thinned to a
    # no-tool nudge (v1.1.x) ONLY because of since-fixed environment bugs (a
    # platform-level cron toolset cap, since reverted host-side; a file-search
    # hidden-dir blindness, fixed upstream); the cost steering stays: model
    # pinned `lite`, a lean per-job
    # toolset, and a declared max_turns from the measured healthy profile.
    return [
        _spec(
            "OtenyFlatBellyTalent daily morning log",
            local_cron(m_hh, m_mm),
            f"{m_hh:02d}:{m_mm:02d} {tz} daily",
            ["food-tracker", "flatbelly-coach-voice"],
            ("Morning log reminder. Ask the tenant (in their language) for their "
             "morning weight and what they have eaten/plan to eat; do NOT pre-fill. "
             "Load food-tracker first."),
        ),
        _spec(
            "OtenyFlatBellyTalent daily evening log",
            local_cron(e_hh, e_mm),
            f"{e_hh:02d}:{e_mm:02d} {tz} daily",
            ["food-tracker", "flatbelly-coach-voice"],
            ("Evening log reminder. Ask for the full day's food + any "
             "sleep/steps/workout; then write the rows and give a grounded day "
             "total with leucine compliance. Load food-tracker first."),
        ),
        _spec(
            "OtenyFlatBellyTalent weekly dashboard",
            local_cron(w_hh, w_mm, dow=0),
            f"Sun {w_hh:02d}:{w_mm:02d} {tz} weekly",
            ["weight-progress-dashboard", "food-tracker"],
            ("Run `talent-run oteny-flatbelly-talent "
             "weight-progress-dashboard/scripts/generate.py`, then write a "
             "4–6 line Telegram caption grounded in a fresh DB read (no "
             "vibe-served facts) and deliver the PNG via MEDIA:<path>."),
            enabled_toolsets=["terminal", "file"],
        ),
    ]


def existing_job_names(jobs_path: str) -> set[str]:
    p = Path(jobs_path)
    if not p.exists():
        return set()
    data = json.loads(p.read_text())
    return {j.get("name") for j in data.get("jobs", [])}


def plan(profile: dict, jobs_path: str, ref: datetime | None = None,
         model: str | None = None, provider: str | None = None,
         cron_policy: dict | None = None, emit_max_turns: bool = False) -> dict:
    specs = build_specs(profile, ref=ref, model=model, provider=provider,
                        cron_policy=cron_policy, emit_max_turns=emit_max_turns)
    have = existing_job_names(jobs_path)
    to_create = [s for s in specs if s["name"] not in have]
    return {"to_create": to_create,
            "existing": [s["name"] for s in specs if s["name"] in have]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="OtenyFlatBellyTalent cron planner (list-first)")
    ap.add_argument("--profile", default=DEFAULT_PROFILE)
    ap.add_argument("--jobs", default=DEFAULT_JOBS)
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    ap.add_argument("--agent-profile", default=str(DEFAULT_AGENT_PROFILE))
    # W6: emit the per-cron max_turns cap only where the deployed Hermes honors it (no
    # released version does yet). Off by default; the control plane flips it once a
    # pinned Hermes supports a per-job cap so an older gateway never gets an unknown field.
    ap.add_argument("--emit-max-turns", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    data = _belt().read_yaml(Path(args.profile))
    profile = data if isinstance(data, dict) else {}

    model, provider = read_model_provider(args.config)
    cron_policy = read_cron_policy(args.agent_profile)
    p = plan(profile, args.jobs, model=model, provider=provider,
             cron_policy=cron_policy, emit_max_turns=args.emit_max_turns)
    if args.json:
        print(json.dumps(p, indent=2))
        return 0
    if not p["to_create"]:
        print("all OtenyFlatBellyTalent crons already registered:", p["existing"])
        return 0
    print("Create these jobs via the `cronjob` tool (list-first — these are absent). "
          "Pin the model+provider shown on EACH (un-pinned cron 400s); the cron string is "
          "the tenant's LOCAL wall-clock (the scheduler reads config.yaml timezone):")
    for s in p["to_create"]:
        mt = f"  max_turns={s['max_turns']}" if "max_turns" in s else ""
        print(f"  • {s['name']}  [{s['local']}]  cron(local)='{s['schedule']}'  "
              f"skills={s['skills']}  model={s['model']}  provider={s['provider']}{mt}")
    if p["existing"]:
        print("already present:", p["existing"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
