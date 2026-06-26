#!/usr/bin/env python3
"""provision_cron — the deterministic cron *planner* for OtenyFlatBellyTalent.

Hermes registers cron jobs through its ``cronjob`` tool (which updates both
``~/.hermes/cron/jobs.json`` and the in-process scheduler), so this script does NOT
write jobs itself — it computes the tz-correct schedule and emits the exact job specs
the first-run section feeds to the ``cronjob`` tool, **list-first** (only the jobs not
already present). Keeping the schedule math in a script (not the LLM) is the
deterministic backbone; the LLM only executes the registration.

Reads ``~/.hermes/data/oteny-flatbelly-talent/profile.yaml`` for ``timezone`` and ``reminders``. Prints a
human plan, or ``--json`` with ``to_create`` (full specs) + ``existing``.

DST caveat: Hermes cron expressions are interpreted in UTC, so the computed UTC hour
is correct for the *current* offset. Re-run this planner after a DST change (or use
Hermes-native tz scheduling if the box exposes it) to keep the wall-clock fixed.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None
try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

DEFAULT_PROFILE = os.path.expanduser("~/.hermes/data/oteny-flatbelly-talent/profile.yaml")
DEFAULT_JOBS = os.path.expanduser("~/.hermes/cron/jobs.json")
DEFAULT_CONFIG = os.path.expanduser("~/.hermes/config.yaml")

# Cron jobs MUST pin their model + provider. Hermes' cron scheduler resolves an
# un-pinned job's model from config.yaml's `model.default` (NOT `model.model`, the
# key the interactive path reads), so a job created without a model sends an empty
# model and the router 400s ("Invalid model name passed in model="). We read the
# tenant's real model/provider from config.yaml and emit them on every spec; these
# constants are only a last-resort fallback if config.yaml can't be read.
#
# The fallback model is the `assistant` PERSONA ALIAS, never the raw OpenRouter slug
# (`~google/gemini-flash-latest`). A tenant can only request the router's persona
# aliases (assistant/builder/researcher, D55) — the metering proxy/router rejects
# anything else with HTTP 400 `unknown model '~google/gemini-flash-latest'`, which is
# exactly how cron jobs fail when pinned to the raw slug.
_FALLBACK_MODEL = "assistant"
_FALLBACK_PROVIDER = "router"


def read_model_provider(config_path: str = DEFAULT_CONFIG) -> tuple[str, str]:
    """(model, provider) the cron jobs must pin — from config.yaml's `model:` block.

    Falls back to the known router defaults if config.yaml is absent/unreadable so a
    spec always carries a working model+provider (an un-pinned cron job is the bug).
    """
    if yaml is None:
        return _FALLBACK_MODEL, _FALLBACK_PROVIDER
    try:
        cfg = yaml.safe_load(Path(config_path).read_text()) or {}
        mc = cfg.get("model", {})
        if isinstance(mc, dict):
            return (mc.get("model") or _FALLBACK_MODEL,
                    mc.get("provider") or _FALLBACK_PROVIDER)
    except Exception:
        pass
    return _FALLBACK_MODEL, _FALLBACK_PROVIDER


def utc_cron(local_hh: int, local_mm: int, tz: str, dow: int | None = None,
             ref: datetime | None = None) -> str:
    """Return a 5-field cron expr (UTC) for a wall-clock time in ``tz``.

    ``dow``: cron day-of-week (0=Sun) for weekly jobs; None for daily.
    ``ref``: reference date (defaults to today) — DST offset is taken from it.
    """
    if ZoneInfo is None:
        raise RuntimeError("zoneinfo unavailable")
    base = (ref or datetime.now()).replace(hour=local_hh, minute=local_mm,
                                           second=0, microsecond=0)
    local = base.replace(tzinfo=ZoneInfo(tz))
    u = local.astimezone(ZoneInfo("UTC"))
    if dow is None:
        return f"{u.minute} {u.hour} * * *"
    # shift the cron weekday if the UTC conversion crossed midnight
    shift = (u.date() - base.date()).days
    udow = (dow + shift) % 7
    return f"{u.minute} {u.hour} * * {udow}"


def _hhmm(s, default):
    try:
        hh, mm = str(s).split(":")
        return int(hh), int(mm)
    except Exception:
        return default


def build_specs(profile: dict, ref: datetime | None = None,
                model: str | None = None, provider: str | None = None) -> list[dict]:
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
    return [
        {
            "name": "OtenyFlatBellyTalent daily morning log",
            "schedule": utc_cron(m_hh, m_mm, tz, ref=ref),
            "local": f"{m_hh:02d}:{m_mm:02d} {tz} daily",
            "skills": ["food-tracker", "flatbelly-coach-voice"],
            "model": model,
            "provider": provider,
            "prompt": ("Morning log reminder. Ask the tenant (in their language) for "
                       "their morning weight and what they have eaten/plan to eat; do "
                       "NOT pre-fill. Load food-tracker first."),
        },
        {
            "name": "OtenyFlatBellyTalent daily evening log",
            "schedule": utc_cron(e_hh, e_mm, tz, ref=ref),
            "local": f"{e_hh:02d}:{e_mm:02d} {tz} daily",
            "skills": ["food-tracker", "flatbelly-coach-voice"],
            "model": model,
            "provider": provider,
            "prompt": ("Evening log reminder. Ask for the full day's food + any "
                       "sleep/steps/workout; then write the rows and give a grounded "
                       "day total with leucine compliance. Load food-tracker first."),
        },
        {
            "name": "OtenyFlatBellyTalent weekly dashboard",
            "schedule": utc_cron(w_hh, w_mm, tz, dow=0, ref=ref),
            "local": f"Sun {w_hh:02d}:{w_mm:02d} {tz} weekly",
            "skills": ["weight-progress-dashboard", "food-tracker"],
            "enabled_toolsets": ["terminal", "file"],
            "model": model,
            "provider": provider,
            "prompt": ("Run weight-progress-dashboard/scripts/generate.py, then write a "
                       "4–6 line Telegram caption grounded in a fresh DB read (no "
                       "vibe-served facts) and deliver the PNG via MEDIA:<path>."),
        },
    ]


def existing_job_names(jobs_path: str) -> set[str]:
    p = Path(jobs_path)
    if not p.exists():
        return set()
    data = json.loads(p.read_text())
    return {j.get("name") for j in data.get("jobs", [])}


def plan(profile: dict, jobs_path: str, ref: datetime | None = None,
         model: str | None = None, provider: str | None = None) -> dict:
    specs = build_specs(profile, ref=ref, model=model, provider=provider)
    have = existing_job_names(jobs_path)
    to_create = [s for s in specs if s["name"] not in have]
    return {"to_create": to_create,
            "existing": [s["name"] for s in specs if s["name"] in have]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="OtenyFlatBellyTalent cron planner (list-first)")
    ap.add_argument("--profile", default=DEFAULT_PROFILE)
    ap.add_argument("--jobs", default=DEFAULT_JOBS)
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    profile = {}
    if yaml and Path(args.profile).exists():
        profile = yaml.safe_load(Path(args.profile).read_text()) or {}

    model, provider = read_model_provider(args.config)
    p = plan(profile, args.jobs, model=model, provider=provider)
    if args.json:
        print(json.dumps(p, indent=2))
        return 0
    if not p["to_create"]:
        print("all OtenyFlatBellyTalent crons already registered:", p["existing"])
        return 0
    print(f"Create these jobs via the `cronjob` tool (list-first — these are absent). "
          f"Pin model='{model}' provider='{provider}' on EACH (un-pinned cron 400s):")
    for s in p["to_create"]:
        print(f"  • {s['name']}  [{s['local']}]  cron(UTC)='{s['schedule']}'  "
              f"skills={s['skills']}  model={s['model']}  provider={s['provider']}")
    if p["existing"]:
        print("already present:", p["existing"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
