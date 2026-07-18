#!/usr/bin/env python3
"""OtenyTravelTalent trip card — parameterized, per-tenant.

Reads ``~/.hermes/data/oteny-travel-talent/{trips.db,profile.yaml}`` and renders a
dark-themed PNG "trip card": header + countdown, the next scheduled items, the key
bookings with their last-known status, the settle-up board, and the packing status.
Nothing about a trip is baked. Prints the absolute output path on success.

Usage:
    trip_card.py --trip 3                 # a specific trip
    trip_card.py                          # the active / soonest trip
    trip_card.py --trip 3 --db PATH --profile PATH --out-dir DIR
"""
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except ImportError:
    # matplotlib is provisioned by the platform (the Oteny deployer installs the
    # runtime.python_packages declared in agent-profile.yaml into the tenant's system
    # python3; the golden + parent images bake it). On a box that predates that, degrade
    # instead of crashing: main() returns 2 so the trip-card cron registers FAILED (ops
    # sees a dead feature) rather than raising a raw ImportError. Same shape as `yaml`.
    plt = None

import argparse
import importlib.util
import os
import sqlite3
import sys
from datetime import date
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

DEFAULT_DB = os.path.expanduser("~/.hermes/data/oteny-travel-talent/trips.db")
DEFAULT_PROFILE = os.path.expanduser("~/.hermes/data/oteny-travel-talent/profile.yaml")
DEFAULT_OUT = "/tmp/hermes/cache"

# Style tokens — keep consistent across the family of OtenyTravelTalent visuals.
BG, PANEL, GRID = "#0b1020", "#121933", "#1f2a4d"
TEXT, MUTED = "#e7ecff", "#8b95c2"
ACCENT, OK, WARN, ALERT, MEMBER = "#7dd3fc", "#34d399", "#fbbf24", "#f87171", "#a78bfa"


