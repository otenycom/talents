#!/usr/bin/env python3
"""provision_cron — the deterministic, TRIP-SCOPED cron planner for OtenyTravelTalent.

Unlike a daily-habit Talent, a travel bot has NOTHING to schedule until a trip exists,
and an idle daily cron on an always-on VM still burns LLM tokens on a *free* talent. So
this planner is called by the new-trip / add-flight checklists (NOT at first-run) and
emits **per-trip** jobs bounded to the trip window — every one self-expires (a bounded
``repeat`` auto-deletes the job; a ``once`` fires and is gone), so **no crons exist when
the tenant has no active trip**.

The recurring jobs are emitted as **day-of-month-bounded cron expressions** (one per
calendar month the window touches), NOT an ``every Nh`` interval. That is the load-bearing
distinction: an interval fires from *creation* time, so a trip booked weeks out used to
tick every 6 h from the booking day — burning tokens far from the trip. A windowed cron
expr (``0 */6 18-31 7 *``) only matches inside its days, so a far-future trip costs zero
cron tokens until its window opens.

It plans four job kinds:
  1. monitor   — watch booked flights/trains across (start − 2d)…(end + 1d), every few hours
  2. briefing  — a daily trip briefing on each trip day
  3. review    — a one-shot post-trip review the day after the trip ends
  4. EU261     — a one-shot delay-claim check the day after each monitored flight arrives

This script does NOT write jobs itself — Hermes registers them through its ``cronjob``
tool (which updates ``~/.hermes/cron/jobs.json`` + the in-process scheduler). It computes
the schedule + the exact specs the checklist feeds to the tool, **list-first** (only the
jobs not already present, keyed by name).

TIMEZONE: Hermes interprets cron expressions AND naive ISO timestamps in the box's
configured timezone (the owner's home tz — see render_config_yaml / oteny-set-timezone),
so the schedule strings here carry the owner's LOCAL wall-clock — no UTC conversion.

Usage:
    python3 provision_cron.py --json                 # plan for the active/soonest trip
    python3 provision_cron.py --trip 3 --json        # plan for a specific trip id
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

DEFAULT_DB = os.path.expanduser("~/.hermes/data/oteny-travel-talent/trips.db")
DEFAULT_PROFILE = os.path.expanduser("~/.hermes/data/oteny-travel-talent/profile.yaml")
DEFAULT_JOBS = os.path.expanduser("~/.hermes/cron/jobs.json")
DEFAULT_CONFIG = os.path.expanduser("~/.hermes/config.yaml")

# Cron jobs MUST pin model + provider. Hermes' cron scheduler resolves an un-pinned
# job's model from config.yaml's `model.default` (NOT `model.model`, the interactive
# key), so a job created without a model sends an empty model and the router 400s
# ("Invalid model name passed in model="). We read the tenant's real model/provider
# from config.yaml and emit them on every spec; these are only a last-resort fallback.
#
# The fallback is the `assistant` PERSONA ALIAS (D55), never the raw OpenRouter slug —
# the router/metering proxy 400s anything but an alias as `unknown model`.
_FALLBACK_MODEL = "assistant"
_FALLBACK_PROVIDER = "router"

# Tunables (quarantined numerics — the translator leaves them byte-identical).
MONITOR_EVERY_H = 6        # disruption check cadence within the window
MONITOR_MARGIN_DAYS = 2    # start watching this many days BEFORE departure
END_MARGIN_DAYS = 1        # keep watching this many days AFTER the trip ends (late arrivals + airline claims)
BRIEFING_HH, BRIEFING_MM = 7, 30   # daily briefing local time
REVIEW_HH = 10             # post-trip review local time (day after end_date)
CLAIM_HH = 12              # EU261 claim local time (day after each flight's arrival)


def read_model_provider(config_path: str = DEFAULT_CONFIG) -> tuple[str, str]:
    """(model, provider) every cron job must pin — from config.yaml's `model:` block.

    Falls back to the router defaults if config.yaml is absent/unreadable so a spec
    always carries a working model+provider (an un-pinned cron job is the bug)."""
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


def _pdate(s) -> date | None:
    try:
        return date.fromisoformat(str(s)[:10])
    except (ValueError, TypeError):
        return None


def _iso_local(d: date, hh: int, mm: int = 0) -> str:
    """A naive local ISO timestamp the `cronjob` tool parses as the box's local tz."""
    return f"{d.isoformat()}T{hh:02d}:{mm:02d}"


