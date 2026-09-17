"""Tests for the tool-reference lint (``lint_tools.py``): a Talent requests real, current
Oteny tools, and no toolset name is refused by the platform."""
from __future__ import annotations

from pathlib import Path

import pytest

from _talents import CATALOG, load

lint = load(CATALOG / "talent-authoring-standard" / "scripts" / "lint_tools.py", "lint_tools")
CATALOG_JSON = CATALOG / "talent-authoring-standard" / "references" / "tools-catalog.json"


@pytest.fixture(scope="module")
def catalog() -> dict:
    return lint._load_catalog(CATALOG_JSON)


def _bundle(tmp_path: Path, profile: str) -> Path:
    b = tmp_path / "some-talent"
    b.mkdir()
    (b / "agent-profile.yaml").write_text(profile)
    return b


def _restricted(toolsets: list[str]) -> str:
    items = "".join(f"  - {t}\n" for t in toolsets)
    return (
        "bot: some-talent\n"
        "restrictions:\n"
        "  tool_use: true\n"
        "  self_learning: true\n"
        f"toolset_contribution:\n{items}"
    )


@pytest.mark.parametrize("toolsets", [
    ["odoo_client", "terminal"],
    ["browser", "talent_run"],
    ["browser", "code_execution"],
    ["browser", "execute_code", "file"],
])
def test_restricted_tool_use_may_list_any_known_toolset(tmp_path, catalog, toolsets):
    """The tool list is the lock and no name is special: a Talent that lists a shell or a
    code runner under restricted tool use accepts what it lists. The lint has no FAIL keyed
    on a toolset name."""
    violations, warnings = lint.lint_bundle(_bundle(tmp_path, _restricted(toolsets)), catalog)
    assert violations == []
    assert warnings == []


def test_unknown_toolset_is_a_warning_not_a_failure(tmp_path, catalog):
    violations, warnings = lint.lint_bundle(
        _bundle(tmp_path, _restricted(["browser", "no_such_toolset"])), catalog)
    assert violations == []
    assert len(warnings) == 1 and "no_such_toolset" in warnings[0]


def test_talent_run_is_a_known_toolset(catalog):
    """The scoped helper runner is in the generated catalog, so a Talent that lists it gets
    no unknown-name warning."""
    assert "talent_run" in catalog["toolset"]
    assert "talent_run" in catalog["live"]


def test_stubbing_a_live_tool_still_fails(tmp_path, catalog):
    live = sorted(catalog["live"] & catalog["required"])
    assert live, "the catalog has live first-party tools"
    profile = f"bot: some-talent\ntools:\n  required: []\n  stubbed: [{live[0]}]\n"
    violations, _ = lint.lint_bundle(_bundle(tmp_path, profile), catalog)
    assert violations and "LIVE in the Oteny catalog" in violations[0]
