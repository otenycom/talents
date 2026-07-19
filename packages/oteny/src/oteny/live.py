"""Live scenario driver — Discuss / CLI / (Phase-2 Telegram) transports.

Apache-2.0 author package. No control-plane Settings / mgmt-SSH. Box exec + harvest traces are injected.
"""
from __future__ import annotations

import asyncio
import html
import re
import shlex
import time


# --------------------------------------------------------------------------- #
# pure command builders (offline-testable)                                     #
# --------------------------------------------------------------------------- #
def clone_db_path(zpool: str, ref: str, db_name: str) -> str:
    """The clone's sqlite db path ON THE NODE host (inside the ZFS-clone rootfs)."""
    return f"/{zpool}/tenants/{ref}/home/hermes/.hermes/data/{_bundle_data_dir(db_name)}"


def _bundle_data_dir(db_rel: str) -> str:
    # db_rel is "<bot>/<db>.db" or just "<db>.db"; the caller passes the bot-qualified rel.
    return db_rel


def sqlite_query_cmd(db_path: str, sql: str) -> str:
    """A read-only sqlite3 query over node-exec — values tab-separated, one row per line."""
    return f"sqlite3 -batch -noheader -separator '\t' {shlex.quote(db_path)} {shlex.quote(sql)}"


def gateway_log_path(zpool: str, ref: str) -> str:
    return f"/{zpool}/tenants/{ref}/home/hermes/.hermes/logs/gateway.log"


def gateway_log_tail_cmd(zpool: str, ref: str, lines: int = 400) -> str:
    return f"tail -n {int(lines)} {shlex.quote(gateway_log_path(zpool, ref))} 2>/dev/null || true"


# The VM-substrate twins (§14.5): a dedicated-VM tenant's home is /home/hermes ON the
# box itself (exec lands on the VM over the tailnet, not on a node), so there is no
# zpool/clone-rootfs prefix.
VM_HERMES_HOME = "/home/hermes"


def vm_db_path(db_rel: str) -> str:
    return f"{VM_HERMES_HOME}/.hermes/data/{_bundle_data_dir(db_rel)}"


def vm_gateway_log_tail_cmd(lines: int = 400) -> str:
    return (f"tail -n {int(lines)} {VM_HERMES_HOME}/.hermes/logs/gateway.log "
            f"2>/dev/null || true")


def _coerce(v: str):
    """Best-effort coerce a sqlite text cell to int/float so ``equals: 76`` matches."""
    try:
        return int(v)
    except ValueError:
        try:
            return float(v)
        except ValueError:
            return v


# --------------------------------------------------------------------------- #
# Discuss transport — the no-Telegram (business-bot) live path                  #
# --------------------------------------------------------------------------- #
# A business-bot clone (e.g. Cuneus's "Barney") has no Telegram bot: it converses in an
# Odoo ``discuss.channel`` inside its CrewRadar seam, which Hermes polls over /json/2/.
# The live driver simulates the human — it ``message_post``s the turn into the channel and
# polls ``mail.message`` for the bot's reply. Pure shaping here; the seam call is injected
# (so it unit-tests offline AND the Barney build supplies the staging-CrewRadar connection).

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def discuss_post_call(channel_id: int, body: str,
                      *, body_is_html: bool = False) -> tuple[str, str, dict]:
    """The /json/2/ call that posts one human turn into a ``discuss.channel`` (a real
    comment, so the bot's poll adapter sees it — not a log-only note).

    The ``body_is_html`` kwarg mirrors the runtime adapter's ``discuss_wire`` twin (parity):
    the driver posts plain human text so it never sets it; the key is added only when true,
    keeping a plain-text post byte-identical across the two planes."""
    payload = {
        "ids": [int(channel_id)],
        "body": body,
        "message_type": "comment",
        "subtype_xmlid": "mail.mt_comment",
    }
    if body_is_html:
        payload["body_is_html"] = True
    return ("discuss.channel", "message_post", payload)


