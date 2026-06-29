"""Integrity + script unit tests for the oteny-travel-talent bundle.

Mirrors the structural invariants in test_talents_bundles.py for the travel Talent (the
shipped selfcheck matches canonical; init.sql creates the six tables idempotently; the
manifest parses + selfchecks; first-run is mechanical + in references/; the bundle is
PII-clean; routing signatures line up) and unit-tests the four travel-specific scripts
(trip-scoped cron planner, transport monitor, settle-up, preflight) + the trip card.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from _talents import CATALOG, SHARED, load, sandbox_env

TRAVEL = CATALOG / "oteny-travel-talent"
TABLES = {"trips", "members", "bookings", "itinerary", "todos", "expenses"}

pc = load(TRAVEL / "scripts" / "provision_cron.py", "tt_provision_cron")
mt = load(TRAVEL / "scripts" / "monitor_transport.py", "tt_monitor_transport")
su = load(TRAVEL / "scripts" / "settle_up.py", "tt_settle_up")
pf = load(TRAVEL / "scripts" / "preflight.py", "tt_preflight")
sc = load(SHARED / "selfcheck.py", "tt_sc_travel")
mg = load(TRAVEL / "scripts" / "migrate.py", "tt_migrate")
ml = load(TRAVEL / "scripts" / "maplink.py", "tt_maplink")


def _sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _flat(text: str) -> str:
    """Lowercased, whitespace-collapsed — so a line-wrapped markdown phrase still matches."""
    return " ".join(text.lower().split())


def _make_db(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.executescript((TRAVEL / "scripts" / "init.sql").read_text())
    con.commit()
    con.row_factory = sqlite3.Row
    return con


# --------------------------------------------------------------------------- #
# structure / upgrade-safety                                                   #
# --------------------------------------------------------------------------- #
def test_shipped_selfcheck_matches_canonical():
    assert _sha(TRAVEL / "scripts" / "selfcheck.py") == _sha(SHARED / "selfcheck.py")


def test_shipped_migrate_matches_canonical():
    assert _sha(TRAVEL / "scripts" / "migrate.py") == _sha(SHARED / "migrate.py")


def test_init_sql_creates_six_tables_idempotently(tmp_path):
    sql = (TRAVEL / "scripts" / "init.sql").read_text()
    db = tmp_path / "trips.db"
    con = sqlite3.connect(db)
    con.executescript(sql)
    t1 = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    con.executescript(sql)  # idempotent — re-running raises nothing
    t2 = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    con.close()
    assert TABLES <= t1
    assert t1 == t2


def test_first_run_lives_in_references_and_is_mechanical():
    fr = (TRAVEL / "trip-planner" / "references" / "first-run.md").read_text()
    assert "selfcheck.py" in fr                       # opens with the guard
    assert "index_reconciler.py" in fr                # registers group routing via reconciler
    assert "scripts/init.sql" in fr and "sqlite3" in fr  # declared schema, not inline DDL
    in_fence = False
    for line in fr.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            assert "python3 -c" not in line and "python -c" not in line
            assert "<<" not in line                   # no heredoc in a runnable block


def test_first_run_not_in_engine_body():
    body = (TRAVEL / "trip-planner" / "SKILL.md").read_text()
    assert "First-run setup" not in body             # moved to references/first-run.md
    assert "CREATE TABLE" not in body                # schema lives in scripts/init.sql


def test_manifest_parses_and_bare_box_selfchecks(tmp_path, monkeypatch):
    manifest = TRAVEL / "required_artifacts.yaml"
    data = yaml.safe_load(manifest.read_text())
    assert data["bot"] == "oteny-travel-talent" and data["artifacts"]
    must = [a for a in data["artifacts"] if a["kind"] == "sqlite_db"][0]["must_have_tables"]
    assert set(must) == TABLES
    sandbox_env(monkeypatch, tmp_path)
    rep = sc.run(manifest)
    assert rep["ready"] is False                      # bare sandbox -> not ready, ran cleanly
    # DM-first routing auto-satisfies even on a bare box (never in the missing list)
    assert "routing" not in {m["kind"] for m in rep["missing"]}


def test_full_setup_reaches_ready(tmp_path, monkeypatch):
    """The plan's done-criterion for first-run: 6 tables + profile + routing -> READY."""
    sandbox_env(monkeypatch, tmp_path)
    data = tmp_path / ".hermes" / "data" / "oteny-travel-talent"
    data.mkdir(parents=True)
    _make_db(data / "trips.db").close()
    (data / "profile.yaml").write_text(
        "home_city: Rotterdam\nhome_timezone: Europe/Amsterdam\n"
        "language: en\ndefault_currency: EUR\n")
    # the tools artifact asserts the visual was DELIVERED — simulate the overlay drop
    delivered = (tmp_path / ".hermes" / "skills" / "talents" / "oteny-travel-talent"
                 / "trip-dashboard" / "scripts")
    delivered.mkdir(parents=True)
    (delivered / "trip_card.py").write_text("# delivered\n")
    rep = sc.run(TRAVEL / "required_artifacts.yaml")
    assert rep["ready"] is True, rep["missing"]       # memory/cron non-blocking; routing auto


