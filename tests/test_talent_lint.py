"""Tests for the versioning + migration-shape lint additions (P2).

The version check is stdlib (regex over agent-profile.yaml); the migration-shape check
needs PyYAML (present here); the cross-version coherence (forgotten bump / mutated id) is a
pure function exercised directly and via the --against CLI.
"""
from __future__ import annotations

from pathlib import Path

from _talents import CATALOG, load

lint = load(CATALOG / "talent-authoring-standard" / "scripts" / "lint_upgrade_safe.py", "lint")

FLATBELLY = CATALOG / "oteny-flatbelly-talent"


def _talent(root: Path, *, version_line: str | None = "version: 1.2.3",
            migrations: str | None = None, artifacts: str = "artifacts: []",
            neutralize: str | None = None, profile_extra: str = "") -> Path:
    """A minimal Talent bundle (has required_artifacts.yaml -> is_talent)."""
    b = root / "oteny-x-talent"
    b.mkdir(parents=True, exist_ok=True)
    (b / "required_artifacts.yaml").write_text("bot: oteny-x-talent\n" + artifacts + "\n")
    prof = "bot: oteny-x-talent\n" + profile_extra
    if version_line is not None:
        prof += version_line + "\n"
    (b / "agent-profile.yaml").write_text(prof)
    if migrations is not None:
        (b / "migrations.yaml").write_text(migrations)
    if neutralize is not None:
        (b / "neutralize.yaml").write_text(neutralize)
    return b


_CRON_ARTIFACT = (
    "artifacts:\n  - kind: cron\n    jobs_path: ~/.hermes/cron/jobs.json\n"
    "    jobs:\n      - \"OtenyX daily nudge\"\n")


# --------------------------------------------------------------------------- #
# version (check 11)                                                            #
# --------------------------------------------------------------------------- #
def test_read_profile_version_strips_inline_comment(tmp_path):
    b = _talent(tmp_path, version_line="version: 1.0.0   # a label over the commit")
    assert lint.read_profile_version(b) == "1.0.0"


def test_missing_version_is_a_finding(tmp_path):
    b = _talent(tmp_path, version_line=None)
    assert any("no `version:`" in f for f in lint.lint_bundle(b))


def test_invalid_semver_is_a_finding(tmp_path):
    b = _talent(tmp_path, version_line="version: v1")
    assert any("not valid semver" in f for f in lint.lint_bundle(b))


def test_valid_version_no_migrations_is_clean(tmp_path):
    b = _talent(tmp_path)
    assert lint.lint_bundle(b) == []


# --------------------------------------------------------------------------- #
# migration shape (check 12)                                                    #
# --------------------------------------------------------------------------- #
def test_flatbelly_migrations_are_well_shaped():
    # the shipped reference migration passes the structural check
    assert lint._migration_shape_findings(FLATBELLY) == []


def test_sql_migration_without_db_is_a_finding(tmp_path):
    b = _talent(tmp_path, migrations=(
        "migrations:\n  - id: 0002_x\n    kind: sql\n    sql: \"CREATE TABLE t(id INT)\"\n"))
    assert any("no top-level `db:`" in f for f in lint.lint_bundle(b))


def test_sql_migration_without_body_is_a_finding(tmp_path):
    b = _talent(tmp_path, migrations="db: x.db\nmigrations:\n  - id: 0002_x\n    kind: sql\n")
    assert any("no `sql` body" in f for f in lint.lint_bundle(b))


def test_checklist_migration_without_ref_is_a_finding(tmp_path):
    b = _talent(tmp_path, migrations="migrations:\n  - id: 0002_x\n    kind: checklist\n")
    assert any("no `ref`" in f for f in lint.lint_bundle(b))


def test_duplicate_migration_id_is_a_finding(tmp_path):
    b = _talent(tmp_path, migrations=(
        "db: x.db\nmigrations:\n"
        "  - id: 0002_x\n    kind: sql\n    sql: \"CREATE TABLE a(id INT)\"\n"
        "  - id: 0002_x\n    kind: sql\n    sql: \"CREATE TABLE b(id INT)\"\n"))
    assert any("duplicate id" in f for f in lint.lint_bundle(b))


