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
    # EVERY bundle that ships a selfcheck copy must match the canonical — derived by
    # glob, not a hand-kept list (a name-keyed list silently missed odoo-website).
    canon = _sha(SHARED / "selfcheck.py")
    copies = [p for p in sorted(CATALOG.glob("*/scripts/selfcheck.py"))
              if p.parts[-3] != "_shared"]
    assert len(copies) >= 5, f"expected the marketable bundles' copies, got {copies}"
    for p in copies:
        assert _sha(p) == canon, f"{p} drifted from skills/_shared/scripts/selfcheck.py"


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


def test_cron_jobs_pin_declared_lite_model(tmp_path):
    # W3/W5: every cron job pins the Talent's DECLARED per-job model (the crons: policy
    # in agent-profile.yaml) — cheap `lite`, NOT the owner's chat persona. An un-pinned
    # job would fire with an empty model and the router 400s (D40). The config model is
    # only the fallback for a job the policy doesn't pin.
    cfg = tmp_path / "config.yaml"
    cfg.write_text("model:\n  provider: router\n  model: builder\n")   # owner picked builder for chat
    model, provider = pc.read_model_provider(str(cfg))
    assert model == "builder" and provider == "router"
    p = pc.plan({"timezone": "Europe/Amsterdam"}, str(tmp_path / "nojobs.json"),
                model=model, provider=provider)   # reads the real FlatBelly crons: policy
    assert p["to_create"], "expected jobs to plan"
    for s in p["to_create"]:
        assert s.get("model") == "lite", s["name"]   # policy wins over the builder chat model
        assert s.get("provider") == "router"


def test_cron_model_fallback_when_no_policy(tmp_path):
    # A job with NO declared policy falls back to the config-read model — which MUST be a
    # persona alias the router accepts (never the raw OpenRouter slug, which 400s). With an
    # empty policy the fallback `assistant` is used, so a spec is never un-pinned.
    model, provider = pc.read_model_provider(str(tmp_path / "absent.yaml"))
    assert model == "assistant" and provider == "router"
    for s in pc.build_specs({"timezone": "Europe/Amsterdam"}, cron_policy={}):
        assert s["model"] == "assistant" and s["provider"] == "router"


def test_cron_schedule_is_local_wall_clock():
    # W3 tz fix: the scheduler evaluates a cron expr in the tenant's configured timezone
    # (config.yaml timezone → hermes_time.now()), NOT UTC — so the schedule is the local
    # wall-clock verbatim. The prior UTC conversion fired reminders off by the UTC offset.
    assert pc.local_cron(8, 0) == "0 8 * * *"
    assert pc.local_cron(20, 0) == "0 20 * * *"
    assert pc.local_cron(12, 0, dow=0) == "0 12 * * 0"
    # DST-invariant: the schedule string has no offset, so it never drifts across DST.
    prof = {"timezone": "Europe/Amsterdam",
            "reminders": {"morning": "08:00", "evening": "20:00"}}
    specs = {s["name"]: s for s in pc.build_specs(prof)}
    assert specs["OtenyFlatBellyTalent daily morning log"]["schedule"] == "0 8 * * *"
    assert specs["OtenyFlatBellyTalent daily evening log"]["schedule"] == "0 20 * * *"


def test_cron_daily_reminders_are_rich_status_summaries():
    # v1.2.0 restore: the daily reminders load food-tracker and run the grounded
    # "day so far" summary (the ORIGINAL behavior — the v1.1.x zero-tool nudge was
    # a workaround for the since-fixed terminal-less cron cap + search_files
    # blindness, not a product choice). Cost steering stays via the crons: policy
    # (lite model + lean toolsets + declared max_turns), not via thinning.
    specs = {s["name"]: s for s in pc.build_specs({"timezone": "Europe/Amsterdam"})}
    for daily in ("OtenyFlatBellyTalent daily morning log",
                  "OtenyFlatBellyTalent daily evening log"):
        s = specs[daily]
        assert s["skills"] == ["food-tracker", "flatbelly-coach-voice"]
        assert "load food-tracker first" in s["prompt"].lower()
    assert specs["OtenyFlatBellyTalent weekly dashboard"]["skills"] == [
        "weight-progress-dashboard", "food-tracker"]


def test_cron_jobs_pin_their_tool_surface():
    # 2026-07-02 hh00067 runaway: a job that omits enabled_toolsets falls back to the
    # tenant's platform_toolsets.cron cap (NO terminal) while the skill demands script
    # execution — an impossible task the model flailed on for 90 iterations. So EVERY
    # job pins its tool surface from the crons: policy. The reminders pin the `no_mcp`
    # sentinel = ZERO tools (a literal [] is falsy upstream and would silently fall
    # back to the platform cap; `no_mcp` passes the truthiness gate and the MCP-merge
    # strips it, leaving a true empty allowlist — live-verified: the captured request
    # carries no tools array). The weekly declares exactly what its skill instructs.
    specs = {s["name"]: s for s in pc.build_specs({"timezone": "Europe/Amsterdam"})}
    for daily in ("OtenyFlatBellyTalent daily morning log",
                  "OtenyFlatBellyTalent daily evening log"):
        # v1.2.0: the rich summary runs preflight/sqlite (terminal), reads
        # references (skills) — exactly what the skill instructs, never less.
        assert specs[daily]["enabled_toolsets"] == ["terminal", "file", "skills"]
    assert specs["OtenyFlatBellyTalent weekly dashboard"]["enabled_toolsets"] == [
        "terminal", "file"]


def test_cron_policy_declares_toolsets_for_every_job():
    # The agent-profile crons: policy is the single source — every declared cron
    # carries a non-empty enabled_toolsets (an omitted one falls back to the platform
    # cap, re-opening the impossible-task class of bug).
    policy = pc.read_cron_policy()
    assert policy, "flatbelly crons: policy missing"
    for name, pol in policy.items():
        ets = pol.get("enabled_toolsets")
        assert isinstance(ets, list) and ets, f"{name} does not pin enabled_toolsets"


def test_cron_max_turns_declared_but_not_emitted_by_default():
    # W6: max_turns is declared in the crons: policy + linted, but only EMITTED to the
    # cronjob tool when a deployed Hermes honors a per-cron cap (no released version does
    # yet), so an older gateway never receives an unknown field.
    default = pc.build_specs({"timezone": "Europe/Amsterdam"})
    assert all("max_turns" not in s for s in default)
    emitted = {s["name"]: s for s in
               pc.build_specs({"timezone": "Europe/Amsterdam"}, emit_max_turns=True)}
    assert emitted["OtenyFlatBellyTalent daily morning log"]["max_turns"] == 15
    assert emitted["OtenyFlatBellyTalent weekly dashboard"]["max_turns"] == 15


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