def test_routing_signature_matches_and_is_dm_first():
    profile = yaml.safe_load((TRAVEL / "agent-profile.yaml").read_text())
    manifest = yaml.safe_load((TRAVEL / "required_artifacts.yaml").read_text())
    routing = [a for a in manifest["artifacts"] if a["kind"] == "routing"][0]
    assert profile["routing"]["signature"] == routing["signature"] == "oteny-travel-talent"
    # DM-first: we do NOT require a group channel_prompt (it auto-satisfies)
    assert not routing.get("requires_channel_prompt")
    assert not routing.get("channel_chat_id")


def test_bundle_is_pii_and_secret_clean():
    import re
    pii = re.compile(r"\bRies\b|\bvriend\b|api[_-]?key\s*[:=]|sk-[A-Za-z0-9]{20}"
                     r"|\b\d{6,}:[A-Za-z0-9_-]{30}", re.IGNORECASE)
    for f in TRAVEL.rglob("*"):
        if f.suffix in (".md", ".yaml", ".py", ".sql", ".template") and "__pycache__" not in f.parts:
            hits = [ln for ln in f.read_text().splitlines() if pii.search(ln)]
            assert not hits, f"PII/secret in {f}: {hits[:2]}"


def test_data_under_hermes_home_no_root_paths():
    for f in TRAVEL.rglob("*"):
        if f.suffix in (".md", ".yaml", ".py", ".sql", ".template") and "__pycache__" not in f.parts:
            assert "~/oteny-travel-talent/" not in f.read_text(), f


# --------------------------------------------------------------------------- #
# provision_cron — the trip-scoped planner                                     #
# --------------------------------------------------------------------------- #
_TRIP = {"id": 3, "name": "Our Trip to Lisbon",
         "start_date": "2026-09-10", "end_date": "2026-09-14"}
_REF = datetime(2026, 8, 1)


def test_cron_trip_specs_shape_and_self_expiry():
    specs = pc.build_trip_specs(_TRIP, model="assistant", provider="router", ref=_REF)
    kinds = {s["kind"]: s for s in specs}
    assert set(kinds) == {"monitor", "briefing", "review"}
    # monitor: every 6h across (start − 2d) … (end + 1d) = Sep 8–15, bounded (auto-deletes)
    assert kinds["monitor"]["schedule"] == "0 */6 8-15 9 *"
    assert kinds["monitor"]["repeat"] == 32          # 8 days × 4/day
    # briefing: daily on the trip days, one run per day
    assert kinds["briefing"]["schedule"] == "30 7 10-14 9 *"
    assert kinds["briefing"]["repeat"] == 5
    # review: one-shot the day after end_date (auto-deletes)
    assert kinds["review"]["schedule"] == "2026-09-15T10:00"
    assert kinds["review"]["repeat"] == 1
    for s in specs:
        assert "#3" in s["name"] and "Lisbon" in s["name"]


def test_cron_jobs_pin_model_and_provider():
    # config.yaml carries the persona alias `assistant` (what render_config_yaml writes),
    # NOT a raw OpenRouter slug, which the router 400s (D55).
    specs = pc.build_trip_specs(_TRIP, model="assistant", provider="router", ref=_REF)
    for s in specs:
        assert s["model"] == "assistant" and s["provider"] == "router"