def test_unknown_kind_is_a_finding(tmp_path):
    b = _talent(tmp_path, migrations="migrations:\n  - id: 0002_x\n    kind: bogus\n")
    assert any("must be 'sql' or 'checklist'" in f for f in lint.lint_bundle(b))


# --------------------------------------------------------------------------- #
# cross-version coherence (the forgotten-bump / mutated-id footguns)            #
# --------------------------------------------------------------------------- #
def test_new_migration_without_bump_fails():
    out = lint.check_upgrade_coherence(
        {"version": "1.0.0", "migration_ids": ["0002_a"]},
        {"version": "1.0.0", "migration_ids": ["0002_a", "0003_b"]},
    )
    assert any("without a version bump" in f for f in out)


def test_new_migration_patch_only_bump_fails():
    out = lint.check_upgrade_coherence(
        {"version": "1.0.0", "migration_ids": ["0002_a"]},
        {"version": "1.0.1", "migration_ids": ["0002_a", "0003_b"]},
    )
    assert any("MINOR or MAJOR" in f for f in out)


def test_new_migration_with_minor_bump_is_clean():
    out = lint.check_upgrade_coherence(
        {"version": "1.0.0", "migration_ids": ["0002_a"]},
        {"version": "1.1.0", "migration_ids": ["0002_a", "0003_b"]},
    )
    assert out == []


def test_renumbered_id_fails():
    out = lint.check_upgrade_coherence(
        {"version": "1.0.0", "migration_ids": ["0002_a"]},
        {"version": "2.0.0", "migration_ids": ["0002_renamed"]},
    )
    assert any("not append-only" in f for f in out)


def test_first_publish_is_clean():
    out = lint.check_upgrade_coherence(
        {"version": None, "migration_ids": []},
        {"version": "1.0.0", "migration_ids": ["0002_a"]},
    )
    assert out == []


def test_non_migration_change_any_bump_ok():
    out = lint.check_upgrade_coherence(
        {"version": "1.0.0", "migration_ids": ["0002_a"]},
        {"version": "1.0.1", "migration_ids": ["0002_a"]},   # patch bump, no new migration
    )
    assert out == []


# --------------------------------------------------------------------------- #
# the --against CLI wires coherence into the gate                               #
# --------------------------------------------------------------------------- #
def test_against_cli_catches_forgotten_bump(tmp_path):
    prior = _talent(tmp_path / "prior", version_line="version: 1.0.0",
                    migrations="db: x.db\nmigrations:\n  - id: 0002_a\n    kind: sql\n    sql: \"CREATE TABLE a(id INT)\"\n")
    cur = _talent(tmp_path / "cur", version_line="version: 1.0.0",
                  migrations=("db: x.db\nmigrations:\n"
                              "  - id: 0002_a\n    kind: sql\n    sql: \"CREATE TABLE a(id INT)\"\n"
                              "  - id: 0003_b\n    kind: sql\n    sql: \"CREATE TABLE b(id INT)\"\n"))
    rc = lint.main([str(cur), "--against", str(prior)])
    assert rc == 1


# --------------------------------------------------------------------------- #
# neutralize safety (check 13) — an outbound-action Talent must de-fang clones   #
# --------------------------------------------------------------------------- #
def test_required_crons_without_neutralize_is_a_finding(tmp_path):
    b = _talent(tmp_path, artifacts=_CRON_ARTIFACT)
    assert any("ships no neutralize.yaml" in f for f in lint.lint_bundle(b))


def test_seam_without_neutralize_is_a_finding(tmp_path):
    b = _talent(tmp_path, profile_extra="seam:\n  base: crewradar\n")
    assert any("legacy seam" in f and "neutralize.yaml" in f for f in lint.lint_bundle(b))


def test_odoo_connection_without_neutralize_is_a_finding(tmp_path):
    b = _talent(tmp_path, profile_extra=(
        "connections:\n  crewradar:\n    kind: odoo\n    uplink_user: bot\n"
        "    odoo_grants: {read: [res.partner], write: []}\n"))
    assert any("named connections" in f and "neutralize.yaml" in f for f in lint.lint_bundle(b))


