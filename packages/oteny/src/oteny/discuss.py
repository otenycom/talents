"""Discuss transport wiring for business-bot live scenarios."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

import yaml

from .client import OdooClient
from .live import DiscussPoster, LIVE_REPLY_QUIET_PERIOD_S


def load_discuss_cfg(bundle: str, catalog_dir: str) -> dict | None:
    cfg_path = Path(catalog_dir) / bundle / "tests" / "discuss.yaml"
    if not cfg_path.is_file():
        return None
    data = yaml.safe_load(cfg_path.read_text()) or {}
    has_channel = data.get("channel_xmlid") or data.get("channel_id")
    return data if has_channel and data.get("bot_login") else None


def read_secret_file(path: str) -> str:
    p = Path(os.path.expanduser(path)) if path else None
    return p.read_text().strip() if (p and p.is_file()) else ""


def resolve_channel_xmlid(uplink: OdooClient, xmlid: str) -> int:
    module, _, name = xmlid.partition(".")
    if not module or not name:
        raise RuntimeError(f"channel_xmlid {xmlid!r} is not a 'module.name' external id")
    try:
        model, res_id = uplink.call(
            "ir.model.data", "check_object_reference",
            module=module, xml_id=name, raise_on_access_error=True)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            f"channel_xmlid {xmlid!r} did not resolve on {uplink.base_url}: {exc}") from exc
    if model != "discuss.channel" or not res_id:
        raise RuntimeError(
            f"channel_xmlid {xmlid!r} resolves to {model}#{res_id}, not discuss.channel")
    return int(res_id)


def driver_channel(channel_override, cfg: dict, resolve_xmlid=None) -> int:
    if channel_override:
        return int(channel_override)
    xmlid = cfg.get("channel_xmlid")
    if xmlid and resolve_xmlid is not None:
        return resolve_xmlid(xmlid)
    if not cfg.get("channel_id"):
        raise RuntimeError("tests/discuss.yaml has no resolvable channel")
    return int(cfg["channel_id"])


def resolve_bot_partner(uplink: OdooClient, bot_login: str) -> int | None:
    users = uplink.search_read("res.users", [["login", "=", bot_login]], ["partner_id"], limit=1)
    pid = users[0].get("partner_id") if users else None
    return pid[0] if isinstance(pid, (list, tuple)) else pid


def build_discuss_driver(
    *,
    uplink_url: str,
    uplink_db: str | None,
    bundle: str,
    catalog_dir: str,
    channel_override=None,
):
    """Return ``(post_message, uplink_call)`` for a no-Telegram business bot."""
    cfg = load_discuss_cfg(bundle, catalog_dir) if uplink_url else None
    if not uplink_url or not cfg:
        async def _unconfigured(text, timeout):
            raise RuntimeError(
                "no live Discuss driver — need tenant uplink_url + tests/discuss.yaml "
                "(channel_xmlid + bot_login + tester_key_file)")
        return _unconfigured, None

    uplink = OdooClient(
        base_url=uplink_url, db=uplink_db,
        api_key=read_secret_file(cfg.get("tester_key_file") or "") or None)
    partner = resolve_bot_partner(uplink, cfg["bot_login"])
    channel = driver_channel(
        channel_override, cfg,
        resolve_xmlid=lambda x: resolve_channel_xmlid(uplink, x))

    async def odoo_call(model, method, **kw):
        return await asyncio.to_thread(uplink.call, model, method, **kw)

    try:
        quiet = float(cfg.get("reply_quiet_period_s", LIVE_REPLY_QUIET_PERIOD_S))
    except (TypeError, ValueError):
        quiet = LIVE_REPLY_QUIET_PERIOD_S
    return DiscussPoster(
        odoo_call=odoo_call, channel_id=channel, bot_partner_id=partner,
        quiet_period_s=quiet), odoo_call
