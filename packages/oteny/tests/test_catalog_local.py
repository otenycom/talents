"""--bundle-dir catalog resolve (no deploy key)."""
from __future__ import annotations

from pathlib import Path

from oteny.catalog import resolve_local_catalog


def test_resolve_local_catalog_copies_shared_and_bundle(tmp_path: Path):
    shared = tmp_path / "_shared" / "scripts"
    shared.mkdir(parents=True)
    (shared / "run_scenario.py").write_text("# stub\n")
    bundle = tmp_path / "my-talent"
    (bundle / "tests" / "scenarios").mkdir(parents=True)
    (bundle / "tests" / "scenarios" / "happy.yaml").write_text("name: happy\n")

    cat, cleanup = resolve_local_catalog(
        "my-talent", str(bundle), shared_dir=str(tmp_path / "_shared"))
    try:
        assert (Path(cat) / "_shared" / "scripts" / "run_scenario.py").is_file()
        assert (Path(cat) / "my-talent" / "tests" / "scenarios" / "happy.yaml").is_file()
    finally:
        cleanup()
    assert not Path(cat).exists()


def test_resolve_requires_scenarios(tmp_path: Path):
    bare = tmp_path / "bare"
    bare.mkdir()
    try:
        resolve_local_catalog("bare", str(bare), shared_dir=str(tmp_path))
        raise AssertionError("expected RuntimeError")
    except RuntimeError as e:
        assert "tests/scenarios" in str(e)