def test_portal_connection_without_neutralize_is_a_finding(tmp_path):
    b = _talent(tmp_path, profile_extra=(
        "connections:\n  portal:\n    kind: portal\n"
        "    real_url: https://permits.example.org\n"
        "    fence_hosts: [permits.example.org]\n"))
    assert any("named connections" in f and "neutralize.yaml" in f for f in lint.lint_bundle(b))


def test_self_contained_talent_needs_no_neutralize(tmp_path):
    # no required crons, no seam -> neutralize.yaml is not required
    b = _talent(tmp_path)
    assert not any("neutralize" in f for f in lint.lint_bundle(b))


def test_neutralize_covering_all_required_crons_is_clean(tmp_path):
    b = _talent(tmp_path, artifacts=_CRON_ARTIFACT, neutralize=(
        "bot: oteny-x-talent\nsteps:\n  - id: 0001_crons\n    kind: crons\n"
        "    crons:\n      disable:\n        - \"OtenyX daily nudge\"\n"))
    assert not any("neutralize" in f for f in lint.lint_bundle(b))


def test_neutralize_missing_a_required_cron_is_a_finding(tmp_path):
    b = _talent(tmp_path, artifacts=_CRON_ARTIFACT, neutralize=(
        "bot: oteny-x-talent\nsteps:\n  - id: 0001_crons\n    kind: crons\n"
        "    crons:\n      disable:\n        - \"OtenyX some other job\"\n"))
    assert any("does not disable every required cron" in f for f in lint.lint_bundle(b))


def test_malformed_neutralize_is_a_finding(tmp_path):
    b = _talent(tmp_path, artifacts=_CRON_ARTIFACT,
                neutralize="bot: oteny-x-talent\nsteps:\n  - kind: crons\n")  # step has no id
    assert any("steps[0] has no `id`" in f for f in lint.lint_bundle(b))


def test_neutralize_sql_step_without_db_is_a_finding(tmp_path):
    b = _talent(tmp_path, profile_extra="seam:\n  base: crewradar\n", neutralize=(
        "bot: oteny-x-talent\nsteps:\n  - id: 0001_seam\n    kind: sql\n"
        "    sql: \"UPDATE seam SET url='staging'\"\n"))
    assert any("no `db:`" in f for f in lint.lint_bundle(b))


def test_flatbelly_neutralize_is_well_shaped():
    assert lint._neutralize_findings(FLATBELLY) == []


# --------------------------------------------------------------------------- #
# scheduled-cron cost policy (check 14)                                         #
# --------------------------------------------------------------------------- #
def _crons(policy_yaml: str) -> str:
    """A profile_extra `crons:` block (prepended into the test talent's agent-profile)."""
    return "crons:\n" + policy_yaml


def test_required_cron_without_policy_is_a_finding(tmp_path):
    b = _talent(tmp_path, artifacts=_CRON_ARTIFACT)   # required cron, no crons: policy
    assert any("no cost policy" in f for f in lint.lint_bundle(b))


def test_cron_without_max_turns_is_a_finding(tmp_path):
    b = _talent(tmp_path, artifacts=_CRON_ARTIFACT, profile_extra=_crons(
        '  - name: "OtenyX daily nudge"\n    frequency: daily\n    model: lite\n'))
    assert any("bound the turn" in f for f in lint.lint_bundle(b))


def test_daily_cron_above_lite_without_justification_is_a_finding(tmp_path):
    b = _talent(tmp_path, artifacts=_CRON_ARTIFACT, profile_extra=_crons(
        '  - name: "OtenyX daily nudge"\n    frequency: daily\n    model: builder\n    max_turns: 4\n'))
    assert any("model_justification" in f for f in lint.lint_bundle(b))


def test_daily_cron_above_lite_with_justification_is_clean(tmp_path):
    b = _talent(tmp_path, artifacts=_CRON_ARTIFACT, profile_extra=_crons(
        '  - name: "OtenyX daily nudge"\n    frequency: daily\n    model: builder\n'
        '    max_turns: 4\n    model_justification: "weekly board synthesis needs Sonnet"\n'))
    assert not any("model_justification" in f for f in lint.lint_bundle(b))


