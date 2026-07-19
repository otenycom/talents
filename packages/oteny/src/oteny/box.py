"""Account-scoped client for the box-access lanes (D199/D201) — the DOGFOOD-compliant
way for an author's dev-loop tooling to look inside its OWN bot box.

Why this exists (the boundary ``tests/test_dogfood_boundary.py`` enforces): an
author-facing dev-loop entrypoint (``test``/``logs``/``selfcheck``/``traces``) must run
with nothing but the account's ``/json/2/`` key — an external Talent author (Cuneus /
Vriend Studio) has no operator ``hermeshost-mgmt`` SSH key and no root on the nodes. So
where a verb needs to reach into the box, it goes through THIS client, and the control
plane does the privileged node hop server-side (D193). The recurring dogfood-bypass bug
was tooling grabbing ``settings.mgmt_ssh_key_path`` + ``asyncssh`` directly because the
mgmt key is ambient on ``Settings``; this class deliberately holds **only** an
``OdooClient`` (the account key) — the mgmt key is not in its scope to grab.

Two public box-access lanes, mirroring ``hh.box_access_request`` (D199):

* :meth:`inspect` — a one-call, account-scoped, REDACTED snapshot (config / env-var
  *names* / installed Talents / a 200-line log tail / sudoers posture). Light, no tunnel.
  Good for a quick "what state is the box in".
* :meth:`shell` — a context manager yielding an ``exec(cmd) -> stdout`` over an ephemeral,
  **account-owned** Cloudflare tunnel (D201): the worker mints ``box-<rid>.oteny.bot`` and
  authorizes OUR ephemeral pubkey; we bridge locally with ``cloudflared access tcp`` and
  SSH in with our own throwaway key. Full fidelity (the whole log, any file, run a bundle
  script) for when the redacted snapshot is not enough. The window + local bridge are torn
  down on exit (and the box's model key is rotated by the reaper).

The trace/log HARVEST lane (``hh.hermes.session``/``.message``/``.event`` over ``/json/2/``,
via :func:`oteny.traces.build_traces_dto`) is account-scoped already and needs no
client here — it is read directly with the account ``OdooClient``.
"""
from __future__ import annotations

import contextlib
import logging
import os
import socket
import subprocess
import tempfile
import time
from collections.abc import Callable, Iterator

log = logging.getLogger(__name__)

_BOX_MODEL = "hh.box_access_request"


class BoxAccessError(RuntimeError):
    """A box-access lane could not be opened / completed over ``/json/2/``."""


