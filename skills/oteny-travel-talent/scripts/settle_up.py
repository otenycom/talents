#!/usr/bin/env python3
"""settle_up — who-owes-whom for an OtenyTravelTalent trip, from the expenses ledger.

Deterministic backbone for the expense-split intent + the post-trip spend recap. Reads
the `expenses` + `members` rows for a trip, nets each person's paid-vs-owed, and emits a
minimal set of settle-up transfers ("Anna owes Ben 84.00 EUR"). Keeping the money math
in a script (not the weak model) is the guard against a confabulated balance.

Split model (per `expenses.split_json`):
  * 'even'  -> the cost is shared equally across every member of the trip.
  * a JSON object {"<member_id>": <weight>} -> shared by weight (absolute amounts work
    too: a weight is just its share of the total).
A NULL `payer_member_id` is the owner (attributed to the trip's lead member if one
exists). Currencies are settled INDEPENDENTLY (no FX conversion in v1) — a mixed-currency
trip yields one settle-up block per currency.

    python3 settle_up.py --trip 3 [--json]

Exit code is always 0; the result is in the output. Paths resolve through the same env
overrides as preflight.py.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

_BOT = "oteny-travel-talent"
_OWNER_ID = 0           # synthetic id for the owner when no lead member exists
_CENT = 0.01            # round transfers to the cent; suppress sub-cent noise


def _home() -> Path:
    return Path(os.environ.get("HH_HOME") or Path.home())


def _hermes_home() -> Path:
    env = os.environ.get("HH_HERMES_HOME") or os.environ.get("HERMES_HOME")
    return Path(env) if env else _home() / ".hermes"


def _data_dir() -> Path:
    return _hermes_home() / "data" / _BOT


def _parse_split(split, member_ids: list[int]) -> dict[int, float]:
    """Return {participant_id: weight}. 'even'/empty -> equal across all members."""
    s = str(split or "even").strip()
    if not s or s.lower() == "even":
        return {m: 1.0 for m in member_ids} if member_ids else {}
    try:
        d = json.loads(s)
        out = {int(k): float(v) for k, v in d.items() if float(v) > 0}
        return out or ({m: 1.0 for m in member_ids} if member_ids else {})
    except (ValueError, TypeError, json.JSONDecodeError):
        return {m: 1.0 for m in member_ids} if member_ids else {}


def _greedy_settle(net: dict[int, float]) -> list[tuple[int, int, float]]:
    """Minimal transfers that zero out the balances. Debtors pay creditors largest-first."""
    debtors = sorted(([p, -b] for p, b in net.items() if b < -_CENT), key=lambda x: x[1])
    creditors = sorted(([p, b] for p, b in net.items() if b > _CENT), key=lambda x: -x[1])
    transfers: list[tuple[int, int, float]] = []
    i = j = 0
    while i < len(debtors) and j < len(creditors):
        d, c = debtors[i], creditors[j]
        pay = round(min(d[1], c[1]), 2)
        if pay > _CENT:
            transfers.append((d[0], c[0], pay))
        d[1] -= pay
        c[1] -= pay
        if d[1] <= _CENT:
            i += 1
        if c[1] <= _CENT:
            j += 1
    return transfers


def settle(members: list[dict], expenses: list[dict], default_currency: str = "") -> dict:
    """Compute balances + settle-up transfers + total spend, grouped by currency."""
    name_by_id = {m["id"]: m.get("display_name") or f"member {m['id']}" for m in members}
    name_by_id[_OWNER_ID] = "You (owner)"
    member_ids = list(name_by_id.keys() - {_OWNER_ID})
    lead_id = next((m["id"] for m in members if m.get("role") == "lead"), None)

    def payer_of(pid):
        if pid is not None:
            return pid
        return lead_id if lead_id is not None else _OWNER_ID

    by_cur: dict[str, list[dict]] = defaultdict(list)
    for e in expenses:
        by_cur[(e.get("currency") or default_currency or "?")].append(e)

    out: dict[str, dict] = {}
    for cur, exps in by_cur.items():
        paid: dict[int, float] = defaultdict(float)
        owed: dict[int, float] = defaultdict(float)
        total = 0.0
        for e in exps:
            amt = float(e.get("amount") or 0)
            total += amt
            paid[payer_of(e.get("payer_member_id"))] += amt
            shares = _parse_split(e.get("split_json"), member_ids)
            wsum = sum(shares.values())
            if wsum <= 0:
                continue
            for pid, w in shares.items():
                owed[pid] += amt * w / wsum
        ids = set(paid) | set(owed)
        net = {p: round(paid[p] - owed[p], 2) for p in ids}
        transfers = [
            {"from_id": d, "from": name_by_id.get(d, f"member {d}"),
             "to_id": c, "to": name_by_id.get(c, f"member {c}"), "amount": amt}
            for d, c, amt in _greedy_settle(net)
        ]
        out[cur] = {
            "total_spend": round(total, 2),
            "balances": {name_by_id.get(p, f"member {p}"): net[p] for p in ids},
            "transfers": transfers,
        }
    return out


def _load(db: Path, trip_id: int):
    con = sqlite3.connect(str(db))
    con.row_factory = sqlite3.Row
    try:
        members = [dict(r) for r in con.execute(
            "SELECT id, display_name, role FROM members WHERE trip_id=? ORDER BY id",
            (trip_id,)).fetchall()]
        expenses = [dict(r) for r in con.execute(
            "SELECT payer_member_id, amount, currency, split_json, note "
            "FROM expenses WHERE trip_id=? ORDER BY id", (trip_id,)).fetchall()]
        return members, expenses
    finally:
        con.close()


def _default_currency() -> str:
    try:
        import yaml
        p = _data_dir() / "profile.yaml"
        if p.exists():
            return (yaml.safe_load(p.read_text()) or {}).get("default_currency") or ""
    except Exception:
        pass
    return ""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="OtenyTravelTalent settle-up")
    ap.add_argument("--db", default=None)
    ap.add_argument("--trip", type=int, required=True)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    db = Path(args.db) if args.db else _data_dir() / "trips.db"
    if not db.exists():
        print(json.dumps({}) if args.json else f"no database at {db}")
        return 0
    members, expenses = _load(db, args.trip)
    result = settle(members, expenses, _default_currency())

    if args.json:
        print(json.dumps(result, indent=2))
        return 0
    if not result:
        print(f"trip #{args.trip}: no expenses logged yet")
        return 0
    if not members:
        for cur, r in result.items():
            print(f"trip #{args.trip}: solo — total spend {r['total_spend']:.2f} {cur} "
                  "(nothing to split)")
        return 0
    for cur, r in result.items():
        print(f"— {cur} — total spend {r['total_spend']:.2f}")
        if not r["transfers"]:
            print("  all square, nobody owes anybody")
        for t in r["transfers"]:
            print(f"  {t['from']} owes {t['to']} {t['amount']:.2f} {cur}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
