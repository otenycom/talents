#!/usr/bin/env python3
"""OtenyFlatBellyTalent progress dashboard — parameterized, per-tenant.

Reads ``~/.hermes/data/oteny-flatbelly-talent/food.db`` (morning weights only — food-tracker hard rule),
computes full-period and 7-day slopes, projects to the goal and to any optional
milestone bands, and writes a dark-themed PNG. Goal, milestones and the DB path come
from ``~/.hermes/data/oteny-flatbelly-talent/profile.yaml`` — nothing about a body is baked.

Prints the absolute output path on success.

Usage:
    generate.py                          # uses ~/.hermes/data/oteny-flatbelly-talent/{food.db,profile.yaml}
    generate.py --db PATH --profile PATH --out-dir DIR
"""
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.patches import FancyBboxPatch
    from matplotlib.patheffects import withStroke
except ImportError:
    # matplotlib is provisioned by the platform (the hermeshost deployer installs the
    # runtime.python_packages declared in agent-profile.yaml into the tenant's system
    # python3; the golden + parent images bake it). On a box that predates that, degrade
    # instead of crashing: main() returns 2 so the weekly-dashboard cron registers FAILED
    # (ops sees a dead feature) rather than raising a raw ImportError. Same shape as `yaml`.
    plt = mdates = FancyBboxPatch = withStroke = None

import argparse
import os
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path