def discuss_fetch_call(channel_id: int, after_id: int) -> tuple[str, str, dict]:
    """The /json/2/ call that fetches new channel messages past ``after_id`` (so we never
    re-read our own just-posted turn), oldest-first.

    Limit matches ``discuss_wire.MARKER_MAX_BACKFILL_MSGS`` (B-MEM1) — keep byte-identical
    to the runtime adapter's ``discuss_fetch_call``."""
    return ("mail.message", "search_read", {
        "domain": [["model", "=", "discuss.channel"], ["res_id", "=", int(channel_id)],
                   ["id", ">", int(after_id)]],
        "fields": ["id", "body", "author_id"],
        "order": "id asc",
        "limit": 200,
    })


def strip_html(body: str | None) -> str:
    """A discuss message ``body`` is HTML; flatten it to text for reply assertions."""
    if not body:
        return ""
    return html.unescape(_HTML_TAG_RE.sub("", body)).strip()


# Gateway progress/status frames posted into the channel DURING a long run ("⏳ Working —
# 3 min — iteration 20/200", "💾 Self-improvement review: …", "⚠️ Iteration budget…"). They
# are the bot's partner too, but they are not the reply — a reply-picker that stopped at
# the first one would grade a 10-minute filing run on its own progress ticker.
_STATUS_PREFIXES = ("⏳", "💾", "⚠️")

# The `[oteny:verbose]` real-time narration frames (transition-harness SKILL: start-ack,
# per-tool lines, heartbeat) are ALL prefixed with the claim work token `[<token>]`,
# optionally after an emoji marker — e.g. "✅ [goAHzbeQ-CN1] crewradar_json2 ·
# riverflow.service.search_read" or "[goAHzbeQ-CN1] still working — 40s, 6 call(s)". They
# are the live progress picture of a long DISPATCHED filing run, NOT its reply; the final
# narration ("✅ Filed the MFNL for …") carries NO token tag. Without this skip a graded run
# returns on the first uplink call (~30 s into a ~10-min filing) and grades a progress
# frame — then the next scenario's message interrupts the still-running turn (the live-seen
# "Interrupt recursion depth" gateway warning on 2026-07-08).
_VERBOSE_FRAME_RE = re.compile(r"^[^\w\[]*\[[A-Za-z0-9][A-Za-z0-9_-]{4,}\]")

# The default reply-debounce window for the LIVE `test` verb (C6). A dispatched filing emits
# a tool line per call plus a "still working" heartbeat whenever it idles past 30 s
# (VERBOSE_HEARTBEAT_IDLE_S), so a quiet window comfortably above that reliably separates
# "still filing" from "done" without cutting a multi-minute run off on its opening narration.
# A bundle's tests/discuss.yaml may override it per Talent via `reply_quiet_period_s`.
LIVE_REPLY_QUIET_PERIOD_S = 45.0


def pick_bot_reply(messages: list[dict], bot_partner_id: int | None) -> str | None:
    """The newest message authored by the bot (its partner) → reply text, else None. With
    no known ``bot_partner_id`` the newest new message is the reply (the caller seeds
    ``after_id`` past its own turn, so any new message is the bot's). Gateway
    progress/status frames AND `[oteny:verbose]` token-tagged narration frames are skipped —
    they are not the reply."""
    out = None
    for m in messages or []:
        author = m.get("author_id")
        aid = author[0] if isinstance(author, (list, tuple)) else author
        if bot_partner_id and aid != bot_partner_id:
            continue
        text = strip_html(m.get("body"))
        if text.startswith(_STATUS_PREFIXES) or _VERBOSE_FRAME_RE.match(text):
            continue
        out = text
    return out


def _posted_message_id(posted) -> int:
    """``message_post`` returns the new ``mail.message`` id (or a recordset → its ids)."""
    if isinstance(posted, (list, tuple)):
        return int(posted[0]) if posted else 0
    return int(posted) if isinstance(posted, (int, float)) else 0