def test_cron_model_provider_read_and_fallback(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("model:\n  provider: router\n  model: assistant\n")
    assert pc.read_model_provider(str(cfg)) == ("assistant", "router")
    # missing config -> the assistant alias, never the raw slug, never empty
    assert pc.read_model_provider(str(tmp_path / "absent.yaml")) == ("assistant", "router")
    for s in pc.build_trip_specs(_TRIP, ref=_REF):
        assert s["model"] == "assistant" and s["provider"] == "router"


def test_cron_listfirst_excludes_registered(tmp_path):
    jobs = tmp_path / "jobs.json"
    plan0 = pc.plan_for_trip(_TRIP, [], str(tmp_path / "none.json"), ref=_REF)
    names = [s["name"] for s in plan0["to_create"]]
    assert len(names) == 3
    jobs.write_text(json.dumps({"jobs": [{"name": names[0]}]}))
    plan1 = pc.plan_for_trip(_TRIP, [], str(jobs), ref=_REF)
    assert names[0] in plan1["existing"]
    assert len(plan1["to_create"]) == 2


def test_cron_flight_claim_one_shot():
    booking = {"id": 5, "booking_ref": "TP661", "carrier": "TAP",
               "end_ts": "2026-09-10T11:55"}
    spec = pc.build_flight_claim_spec(_TRIP, booking, model="assistant", provider="router")
    assert spec["schedule"] == "2026-09-11T12:00"   # day after arrival
    assert spec["repeat"] == 1 and spec["kind"] == "eu261"
    assert "TP661" in spec["name"] and spec["model"] == "assistant"
    # a dateless leg yields no claim job
    assert pc.build_flight_claim_spec(_TRIP, {"id": 6}) is None


def test_cron_month_spanning_stays_windowed_never_interval():
    """A window that crosses a month boundary splits into one day-bounded cron expr per
    month — NEVER an `every Nh` interval (which would fire from creation, weeks early)."""
    trip = {"id": 9, "name": "NYE", "start_date": "2026-12-30", "end_date": "2027-01-03"}
    specs = pc.build_trip_specs(trip, ref=datetime(2026, 12, 1))
    # not a single spec is an interval — the bug that fired far from the trip
    assert all(not s["schedule"].startswith("every ") for s in specs)
    by_kind: dict[str, list[dict]] = {}
    for s in specs:
        by_kind.setdefault(s["kind"], []).append(s)
    # monitor window Dec 28 … Jan 4 → two month segments, each day-of-month bounded
    mon = {s["schedule"]: s for s in by_kind["monitor"]}
    assert set(mon) == {"0 */6 28-31 12 *", "0 */6 1-4 1 *"}
    assert mon["0 */6 28-31 12 *"]["repeat"] == 16        # 4 days × 4/day
    assert mon["0 */6 1-4 1 *"]["repeat"] == 16
    # briefing window = trip days Dec 30 … Jan 3 → two segments
    brief = {s["schedule"] for s in by_kind["briefing"]}
    assert brief == {"30 7 30-31 12 *", "30 7 1-3 1 *"}
    # multi-segment jobs carry a [MM] suffix so each is a distinct, dedupable job
    assert any(name.endswith("[12]") for name in (s["name"] for s in by_kind["monitor"]))
    assert any(name.endswith("[01]") for name in (s["name"] for s in by_kind["monitor"]))
    # the one-shot review is unaffected (day after end_date)
    assert by_kind["review"][0]["schedule"] == "2027-01-04T10:00"


def test_cron_dateless_trip_plans_nothing():
    assert pc.build_trip_specs({"id": 1, "name": "someday"}, ref=_REF) == []


# --------------------------------------------------------------------------- #
# migrate — in-box, forward-only state migrations                              #
# --------------------------------------------------------------------------- #
def test_migrations_manifest_parses_and_refs_resolve():
    manifest = mg.load_manifest()                       # the real travel migrations.yaml
    assert manifest["bot"] == "oteny-travel-talent"
    decl = mg.declared(manifest)
    ids = [m["id"] for m in decl]
    assert ids == sorted(ids)                           # ordered, forward-only
    assert len(ids) == len(set(ids))                    # unique
    assert "0001_windowed_trip_crons" in ids
    md = (TRAVEL / "trip-planner" / "references" / "migrations.md").read_text()
    for m in decl:                                      # every checklist ref resolves
        if m.get("kind", "checklist") == "checklist":
            anchor = m["ref"].split("#", 1)[1]
            assert f"## {anchor}" in md, f"no section for {m['id']} in migrations.md"


def test_migrate_status_then_baseline(tmp_path, monkeypatch):
    sandbox_env(monkeypatch, tmp_path)
    # a legacy box (no marker) → every declared migration pending
    pend = mg.pending_for()
    assert "0001_windowed_trip_crons" in [m["id"] for m in pend]
    assert mg.status_line().startswith("MIGRATIONS: pending —")
    # baseline (fresh first-run) marks all applied WITHOUT running → nothing pending
    assert mg.main(["--baseline"]) == 0
    assert mg.pending_for() == []
    assert mg.status_line() == "MIGRATIONS: none"
    marker = tmp_path / ".hermes" / "data" / "oteny-travel-talent" / "migrations.json"
    assert "0001_windowed_trip_crons" in json.loads(marker.read_text())["applied"]


def test_migrate_mark_is_idempotent_and_targeted(tmp_path, monkeypatch):
    sandbox_env(monkeypatch, tmp_path)
    mg.main(["--mark", "0001_windowed_trip_crons"])
    assert all(m["id"] != "0001_windowed_trip_crons" for m in mg.pending_for())
    mg.main(["--mark", "0001_windowed_trip_crons"])     # re-mark is a no-op
    marker = tmp_path / ".hermes" / "data" / "oteny-travel-talent" / "migrations.json"
    assert json.loads(marker.read_text())["applied"] == ["0001_windowed_trip_crons"]


def test_migrate_apply_refuses_checklist(tmp_path, monkeypatch, capsys):
    sandbox_env(monkeypatch, tmp_path)
    mg.main(["--apply", "0001_windowed_trip_crons"])
    out = capsys.readouterr().out
    assert "ERROR" in out and "checklist" in out        # a checklist migration is agent-run
    assert mg.pending_for()                             # NOT marked applied


def test_migrate_apply_sql_is_idempotent(tmp_path, monkeypatch):
    """A deterministic `sql` migration runs against the bot db and re-runs cleanly."""
    sandbox_env(monkeypatch, tmp_path)
    data = tmp_path / ".hermes" / "data" / "oteny-travel-talent"
    data.mkdir(parents=True)
    _make_db(data / "trips.db").close()
    man = tmp_path / "m.yaml"
    man.write_text(
        "bot: oteny-travel-talent\ndb: trips.db\nmigrations:\n"
        "  - id: 0099_add_col\n    kind: sql\n"
        "    sql: \"ALTER TABLE trips ADD COLUMN seat_pref TEXT;\"\n")
    assert mg.main(["--manifest", str(man), "--apply", "0099_add_col"]) == 0
    cols = {r[1] for r in sqlite3.connect(data / "trips.db").execute("PRAGMA table_info(trips)")}
    assert "seat_pref" in cols
    assert mg.pending_for(man) == []                    # marked applied
    assert mg.main(["--manifest", str(man), "--apply", "0099_add_col"]) == 0  # re-run no-ops


def test_preflight_surfaces_migrations_gate(tmp_path, monkeypatch, capsys):
    # the single per-turn context call carries the pending-migration gate, so the agent
    # reconciles old-version state before planning (even on a box with no db yet).
    sandbox_env(monkeypatch, tmp_path)
    pf.main()
    assert "MIGRATIONS: pending" in capsys.readouterr().out
    mg.main(["--baseline"])                              # fresh first-run baselines
    pf.main()
    assert "MIGRATIONS: none" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# monitor_transport — selection (window gate) + diff/persist                   #
# --------------------------------------------------------------------------- #
def test_monitor_due_window_gates(tmp_path):
    con = _make_db(tmp_path / "trips.db")
    con.execute("INSERT INTO trips (id,name,start_date,end_date,status) VALUES "
                "(1,'Now',date('now','-1 day'),date('now','+5 days'),'active')")
    con.execute("INSERT INTO trips (id,name,start_date,end_date,status) VALUES "
                "(2,'Later',date('now','+200 days'),date('now','+205 days'),'planning')")
    con.execute("INSERT INTO bookings (trip_id,kind,carrier,booking_ref,monitor,status) "
                "VALUES (1,'flight','TAP','TP661',1,'on-time')")
    con.execute("INSERT INTO bookings (trip_id,kind,carrier,booking_ref,monitor) "
                "VALUES (2,'flight','KL','KL1001',1)")
    con.execute("INSERT INTO bookings (trip_id,kind,monitor) VALUES (1,'hotel',0)")
    con.commit()
    due = mt.due_legs(con)
    con.close()
    refs = {d["booking_ref"] for d in due}
    assert refs == {"TP661"}                 # only the in-window monitored flight


def test_monitor_update_diffs_and_errors(tmp_path):
    con = _make_db(tmp_path / "trips.db")
    con.execute("INSERT INTO trips (id,name) VALUES (1,'T')")
    con.execute("INSERT INTO bookings (id,trip_id,kind,monitor,status) "
                "VALUES (7,1,'flight',1,'on-time')")
    con.commit()
    assert mt.update_leg(con, 7, "delayed 40m, gate B7")["result"] == "CHANGED"
    assert mt.update_leg(con, 7, "delayed 40m, gate B7")["result"] == "UNCHANGED"
    # an unmonitored / missing leg is an actionable ERROR, never a silent empty result
    con.execute("INSERT INTO bookings (id,trip_id,kind,monitor) VALUES (8,1,'hotel',0)")
    con.commit()
    assert mt.update_leg(con, 8, "x")["result"] == "ERROR"
    assert mt.update_leg(con, 999, "x")["result"] == "ERROR"
    con.close()


# --------------------------------------------------------------------------- #
# settle_up — split math                                                       #
# --------------------------------------------------------------------------- #
_MEMBERS = [{"id": 1, "display_name": "Anna", "role": "lead"},
            {"id": 2, "display_name": "Ben", "role": "member"}]


def test_settle_even_split():
    res = su.settle(_MEMBERS, [{"payer_member_id": 1, "amount": 100, "currency": "EUR",
                                "split_json": "even"}])
    t = res["EUR"]["transfers"]
    assert res["EUR"]["total_spend"] == 100.0
    assert t == [{"from_id": 2, "from": "Ben", "to_id": 1, "to": "Anna", "amount": 50.0}]


def test_settle_custom_split():
    res = su.settle(_MEMBERS, [{"payer_member_id": 1, "amount": 90, "currency": "EUR",
                                "split_json": '{"2": 1}'}])  # only Ben owes
    assert res["EUR"]["transfers"] == [
        {"from_id": 2, "from": "Ben", "to_id": 1, "to": "Anna", "amount": 90.0}]


def test_settle_all_square():
    exps = [{"payer_member_id": 1, "amount": 50, "currency": "EUR", "split_json": "even"},
            {"payer_member_id": 2, "amount": 50, "currency": "EUR", "split_json": "even"}]
    assert su.settle(_MEMBERS, exps)["EUR"]["transfers"] == []


def test_settle_multi_currency_independent():
    exps = [{"payer_member_id": 1, "amount": 100, "currency": "EUR", "split_json": "even"},
            {"payer_member_id": 2, "amount": 80, "currency": "USD", "split_json": "even"}]
    res = su.settle(_MEMBERS, exps)
    assert set(res) == {"EUR", "USD"}
    assert res["USD"]["transfers"][0]["from"] == "Anna"  # Ben paid USD -> Anna owes


# --------------------------------------------------------------------------- #
# preflight — the one per-turn probe                                           #
# --------------------------------------------------------------------------- #
def _seed_ready(tmp_path):
    data = tmp_path / ".hermes" / "data" / "oteny-travel-talent"
    data.mkdir(parents=True)
    con = _make_db(data / "trips.db")
    today = datetime.now(timezone.utc).date()
    con.execute("INSERT INTO trips (id,name,destination,start_date,end_date,status,group_chat_id) "
                "VALUES (1,'Our Trip to Lisbon','Lisbon',?,?,'active','-100999')",
                ((today.replace(day=max(1, today.day))).isoformat(), today.isoformat()))
    con.execute("UPDATE trips SET start_date=date('now','-2 days'), end_date=date('now','+5 days')")
    con.execute("INSERT INTO members (trip_id,telegram_user,display_name,role) "
                "VALUES (1,'u_anna','Anna','lead')")
    con.execute("INSERT INTO itinerary (trip_id,day_date,time,title) VALUES (1,?, '19:30','Dinner')",
                (today.isoformat(),))
    con.execute("INSERT INTO todos (trip_id,member_id,title,done) VALUES (1,1,'Passport',0)")
    con.commit()
    con.close()
    (data / "profile.yaml").write_text(
        "home_city: Rotterdam\nhome_timezone: UTC\nlanguage: en\ndefault_currency: EUR\n")
    (data / "memory.md").write_text("- home airport is Schiphol\n")
    return data


def test_preflight_ready_surfaces_everything(tmp_path, monkeypatch, capsys):
    sandbox_env(monkeypatch, tmp_path)
    _seed_ready(tmp_path)
    assert pf.main() == 0
    out = capsys.readouterr().out
    assert "READY: yes" in out
    assert "Our Trip to Lisbon" in out and "Lisbon" in out      # active trip
    assert "Dinner" in out                                       # today's schedule
    assert "TODOS: 1 open" in out
    assert "Anna" in out                                         # roster (group-bound)
    assert "home airport is Schiphol" in out                    # domain memory


def test_preflight_overrides_flagged(tmp_path, monkeypatch, capsys):
    sandbox_env(monkeypatch, tmp_path)
    data = _seed_ready(tmp_path)
    (data / "overrides.md").write_text("## Rules\n- never auto-book\n")
    assert pf.main() == 0
    out = capsys.readouterr().out
    assert "OVERRIDES: yes" in out and "precedence" in out


def test_preflight_not_ready_without_profile(tmp_path, monkeypatch, capsys):
    sandbox_env(monkeypatch, tmp_path)
    data = tmp_path / ".hermes" / "data" / "oteny-travel-talent"
    data.mkdir(parents=True)
    _make_db(data / "trips.db").close()
    assert pf.main() == 0
    out = capsys.readouterr().out
    assert "READY: no" in out and "profile(file missing)" in out


def test_preflight_empty_box_is_robust(tmp_path, monkeypatch, capsys):
    sandbox_env(monkeypatch, tmp_path)
    assert pf.main() == 0
    out = capsys.readouterr().out
    assert "READY: no" in out and "db(file missing)" in out


# --------------------------------------------------------------------------- #
# trip_card — the visual (matplotlib gated)                                    #
# --------------------------------------------------------------------------- #
def test_trip_card_renders(tmp_path):
    pytest.importorskip("matplotlib")
    card = load(TRAVEL / "trip-dashboard" / "scripts" / "trip_card.py", "tt_trip_card")
    db = tmp_path / "trips.db"
    con = _make_db(db)
    con.execute("INSERT INTO trips (id,name,destination,start_date,end_date,status) "
                "VALUES (1,'Our Trip to Lisbon','Lisbon','2026-09-10','2026-09-14','planning')")
    con.execute("INSERT INTO members (id,trip_id,display_name,role) VALUES (1,1,'Anna','lead')")
    con.execute("INSERT INTO bookings (trip_id,kind,carrier,booking_ref,start_ts,status,monitor) "
                "VALUES (1,'flight','TAP','TP661','2026-09-10T09:40','on-time',1)")
    con.execute("INSERT INTO expenses (trip_id,payer_member_id,amount,currency,split_json) "
                "VALUES (1,1,100,'EUR','even')")
    con.execute("INSERT INTO todos (trip_id,member_id,title,done) VALUES (1,1,'Passport',0)")
    con.commit()
    con.close()
    prof = tmp_path / "profile.yaml"
    prof.write_text("default_currency: EUR\n")
    rc = card.main(["--trip", "1", "--db", str(db), "--profile", str(prof),
                    "--out-dir", str(tmp_path / "out")])
    assert rc == 0
    pngs = list((tmp_path / "out").glob("oteny_trip_1_*.png"))
    assert len(pngs) == 1 and pngs[0].stat().st_size > 0


# --------------------------------------------------------------------------- #
# maplink — the deterministic deeplink builder (the deeplink-first transit fix) #
# --------------------------------------------------------------------------- #
def test_maplink_google_encoding_olvg_example():
    """The prod-incident route (OLVG Oost -> Haarlemmermeerstraat 6) must encode exactly:
    comma -> %2C, space -> %20, the travelmode carried through."""
    url = ml.google_dir("OLVG Oost, Amsterdam", "Haarlemmermeerstraat 6, Amsterdam", "transit")
    assert url == (
        "https://www.google.com/maps/dir/?api=1"
        "&origin=OLVG%20Oost%2C%20Amsterdam"
        "&destination=Haarlemmermeerstraat%206%2C%20Amsterdam"
        "&travelmode=transit")
    # mode carries through; an unknown mode falls back to transit (the OV core)
    assert "travelmode=driving" in ml.google_dir("A", "B", "driving")
    assert "travelmode=walking" in ml.google_dir("A", "B", "walking")
    assert "travelmode=transit" in ml.google_dir("A", "B", "bogus")


def test_maplink_nl_slug_forms():
    """A numbered address -> adres-<street>-<number>-<city>; a named stop -> station-<name>;
    both lowercase, spaces -> '-'."""
    assert ml.slugify_place("Haarlemmermeerstraat 6, Amsterdam") == \
        "adres-haarlemmermeerstraat-6-amsterdam"
    assert ml.slugify_place("OLVG Oost, Amsterdam") == "station-olvg-oost-amsterdam"
    assert ml.slugify_place("Amsterdam Centraal") == "station-amsterdam-centraal"
    # a house number with a letter suffix is still an address
    assert ml.slugify_place("Kalverstraat 92a, Amsterdam") == \
        "adres-kalverstraat-92a-amsterdam"
    # the 9292 route + departures URLs are built from the slugs
    assert ml.nine292_route("OLVG Oost, Amsterdam", "Haarlemmermeerstraat 6, Amsterdam") == (
        "https://9292.nl/reisadvies/station-olvg-oost-amsterdam/"
        "adres-haarlemmermeerstraat-6-amsterdam")
    assert ml.nine292_departures("Amsterdam Centraal") == (
        "https://9292.nl/locaties/station-amsterdam-centraal/departures")


def test_maplink_default_set_is_google_plus_9292_no_apple():
    """Default (NL transit): Google + 9292 route + 9292 live departures; Apple OFF."""
    links = dict(ml.build_links(origin="OLVG Oost, Amsterdam",
                                destination="Haarlemmermeerstraat 6, Amsterdam",
                                mode="transit"))
    assert set(links) == {"Google Maps", "9292 (NL)", "9292 live departures"}
    assert "Apple Maps" not in links
    assert links["9292 live departures"].endswith("/departures")


def test_maplink_apple_only_on_opt_in():
    no_apple = dict(ml.build_links(origin="A", destination="B", mode="transit"))
    assert "Apple Maps" not in no_apple
    with_apple = dict(ml.build_links(origin="A", destination="B", mode="transit",
                                     apple=True))
    assert with_apple["Apple Maps"].startswith("https://maps.apple.com/directions?")


def test_maplink_non_nl_is_google_only():
    links = dict(ml.build_links(origin="Paris", destination="Lyon", mode="transit",
                                nl=False))
    assert set(links) == {"Google Maps"}


def test_maplink_never_emits_a_server_side_or_keyed_url():
    """HARD CONSTRAINT: only consumer deeplinks, never a Routes/OVapi/JSON/key-bearing URL,
    and never a departure CLOCK time baked into a link."""
    for label, url in ml.build_links(origin="A", destination="Amsterdam Centraal",
                                     mode="transit", apple=True):
        low = url.lower()
        assert "routes.googleapis" not in low and "ovapi" not in low
        assert "x-goog-api-key" not in low and "api_key=" not in low and "apikey=" not in low
        assert url.startswith(("https://www.google.com/maps/",
                               "https://9292.nl/", "https://maps.apple.com/"))
        # no consumer scheme carries a departure time; none of ours should claim one
        assert "departuretime=" not in low and "arrivaltime=" not in low


def test_maplink_main_prints_links(capsys):
    rc = ml.main(["--origin", "OLVG Oost, Amsterdam",
                  "--destination", "Haarlemmermeerstraat 6, Amsterdam", "--mode", "transit"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Google Maps: https://www.google.com/maps/dir/?api=1" in out
    assert "9292.nl/reisadvies/" in out
    assert "/departures" in out
    assert "maps.apple.com" not in out          # Apple off by default


# --------------------------------------------------------------------------- #
# guardrail invariants — the new HARD RULES + deeplink wiring must be present   #
# --------------------------------------------------------------------------- #
def test_maplink_ships_and_is_referenced():
    """The deterministic builder ships in scripts/ and is wired into the reply path
    (SKILL.md + the transit/bookings references), per the deeplink-first fix."""
    assert (TRAVEL / "scripts" / "maplink.py").is_file()
    skill = (TRAVEL / "trip-planner" / "SKILL.md").read_text()
    transit = (TRAVEL / "trip-planner" / "references" / "transit.md").read_text()
    bookings = (TRAVEL / "trip-planner" / "references" / "bookings.md").read_text()
    for body in (skill, transit, bookings):
        assert "maplink.py" in body


def test_hard_rule_strings_present_in_skill():
    """The new mechanical HARD RULES the weak model must read are spelled out in SKILL.md."""
    skill = _flat((TRAVEL / "trip-planner" / "SKILL.md").read_text())
    # (a) deeplink on every getting-somewhere reply
    assert "ends with a real map deeplink" in skill
    # (b) never an AI image as a map
    assert "never generate an ai image as a map" in skill
    assert "image_generate" in skill
    # (c) anti-grind: one travel call, no web_search fallback, bounded budget
    assert "one `travel` call per route" in skill
    assert "never `web_search` a route" in skill
    assert "≤2 tool calls" in skill
    # (d) anti-fabrication of transit specifics
    assert "never invent a transit specific" in skill
    # (e) honest real-time
    assert "honest real-time" in skill
    assert "no made-up" in skill


def test_anti_fabrication_of_closures_in_disruption():
    dis = _flat((TRAVEL / "trip-planner" / "references" / "disruption.md").read_text())
    assert "only real if a live source says so" in dis
    assert "never invent a network change" in dis


def test_anti_sycophancy_voice_rule():
    voice = _flat((TRAVEL / "travel-concierge-voice" / "SKILL.md").read_text())
    assert "ratify a user's guess" in voice
    assert "agreement is **not** verification".lower().replace("**", "") in \
        voice.replace("**", "")


def test_image_generate_map_ban_cross_noted_in_dashboard():
    dash = _flat((TRAVEL / "trip-dashboard" / "SKILL.md").read_text())
    assert "never use `image_generate` for a map or route" in dash
    assert "deterministic data render" in dash          # the allowed distinction


def test_false_maps_api_premise_is_gone():
    """T0.8: the bug-written-down line ('No structured Maps API … grounding covers the whole
    surface') must be rewritten to the deeplink-first reality."""
    transit = (TRAVEL / "trip-planner" / "references" / "transit.md").read_text()
    assert "grounding covers the whole surface" not in transit
    assert "Deeplink-first" in transit


# --------------------------------------------------------------------------- #
# §CHECKOUT — the OVpay check-out reminder (offer, one-shot self-expiry, prefs) #
# --------------------------------------------------------------------------- #
def test_checkout_offer_section_exists_and_is_one_shot():
    raw = (TRAVEL / "trip-planner" / "references" / "checklists.md").read_text()
    cl = _flat(raw)
    assert "§checkout" in cl
    # it OFFERS, never imposes
    assert "offers, never imposes" in cl or "offer, never impose" in cl
    # the scheduled job is a ONE-SHOT that self-expires (reuses the talent's pattern)
    assert "one-shot" in cl and "self-expir" in cl
    assert "repeat: 1" in raw
    assert "zero idle cost" in cl
    # fires ~3 min before arrival
    assert "eta − ~3 min" in cl or "eta − 3 min" in cl or "eta - 3 min" in cl


def test_checkout_never_remind_preference_suppresses_offer():
    cl = _flat((TRAVEL / "trip-planner" / "references" / "checklists.md").read_text())
    # a recorded "never remind" preference stops the offer (subscription/cash)
    assert "never remind" in cl
    assert "say nothing" in cl
    # always-remind path schedules without re-asking
    assert "always remind" in cl


def test_checkout_offer_wired_into_transit_step():
    """The OFFER is the last step of a §TRANSIT answer (SKILL.md), per T0.9."""
    skill = _flat((TRAVEL / "trip-planner" / "SKILL.md").read_text())
    assert "check-out reminder" in skill
    assert "§checkout" in skill


def test_checkout_glossary_terms_present():
    gl = _flat((TRAVEL / "trip-planner" / "references" / "glossary.md").read_text())
    assert "uitchecken" in gl and "ovpay" in gl
    assert "default fare" in gl and "correction" in gl
