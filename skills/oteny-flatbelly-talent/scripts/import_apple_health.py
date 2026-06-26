#!/usr/bin/env python3
"""Apple Health export importer for OtenyFlatBellyTalent — parameterized.

Parses an Apple Health ``export.xml`` (inside the exported .zip) and imports weight,
steps, sleep and workouts into the tenant's food.db. Paths are arguments — nothing is
baked. A real onboarding feature ("import your history"), not just cleanup.

Usage:
    import_apple_health.py --export ~/.hermes/data/oteny-flatbelly-talent/cache/export.zip \\
                           --db ~/.hermes/data/oteny-flatbelly-talent/food.db
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

DEFAULT_DB = os.path.expanduser("~/.hermes/data/oteny-flatbelly-talent/food.db")


def parse_date(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date().isoformat()
    except Exception:
        return None


def parse_time(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).strftime("%H:%M")
    except Exception:
        return None


def import_apple_health(export_zip_path: str, db_path: str) -> dict:
    counts = {"weight": 0, "steps": 0, "sleep": 0, "workouts": 0}
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(export_zip_path) as z:
            z.extractall(tmp)
        xml_path = Path(tmp) / "apple_health_export" / "export.xml"
        if not xml_path.exists():
            # some exports nest differently — search for it
            found = list(Path(tmp).rglob("export.xml"))
            if not found:
                raise FileNotFoundError("export.xml not found in archive")
            xml_path = found[0]

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        context = iter(ET.iterparse(str(xml_path), events=("end",)))
        _event, root = next(context)
        for _event, elem in context:
            if elem.tag == "Record":
                rec, d, val = elem.get("type"), parse_date(elem.get("startDate")), elem.get("value")
                if rec == "HKQuantityTypeIdentifierBodyMass" and val and d:
                    try:
                        # classify time-of-day from the reading hour (language-independent):
                        # before noon -> morning, else evening, so evening weighs don't
                        # pollute the morning-only trend.
                        hm = parse_time(elem.get("startDate"))
                        period = "morning" if (hm and int(hm[:2]) < 12) else "evening"
                        cur.execute(
                            "INSERT INTO weight (date, weight_kg, period, notes) VALUES (?,?,?, 'Apple Health') "
                            "ON CONFLICT(date) DO UPDATE SET weight_kg=excluded.weight_kg, "
                            "period=excluded.period, notes='Apple Health'",
                            (d, float(val), period))
                        counts["weight"] += 1
                    except Exception:
                        pass
                elif rec == "HKQuantityTypeIdentifierStepCount" and val and d:
                    try:
                        cur.execute(
                            "INSERT INTO daily_metrics (date, steps) VALUES (?,?) "
                            "ON CONFLICT(date) DO UPDATE SET steps=excluded.steps", (d, int(float(val))))
                        counts["steps"] += 1
                    except Exception:
                        pass
                elif rec == "HKCategoryTypeIdentifierSleepAnalysis" and d:
                    try:
                        s, e = parse_time(elem.get("startDate")), parse_time(elem.get("endDate"))
                        if s and e:
                            sd = datetime.strptime(s, "%H:%M")
                            ed = datetime.strptime(e, "%H:%M")
                            if ed < sd:
                                ed += timedelta(days=1)
                            hours = (ed - sd).total_seconds() / 3600
                            cur.execute(
                                "INSERT INTO daily_metrics (date, sleep_hours, bedtime, wake_time) VALUES (?,?,?,?) "
                                "ON CONFLICT(date) DO UPDATE SET sleep_hours=excluded.sleep_hours, "
                                "bedtime=excluded.bedtime, wake_time=excluded.wake_time",
                                (d, round(hours, 2), s, e))
                            counts["sleep"] += 1
                    except Exception:
                        pass
            elif elem.tag == "Workout":
                d = parse_date(elem.get("startDate"))
                wt = elem.get("workoutActivityType", "").replace("HKWorkoutActivityType", "")
                dur = elem.get("duration")
                if d and dur:
                    try:
                        cur.execute(
                            "INSERT INTO workouts (date, workout_type, duration_minutes, notes) "
                            "VALUES (?,?,?, 'Apple Health import')",
                            (d, (wt.lower() if wt else "walk"), int(float(dur))))
                        counts["workouts"] += 1
                    except Exception:
                        pass
            elem.clear()
        conn.commit()
        conn.close()
    return counts


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Import Apple Health export into OtenyFlatBellyTalent DB")
    ap.add_argument("--export", required=True, help="path to the Apple Health export .zip")
    ap.add_argument("--db", default=DEFAULT_DB)
    args = ap.parse_args(argv)
    try:
        c = import_apple_health(args.export, args.db)
    except Exception as e:
        print(f"❌ Import failed: {e}", file=sys.stderr)
        return 2
    print(f"✅ Imported — weight:{c['weight']} steps:{c['steps']} "
          f"sleep:{c['sleep']} workouts:{c['workouts']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
