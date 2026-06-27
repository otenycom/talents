"""Integrity tests for the two Talent bundles (8.1 / 8.2 C2).

Asserts structural invariants the rubric depends on: the first-run section exists and
is mechanical; the shipped selfcheck copies match the canonical; the manifests parse
and selfcheck them; the canonical schema (init.sql + the SKILL.md inline DDL) creates
the five tables idempotently; the bundles are PII-clean; routing signatures line up.
"""
from __future__ import annotations

import hashlib
import re
import sqlite3
from datetime import datetime
from pathlib import Path

import pytest
import yaml

from _talents import CATALOG, SHARED, load

FLATBELLY = CATALOG / "oteny-flatbelly-talent"
STOCK = CATALOG / "oteny-stock-talent"
SHOPBOT = CATALOG / "oteny-shopbot-talent"


def _sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def test_shipped_selfcheck_matches_canonical():
    canon = _sha(SHARED / "selfcheck.py")
    assert _sha(FLATBELLY / "scripts" / "selfcheck.py") == canon
    assert _sha(STOCK / "scripts" / "selfcheck.py") == canon
    assert _sha(SHOPBOT / "scripts" / "selfcheck.py") == canon


# The hermeshost-internal default-skill canonical check (skill-translator /
# index-reconciler vs _shared) stays in hermeshost — those infra skills are not part of
# this public catalog. This file tests the marketable Talents.


@pytest.mark.parametrize("firstrun", [
    FLATBELLY / "food-tracker" / "references" / "first-run.md",
    STOCK / "references" / "first-run.md",
    SHOPBOT / "references" / "first-run.md",
])
def test_first_run_lives_in_references_and_is_mechanical(firstrun):
    # D57: the first-run drill moved OUT of the SKILL.md body into references/first-run.md
    # (pulled only when selfcheck = NOT-READY). It opens with the guard and registers
    # routing via the reconciler. (Command-hygiene — no improvised exec in fenced
    # commands — is enforced by the lint, see test_talent_authoring_lint.)
    text = firstrun.read_text()
    assert "selfcheck.py" in text                       # opens with the guard
    assert "index_reconciler.py" in text                # registers routing via the reconciler
    # no improvised exec inside a fenced command block (prose mentions are fine)
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            assert "python3 -c" not in line and "python -c" not in line
            assert "<<" not in line                     # no heredoc in a runnable block


def test_first_run_not_in_skill_body():
    # The fat first-run section + inline DDL are gone from the bodies (D57 lean bodies).
    for skill in (FLATBELLY / "food-tracker" / "SKILL.md", STOCK / "SKILL.md",
                  SHOPBOT / "SKILL.md"):
        text = skill.read_text()
        assert "First-run setup" not in text            # moved to references/first-run.md
        assert "CREATE TABLE" not in text               # schema lives in scripts/ (init.sql / setup_db.py)


@pytest.mark.parametrize("manifest", [
    FLATBELLY / "required_artifacts.yaml",
    STOCK / "required_artifacts.yaml",
    SHOPBOT / "required_artifacts.yaml",
])
def test_manifest_parses_and_selfchecks(manifest, monkeypatch, tmp_path):
    data = yaml.safe_load(manifest.read_text())
    assert data["bot"] and data["artifacts"]
    monkeypatch.setenv("HH_HOME", str(tmp_path))
    monkeypatch.setenv("HH_HERMES_HOME", str(tmp_path / ".hermes"))
    (tmp_path / ".hermes").mkdir(parents=True)
    sc = load(SHARED / "selfcheck.py", "sc_b")
    rep = sc.run(manifest)
    assert rep["ready"] is False  # bare sandbox -> not ready, but it ran cleanly


def test_routing_signature_matches_manifest():
    for bot in (FLATBELLY, STOCK, SHOPBOT):
        profile = yaml.safe_load((bot / "agent-profile.yaml").read_text())
        manifest = yaml.safe_load((bot / "required_artifacts.yaml").read_text())
        routing_artifact = [a for a in manifest["artifacts"] if a["kind"] == "routing"][0]
        assert profile["routing"]["signature"] == routing_artifact["signature"]


def _run_sql_file(db: Path, sql: str):
    con = sqlite3.connect(db)
    con.executescript(sql)
    con.commit()
    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    con.close()
    return tables


def test_init_sql_creates_five_tables_idempotently(tmp_path):
    sql = (FLATBELLY / "scripts" / "init.sql").read_text()
    db = tmp_path / "food.db"
    t1 = _run_sql_file(db, sql)
    assert {"meals", "weight", "daily_metrics", "workouts", "waist"} <= t1
    # idempotent: re-running raises nothing and yields the same set
    t2 = _run_sql_file(db, sql)
    assert t1 == t2


