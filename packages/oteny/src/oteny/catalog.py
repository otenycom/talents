"""Local scenario catalog resolution — --bundle-dir only (no deploy-key git clone)."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path


def resolve_local_catalog(bundle: str, bundle_dir: str, *, shared_dir: str | None = None):
    """Return ``(catalog_dir, cleanup)`` with ``_shared`` + ``<bundle>/tests/scenarios``.

    ``bundle_dir`` is the Talent root (contains ``tests/scenarios``). Peer ``_shared`` is
    resolved from ``shared_dir``, else ``bundle_dir/../_shared``, else talents skills/_shared
    beside this package.
    """
    bdir = Path(bundle_dir).expanduser().resolve()
    if not (bdir / "tests" / "scenarios").is_dir():
        raise RuntimeError(f"no tests/scenarios under --bundle-dir {bdir}")

    shared = None
    if shared_dir:
        shared = Path(shared_dir).expanduser().resolve()
    else:
        peer = bdir.parent / "_shared"
        if peer.is_dir():
            shared = peer
        else:
            # packages/oteny/src/oteny → talents/skills/_shared
            cand = Path(__file__).resolve().parents[4] / "skills" / "_shared"
            if cand.is_dir():
                shared = cand
    if shared is None or not shared.is_dir():
        raise RuntimeError(
            "no _shared catalog beside the bundle (pass --shared-dir or keep "
            "skills/_shared next to the Talent)")

    tmp = Path(tempfile.mkdtemp(prefix="oteny-scen-cat-"))
    ig = shutil.ignore_patterns(".git", "__pycache__")
    try:
        shutil.copytree(shared, tmp / "_shared", ignore=ig)
        shutil.copytree(bdir, tmp / bundle, ignore=ig)
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        raise

    def cleanup() -> None:
        shutil.rmtree(tmp, ignore_errors=True)

    return str(tmp), cleanup


def load_run_scenario(catalog_dir: str):
    """Import skills/_shared/scripts/run_scenario.py from the resolved catalog."""
    import importlib.util

    path = Path(catalog_dir) / "_shared" / "scripts" / "run_scenario.py"
    if not path.is_file():
        raise RuntimeError(f"run_scenario.py missing at {path}")
    spec = importlib.util.spec_from_file_location("oteny_run_scenario", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def bundle_db_rel(bundle: str, catalog_dir: str) -> str | None:
    import yaml

    base = Path(catalog_dir) / bundle
    mig = base / "migrations.yaml"
    if mig.is_file():
        data = yaml.safe_load(mig.read_text()) or {}
        if data.get("db"):
            return f"{bundle}/{data['db']}"
    man = base / "required_artifacts.yaml"
    if man.is_file():
        for a in (yaml.safe_load(man.read_text()) or {}).get("artifacts", []):
            if a.get("kind") == "sqlite_db" and a.get("path"):
                return f"{bundle}/{Path(a['path']).name}"
    return None