def test_daily_lite_cron_needs_no_justification(tmp_path):
    b = _talent(tmp_path, artifacts=_CRON_ARTIFACT, profile_extra=_crons(
        '  - name: "OtenyX daily nudge"\n    frequency: daily\n    model: lite\n    max_turns: 3\n'))
    findings = lint.lint_bundle(b)
    assert not any("model_justification" in f for f in findings)
    assert not any("bound the turn" in f for f in findings)
    assert not any("no cost policy" in f for f in findings)


def test_weekly_cron_above_lite_needs_no_justification(tmp_path):
    # weekly is not daily-or-more, so a costlier persona needs no written justification
    b = _talent(tmp_path, artifacts=_CRON_ARTIFACT, profile_extra=_crons(
        '  - name: "OtenyX daily nudge"\n    frequency: weekly\n    model: builder\n    max_turns: 15\n'))
    assert not any("model_justification" in f for f in lint.lint_bundle(b))


def test_orphan_cron_policy_name_is_a_finding(tmp_path):
    # a crons: entry naming a job not declared in required_artifacts jobs: is name drift
    b = _talent(tmp_path, artifacts=_CRON_ARTIFACT, profile_extra=_crons(
        '  - name: "OtenyX daily nudge"\n    frequency: daily\n    model: lite\n    max_turns: 3\n'
        '  - name: "OtenyX typo job"\n    frequency: daily\n    model: lite\n    max_turns: 3\n'))
    assert any("name drift" in f for f in lint.lint_bundle(b))


def test_flatbelly_cron_policy_is_clean():
    # the shipped FlatBelly bundle satisfies the scheduled-cron cost policy
    assert lint._cron_policy_findings(FLATBELLY) == []


# --------------------------------------------------------------------------- #
# requires: substrate ↔ min_tier consistency (check 15)                         #
# --------------------------------------------------------------------------- #
def test_requires_vm_with_max_is_clean(tmp_path):
    b = _talent(tmp_path, profile_extra="requires:\n  substrate: vm\n  min_tier: max\n")
    assert not any("requires" in f for f in lint.lint_bundle(b))


def test_requires_vm_without_max_is_a_finding(tmp_path):
    # substrate: vm needs min_tier: max (the cheapest tier that provides a VM, D204)
    b = _talent(tmp_path, profile_extra="requires:\n  substrate: vm\n  min_tier: power\n")
    assert any("min_tier: max" in f for f in lint.lint_bundle(b))


def test_requires_unknown_substrate_is_a_finding(tmp_path):
    b = _talent(tmp_path, profile_extra="requires:\n  substrate: bogus\n  min_tier: max\n")
    assert any("substrate" in f and "not one of" in f for f in lint.lint_bundle(b))


def test_requires_unknown_min_tier_is_a_finding(tmp_path):
    b = _talent(tmp_path, profile_extra="requires:\n  substrate: container\n  min_tier: mega\n")
    assert any("min_tier" in f and "not one of" in f for f in lint.lint_bundle(b))


def test_requires_min_tier_without_substrate_is_a_finding(tmp_path):
    b = _talent(tmp_path, profile_extra="requires:\n  min_tier: max\n")
    assert any("without requires.substrate" in f for f in lint.lint_bundle(b))


def test_no_requires_block_is_clean(tmp_path):
    b = _talent(tmp_path)
    assert not any("requires" in f for f in lint.lint_bundle(b))


def test_odoo_website_requires_block_is_clean():
    # the shipped flagship declares requires: {substrate: vm, min_tier: max} — consistent.
    assert lint._requires_findings(CATALOG / "odoo-website") == []


def test_all_real_talents_lint_clean():
    # Marker-derived, not name-derived: a publishable bundle is anything shipping an
    # agent-profile.yaml (the `*-talent` suffix glob silently missed odoo-website).
    bundles = [str(p.parent) for p in sorted(CATALOG.glob("*/agent-profile.yaml"))]
    assert len(bundles) >= 5
    assert lint.main(bundles) == 0


# --------------------------------------------------------------------------- #
# per-task model escalation (check 16 — task_escalations)                       #
# --------------------------------------------------------------------------- #
_SKILLS = "skills:\n  - alpha\n  - beta\n"


