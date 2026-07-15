"""The readiness-contract v2 fleet invariants (plan §6 Phase A / D-g).

The hh00046 false-onboarding incident was HALF-fixed once before (the stdlib belt landed in
``selfcheck.py`` but not its siblings), so the plan's own risk register calls out "half-ship
the belt again" as the thing to gate. These tests enforce the contract ACROSS every bundle so
a future edit to one copy — or a new bundle that regresses — fails CI, not prod:

  * the shared belt (``selfcheck.py``) and the migration runner (``migrate.py``) stay
    BYTE-IDENTICAL across every bundle that ships them (the mirror discipline);
  * the belt exposes the three-valued surface every sibling depends on
    (``read_yaml`` / ``UNREADABLE`` / the ``BELT:stdlib-yaml`` marker);
  * NO preflight carries the removed "…then onboarding / …then first-run" auto-prime that
    turned an environment failure into a false welcome;
  * every belt-equipped preflight is genuinely THREE-VALUED (emits an ``UNKNOWN`` verdict).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from _talents import CATALOG

_PREFLIGHTS = sorted(CATALOG.glob("*/scripts/preflight.py"))
_SELFCHECKS = sorted(CATALOG.glob("*/scripts/selfcheck.py"))
_MIGRATES = sorted(CATALOG.glob("*/scripts/migrate.py"))


def _identical(paths: list[Path]) -> bool:
    bodies = {p.read_bytes() for p in paths}
    return len(bodies) == 1


def test_selfcheck_belt_is_mirrored_byte_identical():
    """Every shipped ``selfcheck.py`` is the SAME file — the belt can't drift per bundle."""
    assert len(_SELFCHECKS) >= 5, _SELFCHECKS
    assert _identical(_SELFCHECKS), "selfcheck.py copies drifted: " + ", ".join(
        str(p.relative_to(CATALOG)) for p in _SELFCHECKS)


def test_migrate_runner_is_mirrored_byte_identical():
    """Every shipped ``migrate.py`` is the SAME file (it shares the belt loader)."""
    assert len(_MIGRATES) >= 3, _MIGRATES
    assert _identical(_MIGRATES), "migrate.py copies drifted: " + ", ".join(
        str(p.relative_to(CATALOG)) for p in _MIGRATES)


def test_belt_exposes_three_valued_surface():
    """The shared belt exports the contract every sibling imports by path."""
    src = _SELFCHECKS[0].read_text()
    assert "def read_yaml(" in src
    assert "UNREADABLE" in src
    assert "BELT:stdlib-yaml" in src


@pytest.mark.parametrize("pf", _PREFLIGHTS, ids=lambda p: p.parent.parent.name)
def test_no_preflight_carries_the_onboarding_prime(pf):
    """D-g: the "…then onboarding" prime is removed everywhere — a NOT-READY must never
    auto-steer the triage into onboarding/first-run (the false-onboarding link)."""
    src = pf.read_text()
    for banned in (", then onboarding", ", then first-run", "then onboarding;"):
        assert banned not in src, f"{pf.relative_to(CATALOG)} still primes onboarding: {banned!r}"


@pytest.mark.parametrize("pf", _PREFLIGHTS, ids=lambda p: p.parent.parent.name)
def test_belt_equipped_preflights_are_three_valued(pf):
    """A preflight that reads YAML through the shared belt (``read_yaml``) must be genuinely
    three-valued — it emits an ``UNKNOWN`` verdict for an environment fault. A bundle whose
    preflight uses its own stdlib reader (e.g. odoo-website) is exempt: it has no PyYAML
    dependency and no onboarding verb, so the incident class can't reach it."""
    src = pf.read_text()
    if "read_yaml" in src:
        assert "UNKNOWN" in src, f"{pf.relative_to(CATALOG)} uses the belt but is not three-valued"
