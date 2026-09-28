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
from .discuss import build_discuss_driver, uplink_url_for_driver
from .live import LiveDriver
from .traces import build_traces_dto, harvest_trace_text, latest_session_id
from .web_transport import WebPoster


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


def transport_for(rec: dict, requested: str, *, uplink_url: str) -> str:
    """The lane to talk to a bot on: an explicit ``cli``/``discuss``/``web`` wins;
    ``auto`` takes Telegram by bot name, the web chat relay for a web bot (its uplink is
    Oteny's own record plane for web chat and it has no Discuss channel), Discuss for a
    Discuss channel or an ERP uplink, and CLI when the bot has no lane at all."""
    if requested in ("cli", "discuss", "web"):
        return requested
    if rec.get("bot_username"):
        return "telegram"
    if rec.get("channel") == "web" and not rec.get("discuss_channel_id"):
        return "web"
    if uplink_url or rec.get("discuss_channel_id"):
        return "discuss"
    return "cli"


def _web_poster(client, rec: dict) -> WebPoster:
    """The web chat lane to a web bot, as its owner: the bot's DM, with tickets the
    author's own account key mints."""
    dm = rec.get("web_dm_channel_id")
    ch = int((dm[0] if isinstance(dm, (list, tuple)) else dm) or 0)
    if not ch:
        raise RuntimeError(f"{rec.get('ref') or 'the bot'} has no web chat DM to talk to "
                           "it in; turn web chat on for it, or pick --transport cli")
    return WebPoster(client, ch=ch)


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
    """Drive a bot's bundle scenarios LIVE. ``transport``: auto|discuss|cli|web."""
    rows = client.search_read(
        "hh.tenant", [("ref", "=", ref)],
        ["id", "node_id", "bot_username", "isolation_tier",
         "uplink_url", "uplink_db", "uplink_env", "discuss_channel_id", "channel",
         "web_dm_channel_id"], limit=1)
    if not rows:
        raise RuntimeError(f"no tenant {ref!r}")
    rec = rows[0]
    # A1: the author's driver may reach the ERP at another address than the bot does.
    uplink_url = uplink_url_for_driver(rec.get("uplink_url") or "")
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

        lane = transport_for(rec, transport, uplink_url=uplink_url)
        exec_on_node = None
        box_exec = None
        if db_rel or lane == "cli":
            box_exec = box_stack.enter_context(AuthorBoxAccess(client).shell(ref))

            async def exec_on_node(cmd: str) -> str:  # noqa: F811
                return await asyncio.to_thread(box_exec, cmd)

        async def dm(bot_username: str, text: str, timeout: float) -> str:
            raise RuntimeError(
                "Telegram DM transport is Phase 2 — use Discuss, web or CLI transport")

        post_message, uplink_call = None, None
        use_cli = lane == "cli"
        use_discuss = lane == "discuss"
        use_web = lane == "web"

        if use_discuss:
            post_message, uplink_call = build_discuss_driver(
                uplink_url=uplink_url,
                uplink_db=rec.get("uplink_db") or None,
                bundle=bundle, catalog_dir=catalog_dir,
                channel_override=rec.get("discuss_channel_id") or None)
        elif use_cli:
            if box_exec is None:
                box_exec = box_stack.enter_context(AuthorBoxAccess(client).shell(ref))

                async def exec_on_node(cmd: str) -> str:  # noqa: F811
                    return await asyncio.to_thread(box_exec, cmd)

            post_message = CliPoster(box_exec)
        elif use_web:
            post_message = _web_poster(client, {**rec, "ref": ref})
        elif rec.get("bot_username"):
            raise RuntimeError(
                f"{ref} is a Telegram bot — Telegram transport is Phase 2; "
                "use a Discuss, web or CLI-capable bot, or wait for oteny[telegram]")

        driver = LiveDriver(
            ref=ref,
            bot_username=None if (use_discuss or use_cli or use_web) else rec.get("bot_username"),
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
            "transport": lane if (use_cli or use_discuss or use_web) else "none",
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