def _esc(root, entries: str):
    return _talent(root, profile_extra=_SKILLS + "task_escalations:\n" + entries)


def test_valid_task_escalation_is_clean(tmp_path):
    b = _esc(tmp_path, "  - {task: live-inventory, model_tier: builder, "
                       "skills: [alpha], model_tier_reason: fabrication-prone}\n")
    assert not any("task_escalations" in f for f in lint.lint_bundle(b))


def test_task_escalation_missing_reason_fails(tmp_path):
    b = _esc(tmp_path, "  - {task: x, model_tier: builder, skills: [alpha]}\n")
    assert any("model_tier_reason` is required" in f for f in lint.lint_bundle(b))


def test_task_escalation_unknown_skill_fails(tmp_path):
    b = _esc(tmp_path, "  - {task: x, model_tier: builder, skills: [zzz], "
                       "model_tier_reason: r}\n")
    assert any("is not one this bundle ships" in f for f in lint.lint_bundle(b))


def test_task_escalation_non_builder_tier_fails(tmp_path):
    # v1 narrowing: researcher is never an automatic escalation target.
    b = _esc(tmp_path, "  - {task: x, model_tier: researcher, skills: [alpha], "
                       "model_tier_reason: r}\n")
    assert any("must be one of ['builder']" in f for f in lint.lint_bundle(b))


def test_task_escalation_floor_smuggling_fails(tmp_path):
    # covering EVERY skill in the bundle is a bundle-wide floor by another name.
    b = _esc(tmp_path, "  - {task: x, model_tier: builder, skills: [alpha, beta], "
                       "model_tier_reason: r}\n")
    assert any("floor in disguise" in f for f in lint.lint_bundle(b))


def test_task_escalation_allowed_on_baked_bundle(tmp_path):
    # deliberately UNLIKE the model_tier floor ban: a task escalation never raises the
    # fleet base persona, so it is legal on a baked (fleet-wide) bundle.
    b = _talent(tmp_path, profile_extra="delivery: baked\n" + _SKILLS +
                "task_escalations:\n  - {task: live-inventory, model_tier: builder, "
                "skills: [alpha], model_tier_reason: fabrication-prone}\n")
    assert not any("task_escalations" in f for f in lint.lint_bundle(b))


def test_no_task_escalations_block_is_clean(tmp_path):
    b = _talent(tmp_path, profile_extra=_SKILLS)
    assert not any("task_escalations" in f for f in lint.lint_bundle(b))


def test_travel_talent_declares_a_valid_escalation():
    # the shipped travel Talent's live-inventory → builder (trip-planner) declaration is clean.
    assert lint._task_escalation_findings(CATALOG / "oteny-travel-talent") == []


# --------------------------------------------------------------------------- #
# selector-manifest ↔ human-doc twin gate (check 17)                            #
# --------------------------------------------------------------------------- #
def _twin_bundle(root: Path, *, manifest: str, doc: str | None,
                 doc_name: str = "form-selectors.md") -> Path:
    """A Talent bundle shipping a selector manifest (+ optional human-doc twin) under
    references/, plus a SKILL.md so the soft-warning path is reachable."""
    b = _talent(root, profile_extra=_SKILLS)
    refs = b / "filing" / "references"
    refs.mkdir(parents=True, exist_ok=True)
    (b / "SKILL.md").write_text("---\nname: x\ndescription: d\nversion: 1.2.3\n---\n"
                                "1. do a thing\n2. verify it\n3. never fabricate\n")
    (refs / "mfnl-selectors.yaml").write_text(manifest)
    if doc is not None:
        (refs / doc_name).write_text(doc)
    return b


_MANIFEST_MATCH = (
    "version: 1\n"
    "doc_twin: form-selectors.md\n"
    "pages:\n"
    "  - page: one\n"
    "    submit: {selector: 'button[type=submit]'}\n"
    "    fields:\n"
    "      - {name: a, selector: '#field_a', kind: fill, "
    "fallbacks: ['role=textbox[name=\"A\"]']}\n"
    "      - {name: r, selector: 'input[name=radio_r][value=Nee]', kind: check, "
    "fallbacks: ['[name=\"radio_r\"]']}\n"
)
# the human twin: primary anchors verbatim, the radio by field with an ellipsis value,
# the machine fallbacks NOT enumerated (documented as a pattern, not a token).
_DOC_MATCH = ("# map\n\nPage one: `#field_a` (text); `input[name=radio_r][value=…]` "
              "(radio); submit `button[type=submit]`.\n")


