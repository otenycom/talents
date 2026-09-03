"""Harvested debug traces over account-key /json/2/ (dogfood)."""
from __future__ import annotations

import base64
import json
import zlib
from typing import Any

PHOTO_TEXT_CAP = 2000
PHOTO_OPTIONS_CAP = 50
_VALUE_KINDS = frozenset({"type", "fill", "select"})


def decode_page_archive(blob_b64: str) -> dict:
    """base64(zlib(json)) — the shape ``hh.browser.trace.read_page_archive`` returns."""
    return json.loads(zlib.decompress(base64.b64decode(blob_b64)).decode("utf-8"))


def compact_photo(archive: dict, *, text_cap: int = PHOTO_TEXT_CAP,
                  options_cap: int = PHOTO_OPTIONS_CAP) -> dict:
    """The archived page as an author reads it back: what the page showed, what
    was aimed, what was in the list — never the raw HTML. Same shape the platform's
    own ``traces --photos`` and the bot's ``browser_recall`` tool hand out."""
    archive = archive if isinstance(archive, dict) else {}
    visible = str(archive.get("visible_text") or archive.get("ground_truth") or "")
    photo = {
        "url": archive.get("url") or "",
        "title": archive.get("title") or "",
        "capture_reason": archive.get("capture_reason") or "",
        "tool_name": archive.get("tool_name") or "",
        "aim": archive.get("aim") or "",
        "generation": archive.get("generation"),
        "visible_text": visible[:text_cap],
        "visible_text_truncated": len(visible) > text_cap,
    }
    options = archive.get("options")
    if isinstance(options, dict) and isinstance(options.get("names"), list):
        names = [str(n) for n in options["names"]]
        photo["options"] = {
            "label": options.get("label") or "",
            "total": options.get("total"),
            "virtualized": bool(options.get("virtualized")),
            "names": names[:options_cap],
            "names_truncated": len(names) > options_cap,
        }
    widgets = archive.get("widgets")
    if isinstance(widgets, list) and widgets:
        photo["open_widgets"] = [
            {"role": w.get("role"), "label": w.get("label"),
             "options": [str(o) for o in (w.get("options") or [])][:options_cap]}
            for w in widgets[:4] if isinstance(w, dict)
        ]
    return photo


def attach_page_photos(client, browser_traces: list[dict], domain: list) -> dict:
    """Put each archived page's compact photo onto its ``page_snapshot`` row as
    ``photo``. The archive flag is read on its own, so an older platform that has
    no page archive yet answers with a note instead of a failed ``traces``. The
    blobs come through ``read_page_archive`` — the row's own seam — so the account
    key's record rules govern, and an author sees only their own bots' pages."""
    summary = {"pages_archived": 0, "photos_attached": 0}
    snap_ids = [t["id"] for t in browser_traces
                if t.get("kind") == "page_snapshot" and isinstance(t.get("id"), int)]
    if not snap_ids:
        return summary
    try:
        flags = client.search_read(
            "hh.browser.trace", [["id", "in", snap_ids]], ["id", "has_page_archive"],
            limit=len(snap_ids))
    except RuntimeError as e:  # the platform predates the page archive
        summary["photos_note"] = f"this platform has no page archive yet ({e})"[:200]
        return summary
    archived = [int(f["id"]) for f in flags if f.get("has_page_archive")]
    summary["pages_archived"] = len(archived)
    if not archived:
        return summary
    blobs = client.call("hh.browser.trace", "read_page_archive", ids=archived) or {}
    for t in browser_traces:
        blob = blobs.get(str(t.get("id"))) if isinstance(blobs, dict) else None
        if not blob:
            continue
        try:
            t["photo"] = compact_photo(decode_page_archive(blob))
        except Exception:  # noqa: BLE001 — a corrupt blob loses its photo, not the DTO
            continue
        summary["photos_attached"] += 1
    return summary


def _msg_preview(m: dict) -> dict:
    content = m.get("content")
    text = content if isinstance(content, str) else ("" if content is None else str(content))
    return {"role": m.get("role"), "tool": m.get("tool_name") or None, "preview": text[:160]}


def derive_uplink_status(diagnostics: list[dict] | None) -> dict:
    """Map recent ``hh.hermes.event`` rows → author-visible uplink health.

    Values: ``auth_failed`` | ``unreachable`` | ``ok`` | ``unknown``. Mute Discuss with
    empty sessions + ``auth_failed`` means remint/re-provision — not website login.

    Newest-first; events older than the latest ``converge`` are ignored so a remint does
    not stay ``auth_failed`` on harvested pre-fix 401s.
    """
    diags = sorted(diagnostics or [], key=lambda d: int(d.get("id") or 0), reverse=True)
    newest_converge_id = 0
    for d in diags:
        if d.get("kind") == "converge":
            newest_converge_id = int(d.get("id") or 0)
            break
    window = ([d for d in diags if int(d.get("id") or 0) >= newest_converge_id]
              if newest_converge_id else diags)

    auth = unreachable = None
    for d in window:
        s = str(d.get("summary") or "")
        low = s.lower()
        first = s.split("\n", 1)[0][:240]
        is_discuss = ("[discuss]" in low or "discuss" in str(d.get("severity") or "").lower()
                      or "mail.message" in low)
        if "401" in s or "unauthorized" in low:
            if is_discuss or "http" in low:
                auth = first
                break
        if is_discuss and (
            "could not reach" in low or "poll error" in low or "urlerror" in low
            or "timed out" in low or "connection" in low
        ):
            if unreachable is None and "warning" not in low:
                unreachable = first
    if auth:
        return {"uplink_status": "auth_failed", "last_uplink_error": auth}
    if unreachable:
        return {"uplink_status": "unreachable", "last_uplink_error": unreachable}
    if window:
        return {"uplink_status": "ok", "last_uplink_error": None}
    return {"uplink_status": "unknown", "last_uplink_error": None}


