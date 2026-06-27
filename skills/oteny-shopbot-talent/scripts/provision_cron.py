#!/usr/bin/env python3
"""provision_cron — the deterministic cron *planner* for OtenyShopBotTalent.

Hermes registers cron jobs through its ``cronjob`` tool (which updates both
``~/.hermes/cron/jobs.json`` and the in-process scheduler), so this script does NOT
write jobs itself — it computes the tz-correct schedule and emits the exact job specs
first-run feeds to the ``cronjob`` tool, **list-first** (only the jobs not already
present). Keeping the schedule math in a script (not the LLM) is the deterministic
backbone; the LLM only executes the registration.

The one job is OPT-IN: a weekly "what do we need this week?" nudge, registered only when
the owner sets ``reminders.weekly_shop`` (empty/absent -> nothing to create).

Reads ``~/.hermes/data/oteny-shopbot-talent/profile.yaml`` for ``timezone`` +
``reminders.weekly_shop`` ("Sat 09:00"). Prints a human plan, or ``--json`` with
``to_create`` (full specs) + ``existing``.

DST caveat: Hermes cron expressions are interpreted in UTC, so the computed UTC hour is
correct for the *current* offset. Re-run this planner after a DST change to keep the
wall-clock fixed.
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

DEFAULT_PROFILE = os.path.expanduser("~/.hermes/data/oteny-shopbot-talent/profile.yaml")
DEFAULT_JOBS = os.path.expanduser("~/.hermes/cron/jobs.json")
DEFAULT_CONFIG = os.path.expanduser("~/.hermes/config.yaml")

# Cron jobs MUST pin their model + provider. Hermes' cron scheduler resolves an un-pinned
# job's model from config.yaml's `model.default` (NOT `model.model`, the interactive
# path), so a job created without a model sends an empty model and the router 400s. We
# read the tenant's real model/provider from config.yaml and emit them on every spec.
# The fallback is the `assistant` PERSONA ALIAS, never the raw OpenRouter slug (the
# router rejects a raw slug with HTTP 400 `unknown model`).
_FALLBACK_MODEL = "assistant"
_FALLBACK_PROVIDER = "router"
# cron day-of-week (0=Sun) for the weekly nudge keywords.
_DOW = {"sun": 0, "mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6}


def read_model_provider(config_path: str = DEFAULT_CONFIG) -> tuple[str, str]:
    """(model, provider) the cron job must pin — from config.yaml's `model:` block."""
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


def utc_cron(local_hh: int, local_mm: int, tz: str, dow: int,
             ref: datetime | None = None) -> str:
    """5-field cron expr (UTC) for a weekly wall-clock time in ``tz`` (dow: 0=Sun)."""
    if ZoneInfo is None:
        raise RuntimeError("zoneinfo unavailable")
    base = (ref or datetime.now()).replace(hour=local_hh, minute=local_mm,
                                           second=0, microsecond=0)
    local = base.replace(tzinfo=ZoneInfo(tz))
    u = local.astimezone(ZoneInfo("UTC"))
    shift = (u.date() - base.date()).days
    return f"{u.minute} {u.hour} * * {(dow + shift) % 7}"


def _parse_weekly(value) -> tuple[int, int, int] | None:
    """'Sat 09:00' -> (dow, hh, mm); None when unset/blank/unparseable (nothing to do)."""
    if not value:
        return None
    parts = str(value).split()
    if len(parts) != 2 or parts[0][:3].lower() not in _DOW:
        return None
    dow = _DOW[parts[0][:3].lower()]
    try:
        hh, mm = parts[1].split(":")
        return dow, int(hh), int(mm)
    except Exception:
        return None


def build_specs(profile: dict, ref: datetime | None = None,
                model: str | None = None, provider: str | None = None) -> list[dict]:
    rem = profile.get("reminders") or {}
    parsed = _parse_weekly(rem.get("weekly_shop"))
    if not parsed:
        return []
    dow, hh, mm = parsed
    tz = profile.get("timezone") or "Europe/Amsterdam"
    model = model or _FALLBACK_MODEL
    provider = provider or _FALLBACK_PROVIDER
    days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    return [{
        "name": "OtenyShopBotTalent weekly shop nudge",
        "schedule": utc_cron(hh, mm, tz, dow, ref=ref),
        "local": f"{days[dow]} {hh:02d}:{mm:02d} {tz} weekly",
        "skills": ["oteny-shopbot-talent"],
        "model": model,
        "provider": provider,
        "prompt": ("Weekly shop nudge. Load oteny-shopbot-talent first and run "
                   "list_view.py to read the active list grounded in the database. If it "
                   "is empty, ask the household (in their language) what they need this "
                   "week. If it has items, post the aisle-ordered list so everyone can "
                   "plan the shop. Do NOT invent items."),
    }]


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
    ap = argparse.ArgumentParser(description="OtenyShopBotTalent cron planner (list-first)")
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
        if not build_specs(profile, model=model, provider=provider):
            print("no weekly nudge configured (set reminders.weekly_shop to enable)")
        else:
            print("weekly nudge already registered:", p["existing"])
        return 0
    print(f"Create via the `cronjob` tool (list-first). Pin model='{model}' "
          f"provider='{provider}' on EACH (un-pinned cron 400s):")
    for s in p["to_create"]:
        print(f"  • {s['name']}  [{s['local']}]  cron(UTC)='{s['schedule']}'  "
              f"skills={s['skills']}  model={s['model']}  provider={s['provider']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