def _last_dom(d: date) -> int:
    """The last calendar day of d's month."""
    nxt = date(d.year + 1, 1, 1) if d.month == 12 else date(d.year, d.month + 1, 1)
    return (nxt - timedelta(days=1)).day


def _first_of_next_month(d: date) -> date:
    return date(d.year + 1, 1, 1) if d.month == 12 else date(d.year, d.month + 1, 1)


def _month_segments(d0: date, d1: date) -> list[tuple[int, int, int]]:
    """Split an inclusive [d0, d1] date window into per-calendar-month segments.

    Returns (start_day, end_day, month) tuples. A single-month window yields ONE
    segment (the common case is one clean cron expression); a window that crosses a
    month boundary yields one segment per month — every segment a day-of-month-bounded
    cron expression. This is the whole point: a cron expr keyed to specific days+month
    fires ONLY inside the window, whereas an `every Nh` interval fires from creation
    time — which is what made a far-future trip's monitor burn tokens for weeks (it
    ticked every 6 h from the day the trip was booked, well before the window)."""
    segs: list[tuple[int, int, int]] = []
    cur = d0
    while cur <= d1:
        last_day = d1.day if (cur.year, cur.month) == (d1.year, d1.month) else _last_dom(cur)
        segs.append((cur.day, last_day, cur.month))
        cur = _first_of_next_month(cur)
    return segs


def _windowed_specs(*, base_name: str, kind: str, minute: str, hour: str, per_day: int,
                    win_start: date, win_end: date, model: str, provider: str,
                    skills: list[str], toolsets: list[str], prompt: str) -> list[dict]:
    """A self-expiring cron-kind spec PER month-segment of the firing window
    [win_start, win_end]. Each fires only on its window days (never from creation) and
    auto-deletes once its bounded ``repeat`` count is reached. Multi-month windows get a
    `[MM]` name suffix so each segment is a distinct, list-first-dedupable job."""
    segs = _month_segments(win_start, win_end)
    multi = len(segs) > 1
    specs: list[dict] = []
    for (d1, d2, month) in segs:
        schedule = f"{minute} {hour} {d1}-{d2} {month} *"
        repeat = (d2 - d1 + 1) * per_day
        name = base_name if not multi else f"{base_name} [{month:02d}]"
        specs.append({
            "name": name, "schedule": schedule, "repeat": repeat, "kind": kind,
            "local": f"{hour}:{minute} on day {d1}-{d2}/{month:02d}",
            "skills": skills, "enabled_toolsets": toolsets,
            "model": model, "provider": provider, "prompt": prompt,
        })
    return specs