class AuthorBoxAccess:
    """Account-scoped box introspection. Constructed with ONLY an account ``OdooClient``
    (never ``Settings`` / the mgmt key). ``sleep``/``clock``/``run`` are injected so the
    lanes unit-test offline with no real Odoo, cloudflared, or ssh."""

    def __init__(
        self,
        client,
        *,
        cloudflared_bin: str = "cloudflared",
        ssh_bin: str = "ssh",
        keygen_bin: str = "ssh-keygen",
        poll_s: float = 5.0,
        inspect_timeout_s: float = 180.0,
        shell_timeout_s: float = 120.0,
        sleep: Callable[[float], None] | None = None,
        clock: Callable[[], float] | None = None,
        run: Callable[..., subprocess.CompletedProcess] | None = None,
        popen: Callable[..., subprocess.Popen] | None = None,
    ) -> None:
        # The account /json/2/ seam — the ONLY credential this client holds. There is no
        # settings/mgmt-ssh-key attribute here on purpose (the dogfood boundary).
        self._client = client
        self._cloudflared = cloudflared_bin
        self._ssh = ssh_bin
        self._keygen = keygen_bin
        self._poll_s = poll_s
        self._inspect_timeout_s = inspect_timeout_s
        self._shell_timeout_s = shell_timeout_s
        self._sleep = sleep or time.sleep
        self._clock = clock or time.monotonic
        self._run = run or _default_run
        self._popen = popen or subprocess.Popen

    # ── inspect lane (redacted snapshot, no tunnel) ─────────────────────────── #

    def inspect(self, ref: str) -> dict:
        """Request an ``inspect`` window and poll it to ``done`` → the redacted snapshot
        dict (``log_tails``/``config_yaml``/``env_keys``/``manifest``/``talents_tree``/…).
        Raises :class:`BoxAccessError` on refusal / failure / timeout."""
        rid = self._open("inspect", ref)
        return self._await_inspect(rid)

    def gateway_log_tail(self, ref: str) -> str:
        """The box's redacted ``gateway.log`` tail (200 lines) via :meth:`inspect`."""
        return ((self.inspect(ref).get("log_tails") or {}).get("gateway.log")) or ""

    # ── shell lane (ephemeral account-owned CF tunnel; full access) ─────────── #

    @contextlib.contextmanager
    def shell(self, ref: str) -> Iterator[Callable[[str], str]]:
        """Open an ephemeral, account-scoped SSH lane into ``ref`` and yield
        ``exec(cmd) -> stdout``. Mints a throwaway keypair, opens a ``shell`` window
        (authorizing our pubkey), brings up the ``cloudflared access tcp`` local bridge, and
        SSHes in with our own key. On exit: close the window + reap the local bridge + temp
        key. The box's disclosed-key grant is rotated server-side by the reaper (D201)."""
        rid = None
        tmp = tempfile.mkdtemp(prefix="oteny-box-shell-")
        bridge: subprocess.Popen | None = None
        try:
            key_path = os.path.join(tmp, "id_ed25519")
            pub = self._keygen_ephemeral(key_path)
            rid = self._open("shell", ref, ssh_pubkey=pub)
            connect = self._await_shell(rid)
            hostname = connect.get("hostname")
            user = connect.get("user") or "hermes"
            if not hostname:
                raise BoxAccessError(f"shell window {rid} for {ref!r} has no hostname")
            self._wait_dns(hostname)
            local_port = _free_local_port()
            bridge = self._start_bridge(hostname, local_port)
            self._wait_ssh_ready(key_path, user, local_port)

            def _exec(cmd: str) -> str:
                res = self._run(
                    [self._ssh, "-p", str(local_port), "-i", key_path,
                     "-o", "StrictHostKeyChecking=accept-new",
                     "-o", "UserKnownHostsFile=/dev/null",
                     "-o", "BatchMode=yes", "-o", "ConnectTimeout=15",
                     "-o", "LogLevel=ERROR",
                     f"{user}@127.0.0.1", cmd],
                    capture_output=True, text=True, timeout=120)
                if res.returncode != 0:
                    raise BoxAccessError(
                        f"shell exec failed (rc={res.returncode}) on {ref!r}: "
                        f"{(res.stderr or '').strip()[:300]}")
                return res.stdout or ""

            yield _exec
        finally:
            if bridge is not None:
                with contextlib.suppress(Exception):
                    bridge.terminate()
                    bridge.wait(timeout=10)
            if rid is not None:
                with contextlib.suppress(Exception):
                    self._client.call(_BOX_MODEL, "close_box_access", request_id=rid)
            with contextlib.suppress(Exception):
                _rmtree(tmp)

    # ── internals (seam + subprocess; injected for tests) ────────────────────── #

    def _open(self, kind: str, ref: str, *, ssh_pubkey: str | None = None) -> int:
        kw: dict = {"ref": ref, "kind": kind}
        if ssh_pubkey is not None:
            kw["ssh_pubkey"] = ssh_pubkey
        resp = self._client.call(_BOX_MODEL, "request_box_access", **kw) or {}
        if not resp.get("accepted"):
            raise BoxAccessError(
                f"box-access {kind} refused for {ref!r}: "
                f"{resp.get('reason') or resp.get('http') or resp}")
        rid = resp.get("request_id")
        if not rid:
            raise BoxAccessError(f"box-access {kind} accepted but no request_id: {resp}")
        return int(rid)

    def _await_inspect(self, rid: int) -> dict:
        deadline = self._clock() + self._inspect_timeout_s
        while self._clock() < deadline:
            st = self._client.call(_BOX_MODEL, "box_access_status", request_id=rid) or {}
            if not st.get("ok"):
                raise BoxAccessError(f"inspect status {rid}: {st.get('reason') or st}")
            if st.get("state") == "done":
                return st.get("snapshot") or {}
            if st.get("terminal"):  # failed
                raise BoxAccessError(f"inspect {rid} failed: {st.get('error') or st}")
            self._sleep(self._poll_s)
        raise BoxAccessError(f"inspect {rid} did not complete in {self._inspect_timeout_s}s")

    def _await_shell(self, rid: int) -> dict:
        deadline = self._clock() + self._shell_timeout_s
        while self._clock() < deadline:
            st = self._client.call(_BOX_MODEL, "box_access_status", request_id=rid) or {}
            if not st.get("ok"):
                raise BoxAccessError(f"shell status {rid}: {st.get('reason') or st}")
            if st.get("state") == "active" and st.get("connect_info"):
                return st["connect_info"]
            if st.get("terminal"):  # done/failed before it went active
                raise BoxAccessError(f"shell {rid} ended before active: {st.get('error') or st}")
            self._sleep(self._poll_s)
        raise BoxAccessError(f"shell {rid} did not go active in {self._shell_timeout_s}s")

    def _keygen_ephemeral(self, key_path: str) -> str:
        self._run([self._keygen, "-t", "ed25519", "-N", "", "-q", "-f", key_path],
                  capture_output=True, text=True, timeout=30, check=True)
        with open(key_path + ".pub", encoding="utf-8") as fh:
            return fh.read().strip()

    def _wait_dns(self, hostname: str) -> None:
        """Hold the FIRST local query of the freshly-minted tunnel hostname until the
        record exists at a public resolver. Each shell window mints a brand-new
        ``box-<rid>`` DNS route; a query fired before it propagates gets an NXDOMAIN the
        OS resolver NEGATIVE-CACHES (macOS), which then poisons every ssh retry inside
        the 45 s bridge budget as ``kex … connection reset by peer`` (live-hit
        2026-07-12 — the same fresh-CNAME class the dev-bot launcher documents). Probing
        a DIRECT resolver never touches the OS cache, so waiting here means the bridge's
        first real lookup lands after the record exists. Best-effort: on timeout (or no
        ``dig`` on the host) proceed — the ssh wait still has its own budget."""
        deadline = self._clock() + 90.0
        while self._clock() < deadline:
            try:
                res = self._run(
                    ["dig", "+short", "+time=3", "+tries=1", "@1.1.1.1", hostname],
                    capture_output=True, text=True, timeout=10)
            except Exception:  # noqa: BLE001 — no dig → skip the belt entirely
                return
            if (res.stdout or "").strip():
                return
            self._sleep(3.0)

    def _start_bridge(self, hostname: str, local_port: int) -> subprocess.Popen:
        # The D201 local-listener form: raw TCP-over-WS with no Cloudflare Access (the SSH
        # pubkey is the gate). Backgrounds a listener on 127.0.0.1:<local_port>.
        return self._popen(
            [self._cloudflared, "access", "tcp", "--hostname", hostname,
             "--url", f"127.0.0.1:{local_port}"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _wait_ssh_ready(self, key_path: str, user: str, local_port: int) -> None:
        deadline = self._clock() + 45.0
        last = ""
        while self._clock() < deadline:
            res = self._run(
                [self._ssh, "-p", str(local_port), "-i", key_path,
                 "-o", "StrictHostKeyChecking=accept-new",
                 "-o", "UserKnownHostsFile=/dev/null", "-o", "BatchMode=yes",
                 "-o", "ConnectTimeout=8", "-o", "LogLevel=ERROR",
                 f"{user}@127.0.0.1", "true"],
                capture_output=True, text=True, timeout=20)
            if res.returncode == 0:
                return
            last = (res.stderr or "").strip()
            self._sleep(2.0)
        raise BoxAccessError(f"ssh bridge never came up on 127.0.0.1:{local_port}: {last[:200]}")


def _default_run(cmd, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, **kw)


def _free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _rmtree(path: str) -> None:
    import shutil
    shutil.rmtree(path, ignore_errors=True)