def test_food_tracker_first_run_applies_declared_init_sql():
    """First-run creates the schema by RUNNING the shipped init.sql (declared,
    approval-clean) — not by pasting an inline CREATE TABLE block (D57)."""
    fr = (FLATBELLY / "food-tracker" / "references" / "first-run.md").read_text()
    assert "scripts/init.sql" in fr                    # the single executable schema
    assert "sqlite3" in fr                             # applied via the sqlite3 CLI
    assert "< ~/.hermes/skills/talents/oteny-flatbelly-talent/scripts/init.sql" in fr  # redirection, not -c
    # the executable schema itself still creates the five tables (covered in detail by
    # test_init_sql_creates_five_tables_idempotently).


def test_morning_filter_is_language_independent(tmp_path):
    """The morning-only trend filter must key on the canonical `period` column, not on
    localized note text — else a non-English tenant's morning weigh-ins are dropped."""
    db = tmp_path / "food.db"
    _run_sql_file(db, (FLATBELLY / "scripts" / "init.sql").read_text())
    con = sqlite3.connect(db)
    con.executescript(
        "INSERT INTO weight (date, weight_kg, period, notes) VALUES"
        " ('2026-06-01', 100.0, 'morning', 'le matin, à jeun'),"   # French note, morning
        " ('2026-06-02',  99.5, NULL,      'σήμερα'),"             # Greek note, period unset -> morning
        " ('2026-06-03', 101.2, 'evening', 'после ужина');")       # Russian note, evening
    con.commit()
    rows = con.execute(
        "SELECT date FROM weight WHERE COALESCE(period,'morning')='morning' ORDER BY date").fetchall()
    con.close()
    got = [r[0] for r in rows]
    assert got == ["2026-06-01", "2026-06-02"], got   # evening excluded; localized notes irrelevant


def test_no_language_coded_data_filter_remains():
    """No SQL/python in the bundle may filter weights on localized note text."""
    offenders = []
    for f in FLATBELLY.rglob("*"):
        if f.suffix in (".md", ".py", ".sql") and f.name != "PLAN.md":
            txt = f.read_text().lower()
            if "like 'ochtend" in txt or 'startswith("ochtend"' in txt:
                offenders.append(str(f))
    assert not offenders, offenders


def test_bundles_are_pii_clean():
    pii = re.compile(
        r"\bRies\b|ALAT 91|HDL 0\.9|aspirin|prescan|life-cvd|atal-medial"
        r"|apify_api|DEFAULT_TOKEN|8799761609|-4936433409|-5249654892|\bArjen\b|XAI_API_KEY",
    )
    for bot in (FLATBELLY, STOCK, SHOPBOT):
        for f in bot.rglob("*"):
            if f.suffix in (".md", ".yaml", ".py", ".sql") and f.name != "PLAN.md":
                hits = [ln for ln in f.read_text().splitlines() if pii.search(ln)]
                assert not hits, f"PII in {f}: {hits[:2]}"


def test_no_token_in_transcript_store():
    # Transcription uses the always-available youtube_transcript tool; this script only
    # persists what the tool returned — so it must carry no token and no network fetch.
    store = (STOCK / "all-in-transcripts" / "scripts" / "store_transcript.py").read_text()
    assert "apify_api_" not in store and "DEFAULT_TOKEN" not in store
    assert "youtube_transcript" in store  # documents the live tool as the fetch source


# ---- provision_cron planner ----
pc = load(FLATBELLY / "scripts" / "provision_cron.py", "pc_cron")


def test_cron_plan_three_jobs_listfirst(tmp_path):
    profile = {"timezone": "Europe/Amsterdam",
               "reminders": {"morning": "08:00", "evening": "20:00", "weekly_dashboard": "Sun 12:00"}}
    p = pc.plan(profile, str(tmp_path / "nojobs.json"), ref=datetime(2026, 7, 1))
    names = [s["name"] for s in p["to_create"]]
    assert names == ["OtenyFlatBellyTalent daily morning log",
                     "OtenyFlatBellyTalent daily evening log",
                     "OtenyFlatBellyTalent weekly dashboard"]
    # list-first: an already-registered job is excluded
    jobs = tmp_path / "jobs.json"
    jobs.write_text('{"jobs": [{"name": "OtenyFlatBellyTalent daily morning log"}]}')
    p2 = pc.plan(profile, str(jobs), ref=datetime(2026, 7, 1))
    assert "OtenyFlatBellyTalent daily morning log" in p2["existing"]
    assert len(p2["to_create"]) == 2


