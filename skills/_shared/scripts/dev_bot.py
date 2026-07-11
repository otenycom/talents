"""The durable dev-bot singleton helper (D210) — the shared launcher MECHANISM.

Every business-bot and B2C-bot author who holds a durable dev bot needs the same boilerplate:
an Oteny ``/json/2/`` client, a ``request_dev_bot`` + poll loop, a cloudflared tunnel, a
keep-alive heartbeat, and a "stop debugging closes the tunnels but LEAVES the bot up" detach.
This module is that mechanism, promoted out of any one author's launcher so the next author
inherits reuse for free. It is pure stdlib (Hermes/Oteny import nothing from it; it imports
nothing back) and carries **the mechanism only** — the reuse DECISION lives in the platform,
inside ``request_dev_bot`` behind the opt-in ``dev_slot`` kwarg (D210 §4). There is no reuse
``if`` here: this helper just passes ``dev_slot`` through and obeys the platform's ``reused``
flag.

The durable model: one dev bot per ``(developer-laptop, Discuss channel | bundle)``, REUSED
across VS Code stop/restart (no ~7-min rebuild), kept alive by developer activity + a ~30-min
heartbeat, and destroyed only by an explicit teardown or the ~18 h idle-TTL reaper.

Surface:
  * ``Oteny`` — the account-key ``/json/2/`` client.
  * ``dev_slot_slug(label, user=None)`` — the generic ``<user>-<label>`` slot label.
  * ``ensure(...)`` — ``request_dev_bot(dev_slot=…)`` → poll to ``active + talent_delivered``;
    a **failed reuse target auto-rebuilds** (re-issue a plain create). Returns ``{ref, reused,
    request_id, delivered, rebuilt}``.
  * ``touch(oteny, ref=…|dev_slot=…)`` / ``down(oteny, ref=…|dev_slot=…)`` — keep-alive / teardown.
  * ``open_cloudflared_tunnel(...)`` → a ``Tunnel`` handle (named, stable host; else quick).
  * ``hold(oteny, ref, tunnels, on_reaped=…)`` — a context manager that routes
    SIGTERM/SIGHUP/SIGINT to a **detach** (close the tunnels, LEAVE the bot up) and runs the
    ~30-min ``touch`` heartbeat on a daemon thread, rebuilding on ``live=False``.
"""

from __future__ import annotations

import contextlib
import getpass
import json
import re
import signal
import subprocess
import threading
import time
import urllib.error
import urllib.request

_DEV_BOT_MODEL = "hh.dev_bot_request"

# Poll budget for a commission → active+delivered. Sized to outlast Oteny's §G2 capacity window.
DEFAULT_PROVISION_TIMEOUT_S = 900
DEFAULT_POLL_S = 6
# The keep-alive heartbeat: ≫ the touch cost, ≪ the ~18 h idle-TTL (many beats before any reap),
# and > the gateway's 30-s idle so it never spams (D210 §7).
DEFAULT_HEARTBEAT_S = 1800