class DiscussPoster:
    """Posts a turn into a ``discuss.channel`` and polls for the bot's reply — the
    no-Telegram analog of the telethon DM. ``odoo_call`` is an async
    ``(model, method, **kw) -> result`` (a seam ``OdooClient.call`` wrapped onto a thread);
    injected so this unit-tests offline and the Barney build supplies the staging-CrewRadar
    connection. ``sleep``/``timeout_clock`` are injectable for a deterministic test."""

    def __init__(self, *, odoo_call, channel_id, bot_partner_id=None,
                 poll_interval_s: float = 2.0, quiet_period_s: float = 0.0,
                 sleep=None, timeout_clock=None):
        self._call = odoo_call
        self._channel = int(channel_id)
        self._bot_partner = bot_partner_id
        self._poll = poll_interval_s
        # C6 debounce: once a reply candidate is seen, keep waiting until NO new channel
        # message (of ANY kind — verbose/status heartbeats included) has arrived for this
        # many seconds, then return the NEWEST non-verbose reply. A long DISPATCHED filing
        # narrates an opening line then keeps working (a tool line per call + a ≤30 s
        # heartbeat); without the debounce the driver returned on that opening (~30 s in),
        # graded the wrong message, AND fired the next scenario INTO the still-running turn
        # (the live-seen "Interrupt recursion depth"). 0.0 = no debounce (return the first
        # reply immediately) — the default, so a quick conversational turn is unchanged and
        # every existing caller keeps its old semantics; the live `test` verb sets a real
        # window (> the heartbeat idle) so a multi-minute filing isn't cut off.
        self._quiet = quiet_period_s
        self._sleep = sleep or asyncio.sleep
        self._clock = timeout_clock or time.monotonic

    async def __call__(self, text: str, timeout: float) -> str:
        model, method, kw = discuss_post_call(self._channel, text)
        after = _posted_message_id(await self._call(model, method, **kw))
        return await self.wait_for_reply(after, timeout)

    async def latest_message_id(self) -> int:
        """The channel's newest ``mail.message`` id — the marker a hand-off records BEFORE
        triggering, so it only reads replies the triggered run produced."""
        model, method, kw = discuss_fetch_call(self._channel, 0)
        kw = {**kw, "order": "id desc", "limit": 1, "fields": ["id"]}
        rows = await self._call(model, method, **kw)
        return int(rows[0]["id"]) if rows else 0

    async def wait_for_reply(self, after_id: int, timeout: float) -> str:
        """Poll the channel for the bot's next message past ``after_id`` (the shared wait
        leg of a posted turn and a workflow hand-off).

        With ``quiet_period_s == 0`` this returns the first non-verbose reply immediately
        (the historical behaviour). With a positive quiet period (the live filing case) it
        DEBOUNCES: it returns the NEWEST non-verbose reply only once the channel has been
        silent for the quiet period — any new frame (a tool line, a heartbeat) resets the
        clock, so a still-running filing keeps the driver waiting instead of grading its
        opening narration and firing the next scenario mid-turn (C6)."""
        start = self._clock()
        seen_max = int(after_id)
        last_activity = start
        reply = ""
        while self._clock() - start < timeout:
            fmodel, fmethod, fkw = discuss_fetch_call(self._channel, after_id)
            msgs = await self._call(fmodel, fmethod, **fkw)
            # ANY new message id means the bot is still active (verbose/status heartbeats
            # included) — reset the quiet clock so the debounce never fires mid-run.
            new_max = max((int(m.get("id") or 0) for m in msgs or []), default=seen_max)
            if new_max > seen_max:
                seen_max = new_max
                last_activity = self._clock()
            candidate = pick_bot_reply(msgs, self._bot_partner)
            if candidate:
                reply = candidate
            # No debounce → return the first reply at once (unchanged). Debounce → hold the
            # newest reply until the channel has been quiet for the window.
            if reply and (self._clock() - last_activity) >= self._quiet:
                return reply
            await self._sleep(self._poll)
        # Timed out: return the best candidate we saw (a filing that narrated but never went
        # quiet within the window is still gradable), else '' (no reply at all).
        return reply


