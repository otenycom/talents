"""Author package must not touch operator infra primitives."""
from __future__ import annotations

import ast
import inspect
import textwrap

import pytest

from oteny import cli, runner, traces
from oteny.live import LiveDriver

FORBIDDEN_ATTRS = {"mgmt_ssh_key_path", "resolved_tailscale_api_key", "tailscale_authkey"}
FORBIDDEN_NAMES = {"asyncssh", "Settings", "get_settings"}
FORBIDDEN_CALLS = {"_node_exec", "_resolve_clone_node_host"}

AUTHOR_SCOPED = {
    "runner.run_scenarios_for_clone": runner.run_scenarios_for_clone,
    "cli.cmd_test": cli.cmd_test,
    "cli.cmd_traces": cli.cmd_traces,
    "traces.build_traces_dto": traces.build_traces_dto,
    "live.LiveDriver.trace": LiveDriver.trace,
    "live.LiveDriver.hand_off": LiveDriver.hand_off,
}


def _forbidden_refs(fn) -> list[str]:
    tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
    bad: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Attribute) and n.attr in FORBIDDEN_ATTRS:
            bad.add(f".{n.attr}")
        if isinstance(n, ast.Name) and n.id in FORBIDDEN_NAMES:
            bad.add(n.id)
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                if a.name.split(".")[0] in FORBIDDEN_NAMES:
                    bad.add(f"import {a.name}")
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id in FORBIDDEN_CALLS):
            bad.add(f"{n.func.id}()")
    return sorted(bad)


@pytest.mark.parametrize("name,fn", list(AUTHOR_SCOPED.items()))
def test_author_entrypoint_has_no_operator_infra(name, fn):
    bad = _forbidden_refs(fn)
    assert not bad, f"{name} references operator infra: {bad}"