def test_cron_jobs_pin_model_and_provider(tmp_path):
    # Every cron job MUST carry a model+provider — an un-pinned job fires with an
    # empty model and the router 400s (D40: scheduler reads model.default, not
    # model.model). The planner reads them from config.yaml.
    # config.yaml carries the persona alias `assistant` (what render_config_yaml
    # writes) — NOT the raw OpenRouter slug, which the router rejects (D55).
    cfg = tmp_path / "config.yaml"
    cfg.write_text("model:\n  provider: router\n  model: assistant\n")
    model, provider = pc.read_model_provider(str(cfg))
    assert model == "assistant" and provider == "router"
    p = pc.plan({"timezone": "Europe/Amsterdam"}, str(tmp_path / "nojobs.json"),
                model=model, provider=provider, ref=datetime(2026, 7, 1))
    assert p["to_create"], "expected jobs to plan"
    for s in p["to_create"]:
        assert s.get("model") == "assistant"
        assert s.get("provider") == "router"


def test_cron_model_provider_fallback_when_no_config(tmp_path):
    # Missing/unreadable config still yields a working model+provider, never empty —
    # and the fallback MUST be a persona alias the router accepts (never the raw
    # OpenRouter slug, which 400s as `unknown model`). Cron routes to `assistant`.
    model, provider = pc.read_model_provider(str(tmp_path / "absent.yaml"))
    assert model == "assistant" and provider == "router"
    for s in pc.build_specs({"timezone": "Europe/Amsterdam"}, ref=datetime(2026, 7, 1)):
        assert s["model"] == "assistant" and s["provider"] == "router"


def test_cron_utc_conversion_summer_offset():
    # CEST (UTC+2): 08:00 local -> 06:00 UTC; Sun 12:00 -> 10:00 UTC ("0 10 * * 0")
    assert pc.utc_cron(8, 0, "Europe/Amsterdam", ref=datetime(2026, 7, 1)) == "0 6 * * *"
    assert pc.utc_cron(12, 0, "Europe/Amsterdam", dow=0, ref=datetime(2026, 7, 1)) == "0 10 * * 0"
    # CET (UTC+1): 08:00 local -> 07:00 UTC
    assert pc.utc_cron(8, 0, "Europe/Amsterdam", ref=datetime(2026, 1, 1)) == "0 7 * * *"


# ---- D34: data relocation + per-bot memory split ----

def test_memory_split_per_bot_domain_and_shared_identity():
    """Each bot declares a shared identity USER.md AND a per-bot domain memory.md
    (non-blocking — domain memory accrues, it never gates coaching)."""
    for bot, datadir in ((FLATBELLY, "oteny-flatbelly-talent"), (STOCK, "oteny-stock-talent"),
                         (SHOPBOT, "oteny-shopbot-talent")):
        manifest = yaml.safe_load((bot / "required_artifacts.yaml").read_text())
        mems = [a for a in manifest["artifacts"] if a["kind"] == "memory"]
        paths = {a["path"] for a in mems}
        assert "~/.hermes/memories/USER.md" in paths           # shared identity
        assert f"~/.hermes/data/{datadir}/memory.md" in paths  # per-bot domain
        domain = next(a for a in mems if a["path"].endswith("memory.md"))
        assert domain.get("blocking") is False
        assert (bot / "profile" / "memory.md.template").exists()  # ships the seed


def test_identity_usermd_template_is_bot_agnostic():
    """The shared USER.md (auto-loaded into EVERY session) must stay identity-only —
    no per-bot domain leaks into the global memory (D34)."""
    txt = (FLATBELLY / "profile" / "USER.md.template").read_text().lower()
    for domain_term in ("leucine", "waist", "protein", "goal_weight", "food.db"):
        assert domain_term not in txt, domain_term


def test_data_relocated_under_hermes_home_no_root_paths_remain():
    """Per-bot data lives under ~/.hermes/data/<bot>/; no ~/<bot>/ data path may
    linger in a bundle (it would escape the ~/.hermes snapshot)."""
    for bot in (FLATBELLY, STOCK):
        for f in bot.rglob("*"):
            if f.suffix in (".md", ".yaml", ".py", ".sql", ".template") and f.name != "PLAN.md":
                txt = f.read_text()
                assert "~/oteny-flatbelly-talent/" not in txt, f
                assert "~/oteny-stock-talent/" not in txt, f
