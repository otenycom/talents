"""Harvested debug traces over account-key /json/2/ (dogfood)."""
from __future__ import annotations

from typing import Any


def _msg_preview(m: dict) -> dict:
    content = m.get("content")
    text = content if isinstance(content, str) else ("" if content is None else str(content))
    return {"role": m.get("role"), "tool": m.get("tool_name") or None, "preview": text[:160]}


def build_traces_dto(client, ref: str, session: str | None = None,
                     since: str | None = None, limit: int = 5) -> dict:
    """Shape harvested Odoo log models into the structured debug trace."""
    sess_domain: list[Any] = [["tenant_ref", "=", ref]]
    if session:
        sess_domain.append(["source_session_id", "=", session])
    if since:
        sess_domain.append(["started_at", ">=", since])
    sessions = client.search_read(
        "hh.hermes.session", sess_domain,
        ["id", "source_session_id", "display_label", "started_at"], limit=limit)

    out_sessions = []
    for s in sessions:
        msgs = client.search_read(
            "hh.hermes.message", [["session_id", "=", s["id"]]],
            ["role", "tool_name", "content", "timestamp"], limit=50)
        turns = client.search_read(
            "hh.hermes.turn", [["session_id", "=", s["id"]]], ["model_call_count"], limit=200)
        out_sessions.append({
            "session": s.get("source_session_id"), "id": s["id"],
            "label": s.get("display_label"), "started_at": s.get("started_at"),
            "turns": len(turns),
            "model_calls": sum(int(t.get("model_call_count") or 0) for t in turns),
            "messages": [_msg_preview(m) for m in msgs],
        })

    diagnostics = client.search_read(
        "hh.hermes.event", [["tenant_ref", "=", ref]], ["kind", "severity", "summary"], limit=25)

    bt_domain: list[Any] = [["tenant_ref", "=", ref]]
    if session:
        bt_domain.append(["session_ref", "=", session])
    if since:
        bt_domain.append(["ts", ">=", since])
    browser_traces = client.search_read(
        "hh.browser.trace", bt_domain,
        ["ts", "page_title", "page_url", "step_index", "kind", "target_attempted",
         "match_count", "el_id", "el_name", "el_role", "el_aria_label", "el_text",
         "el_tag", "el_type", "action_fired", "checked_state", "value_matched",
         "ok", "error", "submit_actual", "nav_from", "nav_to", "has_snapshot"],
        limit=300)
    steps = [t for t in browser_traces if t.get("kind") != "page_snapshot"]
    browser_summary = {
        "actions": len(steps),
        "misses": sum(1 for t in steps if t.get("match_count") == 0),
        "ambiguous": sum(1 for t in steps if (t.get("match_count") or 0) > 1),
        "value_mismatches": sum(1 for t in steps if t.get("value_matched") == 0),
        "failed": sum(1 for t in steps if not t.get("ok")),
    }
    return {
        "ref": ref, "sessions": out_sessions, "diagnostics": diagnostics,
        "browser_summary": browser_summary, "browser_traces": browser_traces,
    }


def latest_session_id(client, ref: str) -> int:
    rows = client.search_read(
        "hh.hermes.session", [["tenant_ref", "=", ref]], ["id"], limit=1)
    return int(rows[0]["id"]) if rows else 0


def harvest_trace_text(dto: dict, *, after_session_id: int = 0) -> str:
    sessions = dto.get("sessions") or []
    fresh = [s for s in sessions if int(s.get("id") or 0) > after_session_id]
    lines: list[str] = []
    for s in (fresh or sessions):
        lines.append(
            f"# session {s.get('session')} label={s.get('label')} "
            f"turns={s.get('turns')} model_calls={s.get('model_calls')}")
        for m in (s.get("messages") or []):
            tool = m.get("tool")
            lines.append(
                f"[{m.get('role')}]"
                + (f" tool={tool}" if tool else "")
                + f" {(m.get('preview') or '')}")
    for d in (dto.get("diagnostics") or [])[:10]:
        lines.append(f"# diag {d.get('kind')} {d.get('severity')}: {d.get('summary')}")
    bs = dto.get("browser_summary") or {}
    if bs.get("actions"):
        lines.append(
            f"# browser actions={bs.get('actions')} misses={bs.get('misses')} "
            f"failed={bs.get('failed')}")
    return "\n".join(lines)