def build_trip_specs(trip: dict, *, model: str | None = None, provider: str | None = None,
                     ref: datetime | None = None) -> list[dict]:
    """The monitor + briefing + review specs for one trip (a dict with id, name,
    start_date, end_date). Window-bounded and self-expiring; returns [] if dateless."""
    model = model or _FALLBACK_MODEL
    provider = provider or _FALLBACK_PROVIDER
    ref = ref or datetime.now()
    start = _pdate(trip.get("start_date"))
    end = _pdate(trip.get("end_date")) or start
    if start is None:
        return []  # a dateless trip has no window to schedule against
    name = trip.get("name") or f"trip {trip.get('id')}"
    tag = f"{name} (#{trip.get('id')})"
    specs: list[dict] = []

    # --- 1. transport monitor (recurring, window-bounded, auto-deletes) ---
    # Window = (start − MONITOR_MARGIN_DAYS) … (end + END_MARGIN_DAYS): watch from a
    # couple of days before the first departure through the day after the trip ends, so
    # a same-day-late arrival or an airline-claim window is still caught. Emitted as a
    # day-of-month-bounded cron expr (one job per calendar month), so it NEVER fires
    # before the window — a far-future trip costs zero cron tokens until it's near.
    specs += _windowed_specs(
        base_name=f"OtenyTravelTalent monitor — {tag}", kind="monitor",
        minute="0", hour=f"*/{MONITOR_EVERY_H}", per_day=24 // MONITOR_EVERY_H,
        win_start=start - timedelta(days=MONITOR_MARGIN_DAYS),
        win_end=end + timedelta(days=END_MARGIN_DAYS),
        model=model, provider=provider,
        skills=["trip-planner", "travel-concierge-voice"],
        toolsets=["terminal", "web"],
        prompt=(
            "Disruption monitor. Load trip-planner; run "
            "scripts/monitor_transport.py --due to list monitored legs due a check. For "
            "each, call the `travel` tool for live status, then "
            "monitor_transport.py --update to record it. Only message the trip group/DM "
            "on a CHANGE (delay/gate/cancellation) and offer a reroute "
            "(references/disruption.md). Nothing changed or nothing due -> [SILENT]. "
            "Never invent a status."),
    )

    # --- 2. daily trip briefing (one per trip day, auto-deletes) ---
    # Window = the trip days only ([start, end]); a day-of-month-bounded cron expr per
    # month, so it fires on exactly the trip days and never before/after.
    specs += _windowed_specs(
        base_name=f"OtenyTravelTalent briefing — {tag}", kind="briefing",
        minute=f"{BRIEFING_MM}", hour=f"{BRIEFING_HH}", per_day=1,
        win_start=start, win_end=end,
        model=model, provider=provider,
        skills=["trip-planner", "travel-concierge-voice"],
        toolsets=["terminal", "web"],
        prompt=(
            "Daily trip briefing. Load trip-planner; run scripts/preflight.py. If today "
            "is OUTSIDE the trip window -> [SILENT]. Otherwise: today's schedule + the "
            "first departure's live leave-by (call `travel` to re-verify status) + "
            "weather + each member's still-open todos. Ground every fact in a DB read or "
            "tool result; never fabricate (references/checklists.md §BRIEFING)."),
    )

    # --- 3. post-trip review (one-shot, day after end_date) ---
    review_day = end + timedelta(days=1)
    specs.append({
        "name": f"OtenyTravelTalent review — {tag}",
        "schedule": _iso_local(review_day, REVIEW_HH), "repeat": 1, "kind": "review",
        "local": f"once {review_day} {REVIEW_HH:02d}:00",
        "skills": ["trip-planner", "trip-dashboard", "travel-concierge-voice"],
        "enabled_toolsets": ["terminal", "web"],
        "model": model, "provider": provider,
        "prompt": (
            "Post-trip review (Wilma 7-step, user-facing). Load trip-planner; follow "
            "references/disruption.md §POST-TRIP REVIEW: route/timing assessment, spend "
            "recap (scripts/settle_up.py), what went well / improvable, and surface any "
            "claimable flight delay. Read-only on the trip; facts only."),
    })
    return specs


def build_flight_claim_spec(trip: dict, booking: dict, *, model: str | None = None,
                            provider: str | None = None) -> dict | None:
    """A one-shot EU261 delay-claim check the day after a flight leg's arrival. Returns
    None if the booking has no usable arrival date."""
    arrival = _pdate(booking.get("end_ts")) or _pdate(booking.get("start_ts"))
    if arrival is None:
        return None
    model = model or _FALLBACK_MODEL
    provider = provider or _FALLBACK_PROVIDER
    claim_day = arrival + timedelta(days=1)
    ref = booking.get("booking_ref") or booking.get("carrier") or f"leg{booking.get('id')}"
    tag = f"{trip.get('name')} (#{trip.get('id')})"
    return {
        "name": f"OtenyTravelTalent EU261 — {tag} {ref}",
        "schedule": _iso_local(claim_day, CLAIM_HH), "repeat": 1, "kind": "eu261",
        "local": f"once {claim_day} {CLAIM_HH:02d}:00",
        "skills": ["trip-planner", "travel-concierge-voice"],
        "enabled_toolsets": ["web"],
        "model": model, "provider": provider,
        "prompt": (
            f"EU261 delay-claim check for flight {ref}. Load trip-planner; call `travel`/"
            "web_search for the ACTUAL vs scheduled arrival. If arrival delay >=3h or the "
            "flight was cancelled, draft an EU261 claim (eligibility, amount by distance, "
            "airline claim URL, ready-to-send message) per references/disruption.md "
            "§EU261. On time -> [SILENT]. Never fabricate a delay."),
    }


