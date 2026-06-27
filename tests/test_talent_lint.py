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
            migrations: str | None = None) -> Path:
    """A minimal Talent bundle (has required_artifacts.yaml -> is_talent)."""
    b = root / "oteny-x-talent"
    b.mkdir(parents=True, exist_ok=True)
    (b / "required_artifacts.yaml").write_text("bot: oteny-x-talent\nartifacts: []\n")
    prof = "bot: oteny-x-talent\n"
    if version_line is not None:
        prof += version_line + "\n"
    (b / "agent-profile.yaml").write_text(prof)
    if migrations is not None:
        (b / "migrations.yaml").write_text(migrations)
    return b


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


def test_all_real_talents_lint_clean():
    bundles = [str(p) for p in sorted(CATALOG.glob("*-talent"))]
    assert bundles
    assert lint.main(bundles) == 0