def build_traces_dto(client, ref: str, session: str | None = None,
                     since: str | None = None, limit: int = 5,
                     photos: bool = False) -> dict:
    """Shape harvested Odoo log models into the structured debug trace.

    ``photos=True`` adds each archived page's compact photo (visible text, the
    aim, the option list — never HTML) to its ``page_snapshot`` row."""
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
        "hh.hermes.event", [["tenant_ref", "=", ref]],
        ["id", "kind", "severity", "summary"], limit=25, order="id desc")

    bt_domain: list[Any] = [["tenant_ref", "=", ref]]
    if session:
        bt_domain.append(["session_ref", "=", session])
    if since:
        bt_domain.append(["ts", ">=", since])
    browser_traces = [
        _enrich_browser_trace_row(t)
        for t in client.search_read(
            "hh.browser.trace", bt_domain,
            ["ts", "page_title", "page_url", "step_index", "kind", "target_attempted",
             "match_count", "el_id", "el_name", "el_role", "el_aria_label", "el_text",
             "el_tag", "el_type", "action_fired", "checked_state", "value_matched",
             "ok", "error", "submit_actual", "nav_from", "nav_to", "has_snapshot",
             "snapshot_pretty"],
            limit=300)
    ]
    steps = [t for t in browser_traces if t.get("kind") != "page_snapshot"]
    snaps = [t for t in browser_traces if t.get("kind") == "page_snapshot"]
    # A native click / type aimed by name carries no locator count and a click
    # carries no value, so a miss is a step that FAILED with nothing matched and a
    # value mismatch is counted only on a step that set a value. Otherwise a clean
    # named run reads as all misses.
    browser_summary = {
        "actions": len(steps),
        "misses": sum(1 for t in steps
                      if t.get("match_count") == 0 and not t.get("ok")),
        "ambiguous": sum(1 for t in steps if (t.get("match_count") or 0) > 1),
        "value_mismatches": sum(1 for t in steps
                                if t.get("kind") in _VALUE_KINDS
                                and t.get("value_matched") == 0),
        # A click that reported SUCCESS and left its control unchecked — the
        # off-viewport no-op signature. The tool says ok, the page did not
        # change, and nothing the model can see tells the difference.
        "click_no_ops": sum(
            1 for t in steps if t.get("ok") and t.get("checked_state") == 0),
        "failed": sum(1 for t in steps if not t.get("ok")),
        "pages_captured": len(snaps),
        "controls_captured": sum(
            len(t.get("form_inventory") or []) for t in snaps),
    }
    if photos:
        browser_summary.update(attach_page_photos(client, browser_traces, bt_domain))
    uplink = derive_uplink_status(diagnostics)
    return {
        "ref": ref, "sessions": out_sessions, "diagnostics": diagnostics,
        "uplink_status": uplink["uplink_status"],
        "last_uplink_error": uplink["last_uplink_error"],
        "browser_summary": browser_summary, "browser_traces": browser_traces,
    }


def _enrich_browser_trace_row(row: dict) -> dict:
    """Promote ``form_inventory`` out of ``snapshot_pretty`` so an author reading
    ``traces`` JSON sees the page's controls — and their checked/value state —
    without decoding zlib. Parity with the platform's own ``traces`` verb."""
    out = dict(row)
    if out.get("kind") != "page_snapshot":
        return out
    if isinstance(out.get("form_inventory"), list):
        return out
    raw = out.get("snapshot_pretty")
    if not isinstance(raw, str) or not raw.strip():
        return out
    try:
        doc = json.loads(raw)
    except (ValueError, TypeError):
        return out
    if isinstance(doc, dict) and isinstance(doc.get("form_inventory"), list):
        out["form_inventory"] = doc["form_inventory"]
    return out


def latest_session_id(client, ref: str) -> int:
    rows = client.search_read(
        "hh.hermes.session", [["tenant_ref", "=", ref]], ["id"], limit=1)
    return int(rows[0]["id"]) if rows else 0


def harvest_trace_text(dto: dict, *, after_session_id: int = 0) -> str:
    sessions = dto.get("sessions") or []
    fresh = [s for s in sessions if int(s.get("id") or 0) > after_session_id]
    lines: list[str] = []
    status = dto.get("uplink_status")
    if status:
        err = dto.get("last_uplink_error")
        lines.append(f"# uplink_status={status}" + (f" last_error={err}" if err else ""))
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
    if bs.get("actions") or bs.get("pages_captured"):
        lines.append(
            f"# browser actions={bs.get('actions')} misses={bs.get('misses')} "
            f"click_no_ops={bs.get('click_no_ops')} failed={bs.get('failed')} "
            f"pages={bs.get('pages_captured')} controls={bs.get('controls_captured')}"
            + (f" archived={bs.get('pages_archived')} photos={bs.get('photos_attached')}"
               if "pages_archived" in bs else ""))
    return "\n".join(lines)