def existing_job_names(jobs_path: str) -> set[str]:
    p = Path(jobs_path)
    if not p.exists():
        return set()
    try:
        data = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return set()
    return {j.get("name") for j in data.get("jobs", [])}


def plan_for_trip(trip: dict, flights: list[dict], jobs_path: str, *,
                  model: str | None = None, provider: str | None = None,
                  ref: datetime | None = None) -> dict:
    """List-first plan: trip jobs + a claim job per monitored flight, minus any whose
    name is already registered."""
    specs = build_trip_specs(trip, model=model, provider=provider, ref=ref)
    for fl in flights:
        spec = build_flight_claim_spec(trip, fl, model=model, provider=provider)
        if spec is not None:
            specs.append(spec)
    have = existing_job_names(jobs_path)
    return {"to_create": [s for s in specs if s["name"] not in have],
            "existing": [s["name"] for s in specs if s["name"] in have]}


def _load_trip_and_flights(db_path: str, trip_id: int | None) -> tuple[dict | None, list[dict]]:
    p = Path(db_path)
    if not p.exists():
        return None, []
    con = sqlite3.connect(str(p))
    con.row_factory = sqlite3.Row
    try:
        if trip_id is not None:
            row = con.execute("SELECT * FROM trips WHERE id=?", (trip_id,)).fetchone()
        else:
            row = con.execute(
                "SELECT * FROM trips WHERE status!='cancelled' "
                "AND (end_date IS NULL OR end_date >= date('now')) "
                "ORDER BY start_date LIMIT 1").fetchone()
        if row is None:
            return None, []
        trip = dict(row)
        flights = [dict(r) for r in con.execute(
            "SELECT * FROM bookings WHERE trip_id=? AND kind IN ('flight') "
            "AND monitor=1", (trip["id"],)).fetchall()]
        return trip, flights
    except sqlite3.Error:
        return None, []
    finally:
        con.close()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="OtenyTravelTalent trip-scoped cron planner")
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    ap.add_argument("--jobs", default=DEFAULT_JOBS)
    ap.add_argument("--trip", type=int, default=None, help="trip id (default: active/soonest)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    trip, flights = _load_trip_and_flights(args.db, args.trip)
    if trip is None:
        msg = "no active/soonest trip found — nothing to schedule"
        print(json.dumps({"to_create": [], "existing": [], "note": msg}) if args.json else msg)
        return 0

    model, provider = read_model_provider(args.config)
    p = plan_for_trip(trip, flights, args.jobs, model=model, provider=provider)
    if args.json:
        print(json.dumps(p, indent=2))
        return 0
    if not p["to_create"]:
        print(f"all crons for trip #{trip['id']} already registered:", p["existing"])
        return 0
    print(f"Create these jobs for trip #{trip['id']} '{trip.get('name')}' via the "
          f"`cronjob` tool (list-first — these are absent). Pin model='{model}' "
          f"provider='{provider}' on EACH (un-pinned cron 400s):")
    for s in p["to_create"]:
        print(f"  • {s['name']}  [{s['local']}]  schedule='{s['schedule']}'  "
              f"repeat={s['repeat']}  skills={s['skills']}  model={s['model']}")
    if p["existing"]:
        print("already present:", p["existing"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