def test_selector_twin_match_is_clean(tmp_path):
    b = _twin_bundle(tmp_path, manifest=_MANIFEST_MATCH, doc=_DOC_MATCH)
    assert not any("twin DRIFT" in f for f in lint.lint_bundle(b))


def test_selector_twin_drift_fails(tmp_path):
    # the doc renamed #field_a → #field_A; the manifest still has #field_a → drift both ways
    drifted = _DOC_MATCH.replace("#field_a", "#field_A")
    b = _twin_bundle(tmp_path, manifest=_MANIFEST_MATCH, doc=drifted)
    findings = lint.lint_bundle(b)
    assert any("twin DRIFT" in f for f in findings)
    msg = next(f for f in findings if "twin DRIFT" in f)
    assert "#field_a" in msg and "#field_A" in msg   # a clear, both-directions set-diff


def test_selector_twin_radio_value_is_normalized(tmp_path):
    # the doc's `[value=…]` ellipsis must normalize to the same field anchor as the
    # manifest's concrete `[value=Nee]` — a radio option value is never drift.
    b = _twin_bundle(tmp_path, manifest=_MANIFEST_MATCH, doc=_DOC_MATCH)
    assert not any("twin DRIFT" in f for f in lint.lint_bundle(b))


def test_selector_twin_missing_doc_is_a_finding(tmp_path):
    b = _twin_bundle(tmp_path, manifest=_MANIFEST_MATCH, doc=None)
    assert any("does not" in f.lower() or "not a file" in f
               for f in lint.lint_bundle(b) if "doc_twin" in f)


def test_selector_manifest_without_doc_twin_warns_not_fails(tmp_path):
    no_twin = _MANIFEST_MATCH.replace("doc_twin: form-selectors.md\n", "")
    b = _twin_bundle(tmp_path, manifest=no_twin, doc=_DOC_MATCH)
    # a manifest with no doc_twin is a SOFT warning, never a hard failure
    assert not any("twin DRIFT" in f for f in lint.lint_bundle(b))
    assert any("doc_twin" in w and "unguarded" in w for w in lint.checklist_warnings(b))


def test_barney_manifest_twin_is_in_lockstep():
    # the shipped Barney bundle (radar) declares doc_twin and must stay drift-free.
    bundle = Path("/Users/ries/oteny/radar/cuneus_barney/talents/cuneus-hr-talent")
    if bundle.is_dir():
        assert not any("twin DRIFT" in f for f in lint.lint_bundle(bundle))


# --------------------------------------------------------------------------- #
# uv runtime lock (check 18)                                                   #
# --------------------------------------------------------------------------- #
def test_flatbelly_ships_uv_lock_and_passes_check():
    assert (FLATBELLY / "pyproject.toml").is_file()
    assert (FLATBELLY / "uv.lock").is_file()
    assert not any("uv.lock" in f or "uv lock" in f for f in lint.lint_bundle(FLATBELLY))


def test_third_party_import_without_lock_is_a_finding(tmp_path):
    b = _talent(tmp_path)
    scripts = b / "scripts"
    scripts.mkdir()
    (scripts / "chart.py").write_text("import matplotlib\nprint(matplotlib.__version__)\n")
    assert any("pyproject.toml` + `uv.lock`" in f or "uv.lock" in f
               for f in lint.lint_bundle(b))


def test_yaml_only_import_does_not_require_uv_lock(tmp_path):
    # platform-baked PyYAML — readiness scripts may import it without a Talent lock
    b = _talent(tmp_path)
    scripts = b / "scripts"
    scripts.mkdir()
    (scripts / "read.py").write_text("import yaml\nprint(yaml.safe_load('a: 1'))\n")
    assert not any("uv.lock" in f for f in lint.lint_bundle(b))