def _belt():
    """The shared readiness belt (``selfcheck.read_yaml`` + ``UNREADABLE``), loaded from the
    bundle's main ``scripts/`` dir — the ONE stdlib-first YAML reader every readiness script
    shares. It gives this dashboard a cold-box-safe profile read AND the three-valued signal
    that lets a PRESENT-but-unreadable profile fail UNKNOWN-loud instead of silently degrading
    to ``{}`` (goal-unset), which would mis-report an env fault as 'no goal set'."""
    import importlib.util

    p = Path(__file__).resolve().parent.parent.parent / "scripts" / "selfcheck.py"
    spec = importlib.util.spec_from_file_location("oteny_readiness_belt", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


DEFAULT_DB = os.path.expanduser("~/.hermes/data/oteny-flatbelly-talent/food.db")
DEFAULT_PROFILE = os.path.expanduser("~/.hermes/data/oteny-flatbelly-talent/profile.yaml")
DEFAULT_OUT = "/tmp/hermes/cache"

# Style tokens — keep consistent across the family of OtenyFlatBellyTalent visuals.
BG, PANEL, GRID = "#0b1020", "#121933", "#1f2a4d"
TEXT, MUTED = "#e7ecff", "#8b95c2"
ACCENT, ACCENT2 = "#7dd3fc", "#a78bfa"      # weight / trend
GOLD, GREEN, PINK = "#fbbf24", "#34d399", "#f472b6"   # milestone / goal / start


def load_profile(path):
    """Read profile.yaml via the shared belt. Returns ``(status, data)``:
      * ``("ok", dict)``       — parsed (goal/milestones available);
      * ``("absent", {})``     — no file / empty → genuine "set a goal first";
      * ``("unreadable", {})`` — PRESENT but unparseable → an ENV fault (UNKNOWN-loud, not
        'no goal set'), so ops sees the real problem instead of a misleading goal-unset."""
    belt = _belt()
    data = belt.read_yaml(Path(path))
    if data is belt.UNREADABLE:
        return "unreadable", {}
    return ("ok", data) if isinstance(data, dict) else ("absent", {})


def load_morning_weights(db_path):
    """Morning weights only — filter on the canonical, language-independent `period`
    column (NULL counts as morning), never on localized note text."""
    con = sqlite3.connect(db_path)
    try:
        rows = con.execute(
            "SELECT date, weight_kg FROM weight "
            "WHERE COALESCE(period,'morning') = 'morning' ORDER BY date ASC").fetchall()
    finally:
        con.close()
    return [(date.fromisoformat(d), float(w)) for d, w in rows]


def linreg(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    denom = sum((x - mx) ** 2 for x in xs)
    if denom == 0:
        return 0.0, my
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denom
    return slope, my - slope * mx


def eta_for(current, target, slope7):
    if slope7 < 0 and current > target:
        days = (current - target) / -slope7
        return date.today() + timedelta(days=int(days)), int(days)
    if current <= target:
        return None, 0
    return None, None


def main(argv=None):
    if plt is None:
        print("Weekly chart unavailable: the plotting library isn't installed on this bot yet.",
              file=sys.stderr)
        return 2      # handled-error convention (like goal-unset / <2-weights below)
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--profile", default=DEFAULT_PROFILE)
    ap.add_argument("--out-dir", default=DEFAULT_OUT)
    args = ap.parse_args(argv)

    status, profile = load_profile(args.profile)
    if status == "unreadable":
        # An ENV fault (a present-but-corrupt profile), NOT a missing goal — UNKNOWN-loud so
        # the weekly cron's failure reads as "fix the environment", never "the user set no goal".
        print("UNKNOWN: profile.yaml is PRESENT but unreadable (environment fault, not a "
              "missing goal). Report it; do NOT regenerate a chart from defaults.",
              file=sys.stderr)
        return 2
    goal = float(profile.get("goal_weight_kg") or 0)
    if not goal:
        print("ERROR: profile.goal_weight_kg not set", file=sys.stderr)
        return 2
    # optional milestones: [{label, weight_kg}]; first one drives the secondary band.
    milestones = [m for m in (profile.get("milestones") or []) if m.get("weight_kg")]
    milestone = milestones[0] if milestones else None

    morning = load_morning_weights(args.db)
    if len(morning) < 2:
        print("ERROR: need at least 2 morning weight rows", file=sys.stderr)
        return 2

    dates = [d for d, _ in morning]
    ws = [w for _, w in morning]
    start_d, start_w, current = dates[0], ws[0], ws[-1]
    xs = [(d - start_d).days for d in dates]
    slope_full, _ = linreg(xs, ws)
    slope7, _ = linreg(xs[-7:], ws[-7:]) if len(xs) >= 7 else (slope_full, 0)

    total_loss = start_w - current
    to_goal = current - goal
    pct_done = (start_w - current) / (start_w - goal) * 100 if start_w > goal else 0.0

    eta_goal_d, eta_goal_days = eta_for(current, goal, slope7)
    eta_goal_str = eta_goal_d.strftime("%d %b %Y") if eta_goal_d else "—"
    eta_goal_sub = (f"{eta_goal_days} days away" if eta_goal_d else
                    "slope flipped, need a recovery week" if eta_goal_days is None else "reached ✓")

    if milestone:
        m_label, m_kg = milestone.get("label", "milestone"), float(milestone["weight_kg"])
        eta_m_d, eta_m_days = eta_for(current, m_kg, slope7)
        eta_m_str = eta_m_d.strftime("%d %b") if eta_m_d else ("reached ✓" if eta_m_days == 0 else "—")
        eta_m_sub = (f"{eta_m_days} days away" if eta_m_d else
                     "reached" if eta_m_days == 0 else "slope flipped")

    plt.rcParams.update({
        "font.family": "DejaVu Sans", "axes.edgecolor": GRID, "axes.labelcolor": MUTED,
        "xtick.color": MUTED, "ytick.color": MUTED, "text.color": TEXT,
    })
    fig = plt.figure(figsize=(13, 8.5), facecolor=BG)
    gs = fig.add_gridspec(3, 4, height_ratios=[0.55, 3.0, 0.9], width_ratios=[1, 1, 1, 1],
                          hspace=0.45, wspace=0.30, left=0.06, right=0.97, top=0.92, bottom=0.08)

    ax_h = fig.add_subplot(gs[0, :])
    ax_h.set_facecolor(BG)
    ax_h.axis("off")
    ax_h.text(0.0, 0.78, f"Road to {goal:g} kg", fontsize=30, fontweight="bold", color=TEXT,
              path_effects=[withStroke(linewidth=3, foreground=BG)])
    ax_h.text(0.0, 0.18,
              f"Day {xs[-1]+1}   ·   {start_d.strftime('%d %b')} → {dates[-1].strftime('%d %b %Y')}"
              f"   ·   morning weights only", fontsize=12, color=MUTED)
    ax_h.text(1.0, 0.78, f"−{total_loss:.1f} kg", fontsize=40, fontweight="bold", color=GREEN,
              ha="right", path_effects=[withStroke(linewidth=3, foreground=BG)])
    ax_h.text(1.0, 0.20, f"{pct_done:.1f}% of the way to {goal:g} kg", fontsize=12, color=MUTED, ha="right")

    ax = fig.add_subplot(gs[1, :])
    ax.set_facecolor(PANEL)
    for sp in ax.spines.values():
        sp.set_color(GRID)
    ax.axhspan(goal - 0.5, goal + 0.5, color=GREEN, alpha=0.10, zorder=1)
    if milestone:
        ax.axhspan(m_kg - 0.5, m_kg + 0.5, color=GOLD, alpha=0.10, zorder=1)

    if slope7 < 0 and eta_goal_days:
        proj_days = list(range(xs[-1], xs[-1] + int(eta_goal_days) + 5))
        proj_x = [start_d + timedelta(days=d) for d in proj_days]
        proj_y = [ws[-1] + slope7 * (d - xs[-1]) for d in proj_days]
        ax.plot(proj_x, proj_y, "--", color=ACCENT2, lw=1.6, alpha=0.65, zorder=3,
                label=f"projected trend (−{abs(slope7)*7:.2f} kg/wk)")
        xlim_right = proj_x[-1] + timedelta(days=3)
    else:
        xlim_right = dates[-1] + timedelta(days=14)

    ax.plot(dates, ws, color=ACCENT, lw=3.2, alpha=0.35, zorder=4)
    ax.plot(dates, ws, color=ACCENT, lw=1.8, zorder=5)
    ax.scatter(dates, ws, s=22, color=ACCENT, edgecolor=BG, lw=0.8, zorder=6)
    ax.scatter([dates[0]], [ws[0]], s=120, color=PINK, edgecolor=BG, lw=1.5, zorder=7)
    ax.scatter([dates[-1]], [ws[-1]], s=180, color=GREEN, edgecolor=BG, lw=1.5, zorder=8)
    ax.annotate(f"{ws[0]:.1f} kg\nstart", xy=(dates[0], ws[0]), xytext=(8, 12),
                textcoords="offset points", color=PINK, fontsize=10, fontweight="bold")
    ax.annotate(f"{ws[-1]:.1f} kg\ntoday", xy=(dates[-1], ws[-1]), xytext=(-6, 14),
                textcoords="offset points", color=GREEN, fontsize=11, fontweight="bold", ha="right")
    ax.axhline(goal, color=GREEN, lw=1.2, ls=":", alpha=0.7)
    ax.text(xlim_right - timedelta(days=1), goal + 0.25, f"GOAL {goal:g} kg → {eta_goal_str}",
            color=GREEN, fontsize=10, fontweight="bold", va="bottom", ha="right")
    if milestone:
        ax.axhline(m_kg, color=GOLD, lw=1.2, ls=":", alpha=0.7)
        ax.text(dates[0], m_kg + 0.25, f"  {m_label} ~{m_kg:g} kg → ETA {eta_m_str}",
                color=GOLD, fontsize=10, fontweight="bold", va="bottom")

    ax.set_ylabel("Weight (kg)", fontsize=11, color=MUTED)
    ax.grid(True, color=GRID, lw=0.6, alpha=0.6)
    ax.set_axisbelow(True)
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    floor = min(goal, m_kg) if milestone else goal
    ax.set_ylim(floor - 1.0, max(max(ws) + 0.6, start_w + 0.4))
    ax.set_xlim(dates[0] - timedelta(days=2), xlim_right)
    leg = ax.legend(loc="upper right", frameon=True, fontsize=9, labelcolor=TEXT)
    if leg:
        leg.get_frame().set_facecolor(BG)
        leg.get_frame().set_edgecolor(GRID)

    def card(ax, title, value, sub, color):
        ax.set_facecolor(PANEL)
        ax.axis("off")
        ax.add_patch(FancyBboxPatch((0.02, 0.05), 0.96, 0.90,
                     boxstyle="round,pad=0.02,rounding_size=0.06", transform=ax.transAxes,
                     linewidth=0, facecolor=PANEL))
        ax.text(0.5, 0.78, title, fontsize=9.5, color=MUTED, ha="center", transform=ax.transAxes)
        ax.text(0.5, 0.45, value, fontsize=22, fontweight="bold", color=color, ha="center", transform=ax.transAxes)
        ax.text(0.5, 0.16, sub, fontsize=9, color=MUTED, ha="center", transform=ax.transAxes)

    pace_str = f"{slope7*7:+.2f} kg/wk".replace("+-", "-")
    pace_sub = ("healthy fat-loss zone" if -1.2 <= slope7*7 <= -0.4 else
                "aggressive — watch for muscle loss" if slope7*7 < -1.2 else
                "slower than target" if slope7 < 0 else "recovery / plateau week")
    card(fig.add_subplot(gs[2, 0]), "PACE  (last 7 days)", pace_str, pace_sub, ACCENT)
    card(fig.add_subplot(gs[2, 1]), "STILL TO GO", f"{to_goal:.1f} kg", f"{pct_done:.0f}% complete", PINK)
    if milestone:
        card(fig.add_subplot(gs[2, 2]), f"{m_label.upper()} ETA", eta_m_str, eta_m_sub, GOLD)
    else:
        card(fig.add_subplot(gs[2, 2]), "FULL-PERIOD PACE", f"{slope_full*7:+.2f} kg/wk", f"n={len(ws)} days", GOLD)
    card(fig.add_subplot(gs[2, 3]), f"{goal:g} kg ETA  (at current pace)", eta_goal_str, eta_goal_sub, GREEN)

    fig.text(0.06, 0.015,
             f"{start_w:.1f} → {current:.1f} kg morning baseline · "
             f"slope (full {xs[-1]+1} d): {slope_full*7:+.2f} kg/wk · last 7 d: {slope7*7:+.2f} kg/wk",
             color=MUTED, fontsize=8.5)
    fig.text(0.97, 0.015, "OtenyFlatBellyTalent · morning weights filtered", color=MUTED, fontsize=8.5, ha="right")

    os.makedirs(args.out_dir, exist_ok=True)
    out_path = os.path.join(args.out_dir, f"oteny_belly_progress_{date.today().isoformat()}.png")
    plt.savefig(out_path, dpi=180, facecolor=BG, bbox_inches="tight", pad_inches=0.25)
    print(out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
