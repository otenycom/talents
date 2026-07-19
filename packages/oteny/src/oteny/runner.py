"""Graded live scenario runner — account-key dogfood (no staff Settings)."""
from __future__ import annotations

import asyncio
import contextlib
import fnmatch
import json
from pathlib import Path

from .box import AuthorBoxAccess
from .catalog import bundle_db_rel, load_run_scenario, resolve_local_catalog
from .cli_transport import CliPoster
from .discuss import build_discuss_driver
from .live import LiveDriver
from .traces import build_traces_dto, harvest_trace_text, latest_session_id


def filter_scenario_paths(paths: list[str], scenario_globs: list[str] | None) -> list[str]:
    if not scenario_globs:
        return paths
    kept, unmatched = [], []
    for glob in scenario_globs:
        hits = [p for p in paths if fnmatch.fnmatch(Path(p).stem, glob)]
        if not hits:
            unmatched.append(glob)
        kept.extend(h for h in hits if h not in kept)
    if unmatched:
        stems = ", ".join(sorted(Path(p).stem for p in paths))
        raise RuntimeError(
            f"--scenario {unmatched!r} matched no scenario (have: {stems})")
    return kept


def run_scenarios_for_clone(
    client,
    ref: str,
    bundle: str,
    *,
    bundle_dir: str,
    shared_dir: str | None = None,
    scenario_globs: list[str] | None = None,
    transport: str = "auto",
    junit: str | None = None,
) -> dict:
    """Drive a bot's bundle scenarios LIVE. ``transport``: auto|discuss|cli."""
    rows = client.search_read(
        "hh.tenant", [("ref", "=", ref)],
        ["id", "node_id", "bot_username", "isolation_tier",
         "uplink_url", "uplink_db", "uplink_env", "discuss_channel_id"], limit=1)
    if not rows:
        raise RuntimeError(f"no tenant {ref!r}")
    rec = rows[0]
    nid = rec["node_id"][0] if isinstance(rec["node_id"], (list, tuple)) else rec["node_id"]
    substrate = "vm" if ((rec.get("isolation_tier") == "vm") or not nid) else "container"

    catalog_dir, cleanup = resolve_local_catalog(bundle, bundle_dir, shared_dir=shared_dir)
    box_stack = contextlib.ExitStack()
    try:
        db_rel = bundle_db_rel(bundle, catalog_dir)

        def read_trace(after_session_id: int) -> str:
            dto = build_traces_dto(client, ref, limit=5)
            return harvest_trace_text(dto, after_session_id=after_session_id)

        def latest_sid() -> int:
            return latest_session_id(client, ref)

        exec_on_node = None
        box_exec = None
        if db_rel or transport == "cli" or (
                transport == "auto" and not rec.get("bot_username")
                and not rec.get("uplink_url") and not rec.get("discuss_channel_id")):
            box_exec = box_stack.enter_context(AuthorBoxAccess(client).shell(ref))

            async def exec_on_node(cmd: str) -> str:  # noqa: F811
                return await asyncio.to_thread(box_exec, cmd)

        async def dm(bot_username: str, text: str, timeout: float) -> str:
            raise RuntimeError(
                "Telegram DM transport is Phase 2 — use Discuss or CLI transport")

        post_message, uplink_call = None, None
        use_cli = transport == "cli"
        use_discuss = transport == "discuss"
        if transport == "auto":
            if rec.get("bot_username"):
                use_discuss = False  # would be telegram — refuse for now
            elif rec.get("uplink_url") or rec.get("discuss_channel_id"):
                use_discuss = True
            else:
                use_cli = True

        if use_discuss:
            post_message, uplink_call = build_discuss_driver(
                uplink_url=rec.get("uplink_url") or "",
                uplink_db=rec.get("uplink_db") or None,
                bundle=bundle, catalog_dir=catalog_dir,
                channel_override=rec.get("discuss_channel_id") or None)
        elif use_cli:
            if box_exec is None:
                box_exec = box_stack.enter_context(AuthorBoxAccess(client).shell(ref))

                async def exec_on_node(cmd: str) -> str:  # noqa: F811
                    return await asyncio.to_thread(box_exec, cmd)

            post_message = CliPoster(box_exec)
        elif rec.get("bot_username"):
            raise RuntimeError(
                f"{ref} is a Telegram bot — Telegram transport is Phase 2; "
                "use a Discuss or CLI-capable bot, or wait for oteny[telegram]")

        driver = LiveDriver(
            ref=ref, bot_username=None if (use_discuss or use_cli) else rec.get("bot_username"),
            db_rel=db_rel, exec_on_node=exec_on_node, dm=dm,
            post_message=post_message, uplink_call=uplink_call,
            substrate=substrate, read_trace=read_trace,
            latest_session_id=latest_sid)

        rs = load_run_scenario(catalog_dir)
        rs.set_live_driver(driver)
        scen_dir = Path(catalog_dir) / bundle / "tests" / "scenarios"
        paths = sorted(str(p) for p in scen_dir.glob("*.yaml"))
        paths = filter_scenario_paths(paths, scenario_globs)
        results = [rs.run_scenario(Path(p), "live") for p in paths]
        ok = all(s["failed"] == 0 and not s["error"] for s in results)
        report = {
            "ok": ok, "ref": ref, "bundle": bundle, "scenarios": results,
            "transport": "cli" if use_cli else ("discuss" if use_discuss else "none"),
            "summary": {
                "scenarios": len(results),
                "passed": sum(s["passed"] for s in results),
                "failed": sum(s["failed"] for s in results),
            },
        }
        if junit:
            Path(junit).write_text(_junit_xml(bundle, results))
        return report
    finally:
        box_stack.close()
        cleanup()


def _junit_xml(bundle: str, results: list[dict]) -> str:
    cases = []
    for s in results:
        name = s.get("name") or s.get("path") or "scenario"
        fail = s.get("failed") or 0
        err = s.get("error")
        if err:
            cases.append(
                f'<testcase classname="{bundle}" name="{name}">'
                f'<error message="{_xml(str(err))}"/></testcase>')
        elif fail:
            cases.append(
                f'<testcase classname="{bundle}" name="{name}">'
                f'<failure message="{fail} failed"/></testcase>')
        else:
            cases.append(f'<testcase classname="{bundle}" name="{name}"/>')
    body = "\n".join(cases)
    return (
        f'<?xml version="1.0"?><testsuite name="{bundle}" tests="{len(results)}">'
        f"{body}</testsuite>")


def _xml(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;"))[:500]


def emit(obj) -> None:
    print(json.dumps(obj, indent=2, default=str))