# --------------------------------------------------------------------------- #
# the LiveDriver                                                                #
# --------------------------------------------------------------------------- #
class LiveDriver:
    """Drives a real clone for run_scenario --backend live. ``exec_on_node`` is an async
    ``(cmd: str) -> str`` (node-exec stdout); ``dm`` is an async ``(text) -> reply`` (the
    Telegram path); ``post_message`` is an async ``(text, timeout) -> reply`` (the Discuss
    path for a no-Telegram clone). All injected so the driver unit-tests offline (the live
    ``test`` verb passes the real telethon / asyncssh / Discuss implementations)."""

    def __init__(self, *, ref: str, bot_username: str | None,
                 db_rel: str | None, exec_on_node, dm, dm_timeout: float = 90.0,
                 post_message=None, uplink_call=None, substrate: str = "container",
                 read_trace=None, latest_session_id=None, uplink_poll_s: float = 6.0,
                 zpool: str | None = None):
        self._ref = ref
        self._bot = bot_username
        self._zpool = zpool
        # ``substrate`` picks the exec-side layout: a container's home is a ZFS clone
        # rootfs mounted ON ITS NODE (exec lands on the node); a dedicated VM's home is
        # /home/hermes on the box itself (exec lands on the VM). It is also read by the
        # scenario runner's §14.5 skip (a `requires: {substrate: vm}` scenario is
        # skipped on a container clone) — exposed as a public attr for that.
        self.substrate = substrate
        if not db_rel:
            self._db = None
        elif substrate == "vm":
            self._db = vm_db_path(db_rel)
        else:
            if not zpool:
                self._db = None
            else:
                self._db = clone_db_path(zpool, ref, db_rel)
        self._exec = exec_on_node
        self._dm = dm
        self._dm_timeout = dm_timeout
        self._post_message = post_message
        # A no-Telegram (business-bot) clone's source of truth is the business Odoo, NOT a
        # local sqlite db — so a scenario asserts ground truth over /json/2/ (the
        # business-bot-pattern §5 data-plane check), not over ``scalar``/``rows``.
        # ``uplink_call`` is the async ``(model, method, **kw) -> result`` the Discuss
        # transport already uses; the ``test`` verb injects the live OdooClient.call here.
        self._uplink_call = uplink_call
        # DOGFOOD trace lane: ``read_trace`` is an injected ``() -> str`` that reads the
        # box's activity from the HARVESTED Odoo log (``build_traces_dto`` over /json/2/,
        # record-rule scoped to the account) — NOT the operator mgmt-SSH gateway-log tail.
        # When present it is preferred by :meth:`trace`; the ``exec_on_node`` fallback stays
        # only for offline unit tests (a fake exec) and clone-db reads (routed by the CLI
        # through the account-scoped box-access shell, never asyncssh). See
        # ``tests/test_dogfood_boundary.py``.
        self._read_trace = read_trace
        # ``latest_session_id`` (``() -> int``) reads the newest harvested session id over
        # /json/2/; captured as a baseline BEFORE each turn so :meth:`trace` renders only the
        # session THIS turn produced (monotonic ids — skew-free vs a wall-clock ``since``).
        self._latest_session_id = latest_session_id
        self._trace_after = 0
        self._uplink_poll_s = uplink_poll_s

    def _mark_trace_baseline(self) -> None:
        if self._latest_session_id is not None:
            try:
                self._trace_after = int(self._latest_session_id() or 0)
            except Exception:  # noqa: BLE001 — a harvest read blip must not break the turn
                pass

    def send(self, text: str, timeout: float | None = None) -> str:
        self._mark_trace_baseline()
        wait = timeout or self._dm_timeout
        if self._bot:
            return asyncio.run(self._dm(self._bot, text, wait))
        if self._post_message:        # a no-Telegram (Discuss) clone posts into its channel
            return asyncio.run(self._post_message(text, wait))
        return ""

    def hand_off(self, spec: dict, timeout: float | None = None) -> str:
        """Perform the REAL workflow hand-off over the bot's business-Odoo uplink and wait
        for the bot's channel narration — the scenario trigger that exercises the actual
        dispatch path (the hand-off write fires the inline token-fenced dispatch, D181/D177),
        not a driver-posted flagged message that would bypass the claim fence.

        ``spec`` = ``{model, domain, to_state}``: exactly ONE record must match ``domain``;
        ``to_state`` names the bot-queue ``riverflow.state`` (resolved by name within the
        record's workflow — names are portable across tiers, ids are not)."""
        if not (self._uplink_call and self._post_message is not None
                and hasattr(self._post_message, "wait_for_reply")):
            raise RuntimeError(
                "hand_off needs a Discuss business-bot driver (uplink + channel poster)")
        self._mark_trace_baseline()
        model = spec["model"]
        domain = spec.get("domain", [])
        to_state = spec["to_state"]

        async def _run() -> str:
            recs = await self._uplink_call(
                model, "search_read", domain=domain, fields=["id", "workflow_id"], limit=2)
            if len(recs) != 1:
                raise RuntimeError(f"hand_off matched {len(recs)} records for {domain!r} "
                                   f"(need exactly 1 — seed/reset the fixture)")
            wf = recs[0].get("workflow_id")
            wf_id = wf[0] if isinstance(wf, (list, tuple)) else wf
            sdom = [["name", "=", to_state]] + (
                [["workflow_id", "=", wf_id]] if wf_id else [])
            states = await self._uplink_call(
                "riverflow.state", "search_read", domain=sdom, fields=["id"], limit=2)
            if len(states) != 1:
                raise RuntimeError(
                    f"hand_off resolved {len(states)} states named {to_state!r}")
            # marker BEFORE the trigger, so we only read what the triggered run posts.
            after = await self._post_message.latest_message_id()
            await self._uplink_call(
                model, "write", ids=[recs[0]["id"]], vals={"state_id": states[0]["id"]})
            wait = timeout or self._dm_timeout
            done_when = spec.get("done_when")
            if done_when:
                # Wait on GROUND TRUTH (the record reaching its terminal state), not channel
                # silence — a long filing pauses on the portal for minutes, which the reply
                # debounce misreads as "done" (the 2026-07-11 false-fail: graded a mid-fill
                # frame ~9 min before Barney finished). Once the record settles, grab the
                # final narration (the channel is quiet now, so the debounce returns it fast).
                deadline = time.monotonic() + wait
                await self._await_done(done_when, deadline)
                remaining = max(60.0, deadline - time.monotonic())
                return await self._post_message.wait_for_reply(after, remaining)
            return await self._post_message.wait_for_reply(after, wait)

        return asyncio.run(_run())

    def trace(self) -> str:
        # Account-scoped by default: the harvested activity over /json/2/ (dogfood — an
        # external author reads it with only their account key). The mgmt-SSH gateway-log
        # tail is only the offline-test fallback (a fake ``exec_on_node``).
        if self._read_trace is not None:
            return self._read_trace(self._trace_after)
        zpool = self._zpool or "tank"
        cmd = (vm_gateway_log_tail_cmd() if self.substrate == "vm"
               else gateway_log_tail_cmd(zpool, self._ref))
        return asyncio.run(self._exec(cmd))

    def scalar(self, sql: str):
        rows = self.rows(sql)
        return rows[0][0] if rows and rows[0] else None

    def rows(self, sql: str):
        if not self._db:
            return []
        out = asyncio.run(self._exec(sqlite_query_cmd(self._db, sql)))
        result = []
        for line in (out or "").splitlines():
            if line == "":
                continue
            result.append(tuple(_coerce(c) for c in line.split("\t")))
        return result

    def assert_uplink(self, spec: dict) -> dict:
        """Assert ONE ground-truth check over the business Odoo via /json/2/ — the
        business-bot-pattern §5 data-plane assertion (read back the records a turn should
        have written/changed). A scenario turn declares these under ``expect.uplink:``::

            uplink:
              - model: riverflow.service
                domain: [["current_workflow_name","=","Arrange MFNL Notification"],
                         ["employee_id.name","ilike","Becoy"]]
                equals: {field: state_id, value: "Filed — awaiting confirmation"}
              - model: rivercreds.credential
                domain: [["credential_type_id.code","=","mfnl_filing"],
                         ["number","!=",false], ["employee_id.name","ilike","Becoy"]]
                count: 1

        Verbs: ``count``/``min_count`` (over ``search_count``) and ``equals``
        (``{field, value}`` read off the single matched record; an m2o cell ``[id, name]``
        matches by name when ``value`` is a string). Live-only — the mock backend has no
        uplink, so ``uplink:`` is ignored offline."""
        if not self._uplink_call:
            return {"kind": "uplink", "ok": False, "spec": spec,
                    "reason": "no uplink client — business-bot (Discuss) clones only"}
        res = asyncio.run(self._eval_uplink(spec))
        return {"kind": "uplink", "spec": spec, **res}

    async def _eval_uplink(self, spec: dict) -> dict:
        """ONE ground-truth check over /json/2/ (async), shared by :meth:`assert_uplink`
        (single-shot) and :meth:`hand_off`'s ``done_when`` poll. Returns ``{ok, got, …}``."""
        model = spec.get("model")
        domain = spec.get("domain", [])
        if not model:
            return {"ok": False, "reason": "no model"}
        try:
            if "count" in spec or "min_count" in spec:
                n = await self._uplink_call(model, "search_count", domain=domain)
                ok = (n == spec["count"]) if "count" in spec else (n >= spec["min_count"])
                return {"ok": bool(ok), "got": n}
            if "equals" in spec:
                field = spec["equals"]["field"]
                want = spec["equals"]["value"]
                recs = await self._uplink_call(
                    model, "search_read", domain=domain, fields=[field], limit=2)
                got = recs[0].get(field) if recs else None
                # an m2o reads back as [id, name]; match by name for a string expectation.
                # Some models render a COMPOSITE display name ("<name> | <context>" — e.g.
                # riverflow.state shows "Filed — awaiting confirmation | Arrange MFNL
                # Notification"), so the bare-name segment before " | " matches too: a
                # scenario stays readable + tier-portable without baking the context in.
                if isinstance(got, (list, tuple)) and len(got) == 2 and isinstance(want, str):
                    got = got[1]
                if isinstance(want, bool):
                    ok = got == want
                else:
                    ok = _coerce(str(got)) == _coerce(str(want))
                    if not ok and isinstance(got, str) and " | " in got:
                        ok = got.split(" | ", 1)[0].strip() == str(want)
                return {"ok": ok, "got": got, "matched_rows": len(recs)}
            return {"ok": False, "reason": "no assertion verb"}
        except Exception as e:  # a seam/query error is a test failure, not a runner crash
            return {"ok": False, "reason": f"{type(e).__name__}: {e}"}

    async def _await_done(self, done_when, deadline: float) -> bool:
        """Poll a ground-truth condition (or list) until ALL pass, or ``deadline`` (monotonic)
        passes. THE reliable 'the bot finished' signal for a long async run — a filing's
        completion is a business-record state reaching its terminal value, not the channel
        going quiet (which a mid-run browser pause fakes — the 2026-07-11 false-fail)."""
        specs = done_when if isinstance(done_when, list) else [done_when]
        while time.monotonic() < deadline:
            results = [await self._eval_uplink(s) for s in specs]
            if all(r.get("ok") for r in results):
                return True
            await asyncio.sleep(self._uplink_poll_s)
        return False