class Oteny:
    """A minimal ``/json/2/`` client authenticated by the account bearer key. The key rides the
    Authorization header over TLS; call payloads ride the JSON body — never argv, never logs."""

    def __init__(self, base_url: str, key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self._key = key

    def call(self, model: str, method: str, **kwargs) -> object:
        url = f"{self.base_url}/json/2/{model}/{method}"
        data = json.dumps(kwargs).encode()
        req = urllib.request.Request(
            url, data=data, method="POST",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self._key}"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                body = json.loads(r.read().decode() or "null")
        except urllib.error.HTTPError as e:
            detail = (e.read().decode() or "")[:300]
            raise RuntimeError(f"HTTP {e.code} from {model}/{method}: {detail}") from None
        if isinstance(body, dict) and body.get("name") and body.get("message"):
            raise RuntimeError(f"Odoo error: {body['name']}: {body['message']}")
        return body


def dev_slot_slug(label: str, user: str | None = None) -> str:
    """The generic durable-slot label — ``<user>-<label>`` (D210 §5.C). The platform treats it as
    an OPAQUE token it matches by equality and never parses, so no client literal is required; a
    generic slug just keeps it readable + collision-free across developers on one account."""
    user = user or getpass.getuser()
    slug = re.sub(r"[^a-z0-9-]+", "-", f"{user}-{label}".lower()).strip("-")
    return slug or "dev"


def request_kwargs(*, dev_slot: str, bundle: str, uplink_key: str | None = None,
                   talent_source_repo: str | None = None, repo_subpath: str | None = None,
                   source_ref: str | None = None, pin_mode: str = "follow",
                   uplink_url: str | None = None, uplink_db: str | None = None,
                   uplink_env: str = "staging", discuss_channel: str | None = None,
                   spinup_config: dict | None = None) -> dict:
    """Build the ``request_dev_bot`` payload — pure, so a test pins the shape with no round-trip.
    ``dev_slot`` is the D210 durable-singleton opt-in; the launcher passes a **fresh** uplink key +
    the current coords/channel/stub on EVERY run (reuse is converge-in-place, so the platform
    re-pushes them). ``spinup_config`` carries the account's own tunnelled doubles (D168)."""
    kw: dict = {
        "dev_slot": dev_slot, "bundle": bundle, "pin_mode": pin_mode, "uplink_env": uplink_env,
    }
    for k, v in (("uplink_key", uplink_key), ("talent_source_repo", talent_source_repo),
                 ("repo_subpath", repo_subpath), ("source_ref", source_ref),
                 ("uplink_url", uplink_url), ("uplink_db", uplink_db),
                 ("discuss_channel", discuss_channel), ("spinup_config", spinup_config)):
        if v is not None:
            kw[k] = v
    return kw


def parse_status(status: dict) -> tuple[bool, str, str, str, bool, str]:
    """(terminal, state, ref, error, talent_delivered, talent_delivery_error) from a
    ``dev_bot_request_status`` response. Pure. ``talent_delivered`` defaults False when an older
    platform omits it — so the caller falls into the belt-wait fallback, never a false ready."""
    if not status.get("ok"):
        return True, "unreadable", "", status.get("reason", "status not readable"), False, ""
    return (bool(status.get("terminal")), status.get("state", ""), status.get("ref", ""),
            status.get("error", ""), bool(status.get("talent_delivered")),
            status.get("talent_delivery_error", ""))


def _poll_to_terminal(oteny: Oteny, request_id, *, timeout_s: int, poll_s: int,
                      log) -> tuple[str, str, bool, str]:
    """Poll one request to a terminal state. Returns (state, ref, delivered, error)."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        status = oteny.call(_DEV_BOT_MODEL, "dev_bot_request_status", request_id=request_id)
        terminal, state, ref, error, delivered, delivery_error = parse_status(status)
        if terminal:
            return state, ref, delivered, (error or delivery_error)
        log(f"[dev_bot]   … {state} ({int(deadline - time.time())}s budget left)")
        time.sleep(poll_s)
    return "timeout", "", False, f"provisioning did not finish within {timeout_s}s"


def _request_or_fallback(oteny: Oteny, kwargs: dict, log):
    """Call ``request_dev_bot``, degrading gracefully on a platform that predates D210. An Oteny
    that has no ``dev_slot`` param rejects the kwarg (a `/json/2/` "unexpected keyword argument"
    error); drop it and create fresh (no reuse — the old platform can't). This makes a launcher
    that passes ``dev_slot`` FORWARD- and BACKWARD-compatible, so the platform-vs-launcher deploy
    order never breaks a run."""
    try:
        return oteny.call(_DEV_BOT_MODEL, "request_dev_bot", **kwargs)
    except RuntimeError as exc:
        if "dev_slot" in kwargs and "dev_slot" in str(exc):
            log("[dev_bot] this Oteny predates durable reuse (no dev_slot) — creating fresh.")
            return oteny.call(_DEV_BOT_MODEL, "request_dev_bot",
                              **{k: v for k, v in kwargs.items() if k != "dev_slot"})
        raise


def ensure(oteny: Oteny, *, dev_slot: str, bundle: str, timeout_s: int = DEFAULT_PROVISION_TIMEOUT_S,
           poll_s: int = DEFAULT_POLL_S, log=print, **rk) -> dict:
    """Commission-or-reuse a durable dev bot and poll it to ``active`` (D210 §5.B).

    Calls ``request_dev_bot(dev_slot=…)`` and lets the PLATFORM decide reuse (converge-in-place) vs
    fresh create — this helper never decides. On a **failed reuse target** (the incumbent's clone
    vanished — a node death / backup-reap; ``node_id`` was only a record check) it AUTO-REBUILDS:
    re-issue a plain create (drop ``dev_slot``), which now misses and commissions fresh (§5.C2/R7).

    Returns ``{ref, reused, request_id, delivered, rebuilt}``. Raises RuntimeError on a create
    that fails (not a reuse) or on a refused request."""
    kwargs = request_kwargs(dev_slot=dev_slot, bundle=bundle, **rk)
    accepted = _request_or_fallback(oteny, kwargs, log)
    if not isinstance(accepted, dict) or not accepted.get("accepted"):
        raise RuntimeError(f"request_dev_bot refused: {accepted}")
    reused = bool(accepted.get("reused"))
    request_id = accepted["request_id"]
    log(f"[dev_bot] request_dev_bot accepted (request_id={request_id}, reused={reused}); "
        "provisioning …")
    state, ref, delivered, error = _poll_to_terminal(
        oteny, request_id, timeout_s=timeout_s, poll_s=poll_s, log=log)
    if state == "active" and ref:
        return {"ref": ref, "reused": reused, "request_id": request_id,
                "delivered": delivered, "rebuilt": False}
    # A failed REUSE target → the incumbent is gone; re-issue a plain create (no dev_slot) so it
    # misses and commissions fresh. A create that fails is a real error (raise).
    if reused:
        log(f"[dev_bot] reuse target failed ({error or state}); rebuilding fresh …")
        fresh = dict(kwargs)
        fresh.pop("dev_slot", None)                       # drop the slot → force a create (miss)
        accepted2 = oteny.call(_DEV_BOT_MODEL, "request_dev_bot", **fresh)
        if not isinstance(accepted2, dict) or not accepted2.get("accepted"):
            raise RuntimeError(f"rebuild request_dev_bot refused: {accepted2}")
        rid2 = accepted2["request_id"]
        state2, ref2, delivered2, error2 = _poll_to_terminal(
            oteny, rid2, timeout_s=timeout_s, poll_s=poll_s, log=log)
        if state2 == "active" and ref2:
            return {"ref": ref2, "reused": False, "request_id": rid2,
                    "delivered": delivered2, "rebuilt": True}
        raise RuntimeError(f"rebuild ended in state={state2!r}: {error2 or '(no error)'}")
    raise RuntimeError(f"provisioning ended in state={state!r}: {error or '(no error)'}")


def await_belt_delivery(oteny: Oteny, ref: str, *, window_s: int = 360, poll_s: int = 10,
                        log=print) -> bool:
    """Poll a tenant's external Talent source until every row is ``delivered`` (the 5-min
    deliver-external belt landed the bundle), within a bounded window. Generic across any
    external-git dev bot. Returns True on delivery, False on timeout."""
    deadline = time.time() + window_s
    while time.time() < deadline:
        try:
            rows = oteny.call("hh.talent.source", "search_read",
                              domain=[["tenant_id.ref", "=", ref], ["kind", "=", "external_git"]],
                              fields=["last_status", "last_error"])
        except Exception as exc:  # noqa: BLE001 — a transient read blip must not abort the wait
            log(f"[dev_bot]   (belt poll blip: {exc})")
            rows = None
        if rows and all((r.get("last_status") == "delivered") for r in rows):
            return True
        time.sleep(poll_s)
    return False


def touch(oteny: Oteny, *, ref: str | None = None, dev_slot: str | None = None) -> dict:
    """Keep-alive: stamp the durable bot's idle clock. Surfaces the platform ``live`` flag —
    ``live=False`` means it was reaped/teardown-scheduled, so the caller rebuilds. Select by ref
    (the held bot) or dev_slot (a dev who lost the local state file)."""
    kw = {"ref": ref} if ref else {"dev_slot": dev_slot}
    out = oteny.call(_DEV_BOT_MODEL, "touch_dev_bot", **kw)
    return out if isinstance(out, dict) else {"ok": False, "live": False}


def down(oteny: Oteny, *, ref: str | None = None, dev_slot: str | None = None) -> dict:
    """Explicit self-serve teardown of one of the account's OWN dev bots (by ref or dev_slot)."""
    kw = {"ref": ref} if ref else {"dev_slot": dev_slot}
    out = oteny.call(_DEV_BOT_MODEL, "teardown_dev_bot", **kw)
    return out if isinstance(out, dict) else {"ok": False}


# ── the cloudflared tunnel provisioner (named, stable host; else quick) ─────────────────── #
class Tunnel:
    """A held cloudflared tunnel: a subprocess + its public URL. ``close()`` reaps it. The stable
    NAMED host is a stated precondition of the durable singleton — the already-delivered uplink
    host survives a restart, so reuse is safe; a QUICK tunnel's rotating host degrades to
    repoint-every-run (the platform re-renders it on the reuse converge, D210 R10)."""

    def __init__(self, proc: subprocess.Popen, url: str, *, named: bool):
        self.proc = proc
        self.url = url
        self.named = named

    def alive(self) -> bool:
        return self.proc.poll() is None

    def close(self) -> None:
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()


def open_quick_tunnel(port: int, label: str, *, cloudflared: str = "cloudflared",
                      log=print) -> Tunnel:
    """A cloudflared QUICK tunnel (``--url``, trycloudflare.com) — no CF API token needed, but its
    host ROTATES every run (never an identity — a repointed coord, D210 §3/R10)."""
    proc = subprocess.Popen(
        [cloudflared, "tunnel", "--url", f"http://127.0.0.1:{port}"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    deadline = time.time() + 40
    while time.time() < deadline:
        line = proc.stdout.readline() if proc.stdout else ""
        if not line and proc.poll() is not None:
            raise RuntimeError(f"cloudflared quick tunnel ({label}) exited on startup")
        m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line or "")
        if m:
            log(f"[dev_bot] quick tunnel ({label}) → {m.group(0)}")
            return Tunnel(proc, m.group(0), named=False)
    proc.terminate()
    raise RuntimeError(f"cloudflared quick tunnel ({label}) printed no URL within 40s")


@contextlib.contextmanager
def hold(oteny: Oteny, ref: str, tunnels, *, on_reaped=None,
         heartbeat_s: int = DEFAULT_HEARTBEAT_S, log=print):
    """Hold a DURABLE dev bot: run the keep-alive heartbeat + close the tunnels on stop, but NEVER
    tear the bot down (D210 §5.B/§5.C). A launcher writes ``with dev_bot.hold(oteny, ref, tunnels):
    serve()``. On SIGTERM/SIGHUP/SIGINT ("stop debugging" / a terminal close) this **detaches** —
    closes the passed tunnels and exits WITHOUT calling ``teardown_dev_bot`` — so the singleton
    survives to be REUSED on the next launch. A daemon-thread heartbeat calls ``touch`` every
    ``heartbeat_s`` and invokes ``on_reaped`` (rebuild) if the bot went ``live=False``. Teardown
    happens ONLY via an explicit ``down()`` / the ~18 h idle-TTL reaper."""
    stop = threading.Event()

    class _HoldRelease(Exception):
        pass

    def _release(signum, frame):  # noqa: ARG001
        raise _HoldRelease()

    installed = {}
    for sig in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
        try:
            installed[sig] = signal.signal(sig, _release)
        except (ValueError, OSError):
            pass   # not the main thread — the caller runs single-threaded, so this is belt-only

    def _beat():
        # A daemon thread, independent of the debugged code path, so a breakpoint pause doesn't
        # stop the heartbeat. stop.wait() returns True the instant hold releases → clean exit.
        while not stop.wait(heartbeat_s):
            try:
                res = touch(oteny, ref=ref)
            except Exception as exc:  # noqa: BLE001 — a heartbeat blip is not a reap
                log(f"[dev_bot] heartbeat blip: {exc}")
                continue
            if not res.get("live"):
                log("[dev_bot] the dev bot was reaped (live=False) — rebuilding.")
                if on_reaped:
                    on_reaped()
                return

    hb = threading.Thread(target=_beat, name="dev-bot-heartbeat", daemon=True)
    hb.start()
    try:
        yield
    except (_HoldRelease, KeyboardInterrupt):
        log("[dev_bot] detaching — closing tunnels, LEAVING the dev bot up "
            "(the next launch REUSES it, no ~7-min rebuild).")
    finally:
        stop.set()
        for t in (tunnels or []):
            try:
                t.close()
            except Exception as exc:  # noqa: BLE001 — one tunnel close never blocks the rest
                log(f"[dev_bot] (tunnel close blip: {exc})")
        for sig, prev in installed.items():
            try:
                signal.signal(sig, prev)
            except (ValueError, OSError):
                pass
