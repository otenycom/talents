"""Helpers for the Oteny marketable-Talent unit tests (talents.git, the canonical home).

The bundle scripts are run by Hermes on the tenant box and loaded by path with importlib.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CATALOG = REPO / "skills"
SHARED = CATALOG / "_shared" / "scripts"


def load(path: str | Path, name: str | None = None):
    path = Path(path)
    name = name or f"talent_{path.stem}"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sandbox_env(monkeypatch, root: Path):
    """Point the selfcheck/reconciler home-resolution at a sandbox dir."""
    monkeypatch.setenv("HH_HOME", str(root))
    monkeypatch.setenv("HH_HERMES_HOME", str(root / ".hermes"))
    (root / ".hermes").mkdir(parents=True, exist_ok=True)