def _load_settle():
    """Import the sibling settle_up.py by path (robust across the bundle layout)."""
    p = Path(__file__).resolve().parent.parent.parent / "scripts" / "settle_up.py"
    try:
        spec = importlib.util.spec_from_file_location("oteny_travel_settle", p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


def load_profile(path):
    if yaml and os.path.exists(path):
        with open(path) as fh:
            return yaml.safe_load(fh) or {}
    return {}


def resolve_trip(con, trip_id):
    con.row_factory = sqlite3.Row
    if trip_id is not None:
        row = con.execute("SELECT * FROM trips WHERE id=?", (trip_id,)).fetchone()
    else:
        row = con.execute(
            "SELECT * FROM trips WHERE status!='cancelled' "
            "AND (end_date IS NULL OR end_date >= date('now')) "
            "ORDER BY start_date LIMIT 1").fetchone()
        if row is None:
            row = con.execute("SELECT * FROM trips ORDER BY id DESC LIMIT 1").fetchone()
    return dict(row) if row else None


def countdown(trip, today):
    s = trip.get("start_date")
    e = trip.get("end_date") or s
    try:
        sd = date.fromisoformat(s) if s else None
        ed = date.fromisoformat(e) if e else None
    except (ValueError, TypeError):
        return ""
    if sd is None:
        return "dates TBD"
    if today < sd:
        d = (sd - today).days
        return "tomorrow" if d == 1 else f"in {d} days"
    if ed and today <= ed:
        return f"Day {(today - sd).days + 1} of {(ed - sd).days + 1}"
    return "ended"


def _panel(fig, rect, title):
    ax = fig.add_axes(rect)
    ax.set_facecolor(PANEL)
    ax.axis("off")
    ax.add_patch(plt.Rectangle((0, 0), 1, 1, transform=ax.transAxes, facecolor=PANEL,
                               edgecolor=GRID, lw=1.0, zorder=0))
    ax.text(0.04, 0.93, title, fontsize=12, fontweight="bold", color=ACCENT,
            va="top", transform=ax.transAxes)
    return ax


def _lines(ax, rows, *, empty="(nothing yet)", start_y=0.80, dy=0.115, color=TEXT):
    if not rows:
        ax.text(0.06, start_y, empty, fontsize=10, color=MUTED, va="top",
                transform=ax.transAxes)
        return
    y = start_y
    for r in rows[:6]:
        ax.text(0.06, y, r, fontsize=10, color=color, va="top", transform=ax.transAxes)
        y -= dy


def main(argv=None):
    if plt is None:
        print("Trip card unavailable: the plotting library isn't installed on this bot yet.",
              file=sys.stderr)
        return 2      # handled-error convention (like the no-db / no-trip cases below)
    ap = argparse.ArgumentParser()
    ap.add_argument("--trip", type=int, default=None)
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--profile", default=DEFAULT_PROFILE)
    ap.add_argument("--out-dir", default=DEFAULT_OUT)
    args = ap.parse_args(argv)

    if not os.path.exists(args.db):
        print(f"ERROR: no database at {args.db}", file=sys.stderr)
        return 2
    con = sqlite3.connect(args.db)
    trip = resolve_trip(con, args.trip)
    if trip is None:
        print("ERROR: no trip to render", file=sys.stderr)
        con.close()
        return 2

    profile = load_profile(args.profile)
    today = date.today()
    tid = trip["id"]

    con.row_factory = sqlite3.Row
    sched = [dict(r) for r in con.execute(
        "SELECT day_date, time, title, place FROM itinerary WHERE trip_id=? "
        "AND day_date >= date('now') ORDER BY day_date, COALESCE(time,'99:99') LIMIT 6",
        (tid,)).fetchall()]
    bookings = [dict(r) for r in con.execute(
        "SELECT kind, title, carrier, booking_ref, start_ts, status, monitor "
        "FROM bookings WHERE trip_id=? ORDER BY COALESCE(start_ts,'') LIMIT 6",
        (tid,)).fetchall()]
    members = [dict(r) for r in con.execute(
        "SELECT id, display_name, role FROM members WHERE trip_id=? ORDER BY id",
        (tid,)).fetchall()]
    todos = [dict(r) for r in con.execute(
        "SELECT member_id, done FROM todos WHERE trip_id=?", (tid,)).fetchall()]
    expenses = [dict(r) for r in con.execute(
        "SELECT payer_member_id, amount, currency, split_json FROM expenses WHERE trip_id=?",
        (tid,)).fetchall()]
    con.close()

    # --- settle-up ---
    settle_mod = _load_settle()
    default_cur = profile.get("default_currency") or ""
    settle_lines = []
    if settle_mod is not None and expenses:
        result = settle_mod.settle(members, expenses, default_cur)
        for cur, r in result.items():
            settle_lines.append(f"total {r['total_spend']:.2f} {cur}")
            if not r["transfers"]:
                settle_lines.append("  all square")
            for t in r["transfers"][:4]:
                settle_lines.append(f"  {t['from']} → {t['to']}: {t['amount']:.2f} {cur}")
    elif expenses:
        tot = sum(float(e.get("amount") or 0) for e in expenses)
        settle_lines.append(f"total {tot:.2f} {default_cur}")

    # --- packing/todo status ---
    open_n = sum(1 for t in todos if not t["done"])
    pack_lines = [f"{open_n} of {len(todos)} to-dos still open"] if todos else []
    name_by_id = {m["id"]: m["display_name"] for m in members}
    per = {}
    for t in todos:
        if t["done"]:
            continue
        who = name_by_id.get(t["member_id"], "party")
        per[who] = per.get(who, 0) + 1
    for who, n in list(per.items())[:4]:
        pack_lines.append(f"  {who}: {n} open")

    # --- bookings / plan text ---
    def book_line(b):
        head = f"{b['kind']} {b.get('carrier') or ''} {b.get('booking_ref') or ''}".strip()
        flag = f"  [{b['status']}]" if b.get("status") else ""
        return (f"{(b.get('start_ts') or '')[:16]}  {head or b.get('title') or ''}{flag}")[:46]

    sched_lines = [f"{(s.get('day_date') or '')[5:]} {s.get('time') or ''}  "
                   f"{s.get('title') or ''}".strip()[:46] for s in sched]
    book_lines = [book_line(b) for b in bookings]

    # --- render ---
    plt.rcParams.update({"font.family": "DejaVu Sans", "text.color": TEXT})
    fig = plt.figure(figsize=(11, 8.5), facecolor=BG)

    head = fig.add_axes([0.0, 0.86, 1.0, 0.14])
    head.set_facecolor(BG)
    head.axis("off")
    dest = f" · {trip['destination']}" if trip.get("destination") else ""
    head.text(0.04, 0.62, f"{trip['name']}{dest}", fontsize=26, fontweight="bold",
              color=TEXT, va="center")
    span = ""
    if trip.get("start_date"):
        span = f"{trip['start_date']} → {trip.get('end_date') or '?'}   ·   "
    head.text(0.04, 0.20, f"{span}{countdown(trip, today)}   ·   {trip.get('status', '')}",
              fontsize=13, color=MUTED, va="center")

    # Panel titles are plain text — DejaVu Sans (matplotlib's default) has no emoji
    # glyphs, so an emoji here renders as a tofu box. Emoji live in the Telegram reply
    # caption, not in the drawn image.
    ax1 = _panel(fig, [0.04, 0.46, 0.44, 0.36], "Plan — next up")
    _lines(ax1, sched_lines, empty="no scheduled items yet")
    ax2 = _panel(fig, [0.52, 0.46, 0.44, 0.36], "Bookings")
    _lines(ax2, book_lines, empty="no bookings yet")
    ax3 = _panel(fig, [0.04, 0.06, 0.44, 0.34], "Settle-up")
    _lines(ax3, settle_lines, empty="no expenses logged")
    ax4 = _panel(fig, [0.52, 0.06, 0.44, 0.34], "Packing status")
    _lines(ax4, pack_lines, empty="no to-dos yet", color=MEMBER)

    fig.text(0.96, 0.015, "OtenyTravelTalent", color=MUTED, fontsize=8.5, ha="right")

    os.makedirs(args.out_dir, exist_ok=True)
    out_path = os.path.join(args.out_dir, f"oteny_trip_{tid}_{today.isoformat()}.png")
    plt.savefig(out_path, dpi=170, facecolor=BG, bbox_inches="tight", pad_inches=0.2)
    plt.close(fig)
    print(out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
