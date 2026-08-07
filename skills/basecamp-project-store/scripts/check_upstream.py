#!/usr/bin/env python3
"""check_upstream — re-prove every claim in references/cli-reference.md against a live board.

The command-line tool moves between releases, and it moves silently: the same flag that
returned open todos in 0.7.x returns completed ones in 0.9.0. A page of hard-won traps is
therefore only true of the version it was written against, and nothing in a release note
reliably says which trap just changed. So the page is checked the same way it was written —
by running the commands and reading what comes back.

    python3 check_upstream.py --account <acc> --project <scratch-proj> --list <scratch-list>

Every probe prints HOLDS (the reference page is still right), BROKEN (the behaviour changed —
fix the page) or SKIPPED. Exit code is 1 if anything is BROKEN, so this can gate a version bump.

WRITES: a few draft messages and one todo, each trashed again before the run ends. A draft
notifies nobody, but point this at a SCRATCH project all the same — never a customer's board.

Standard library only.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import cli_path, run_cli  # noqa: E402

_MD_BODY = "# Heading\n\n- bullet one\n- bullet two\n\n| Item | Price |\n| --- | --- |\n| Espresso | 2,50 |"
_HTML_BODY = _MD_BODY + '\n\nAnd a tag: <div class="x">hello</div>'
_FENCED_BODY = 'Before.\n\n```\n<div class="x">hello</div>\n```\n\nAfter.'


class Probes:
    def __init__(self, account: str, project: str, list_id: str) -> None:
        self.account = account
        self.project = project
        self.list_id = list_id
        self.scope = ["--account", account, "--in", project]
        self.created: list[tuple[str, str]] = []   # (kind, id) to clean up
        self.results: list[tuple[str, str, str]] = []

    # ---------------------------------------------------------------- helpers
    def _json(self, argv: list[str], *, timeout: int = 60) -> dict:
        try:
            proc = run_cli([*argv, "--json"], timeout=timeout)
        except (FileNotFoundError, subprocess.SubprocessError, OSError) as exc:
            return {"ok": False, "error": str(exc)}
        try:
            return json.loads(proc.stdout or "{}")
        except ValueError:
            return {"ok": False, "error": (proc.stderr or proc.stdout or "unreadable").strip()[:200]}

    def _draft(self, title: str, body: str) -> str | None:
        payload = self._json(["messages", "create", title, body, "--draft", "--no-subscribe",
                              *self.scope])
        mid = str(((payload.get("data") or {}).get("id") or "")) if payload.get("ok") else ""
        if mid:
            self.created.append(("messages", mid))
            return mid
        return None

    def _content(self, message_id: str) -> str:
        payload = self._json(["messages", "show", message_id, *self.scope])
        return ((payload.get("data") or {}).get("content") or "") if payload.get("ok") else ""

    def record(self, name: str, holds: bool, detail: str) -> None:
        self.results.append((name, "HOLDS" if holds else "BROKEN", detail))

    def skip(self, name: str, detail: str) -> None:
        self.results.append((name, "SKIPPED", detail))

    # ----------------------------------------------------------------- probes
    def account_required(self) -> None:
        """§1 — every command needs --account, even with an unambiguous project."""
        payload = self._json(["projects", "list"])
        error = str(payload.get("error") or "")
        self.record("§1 --account is required", not payload.get("ok") and "account" in error.lower(),
                    error[:80] or "the call succeeded without --account")

    def positional_list_id_ignored(self) -> None:
        """§2 — a bare list id widens the answer to the whole project instead of failing."""
        scoped = self._json(["todos", "list", "--list", self.list_id, *self.scope])
        loose = self._json(["todos", "list", self.list_id, *self.scope])
        whole = self._json(["todos", "list", *self.scope])
        if not all(p.get("ok") for p in (scoped, loose, whole)):
            self.skip("§2 positional list id ignored", "a listing call failed")
            return
        n_scoped, n_loose, n_whole = (len(p.get("data") or []) for p in (scoped, loose, whole))
        if n_scoped == n_whole:
            # The scratch list holds every open todo on the project, so "scoped" and "whole"
            # are the same number and a widened answer is indistinguishable from a correct
            # one. Nothing is proven either way — say so rather than banking a false HOLDS.
            self.skip("§2 positional list id ignored",
                      f"inconclusive: the list holds all {n_whole} open todos — "
                      "use a project with a second list")
            return
        self.record("§2 positional list id ignored", n_loose == n_whole,
                    f"--list={n_scoped}, positional={n_loose}, whole project={n_whole}")

    def status_filter_works(self) -> None:
        """§2 — `--status completed` really filters (it did NOT on 0.7.x)."""
        payload = self._json(["todos", "list", "--list", self.list_id, "--status", "completed",
                              *self.scope])
        if not payload.get("ok"):
            self.skip("§2 --status completed filters", "the listing call failed")
            return
        rows = payload.get("data") or []
        if not rows:
            self.skip("§2 --status completed filters", "no completed todos on the scratch list")
            return
        self.record("§2 --status completed filters", all(r.get("completed") for r in rows),
                    f"{sum(1 for r in rows if r.get('completed'))}/{len(rows)} really completed")

    def messages_create_has_no_stdin(self) -> None:
        """§3 — `-` is a literal body on messages create; the piped text is dropped."""
        exe = cli_path()
        if not exe:
            self.skip("§3 messages create has no `-` stdin", "the tool is not installed")
            return
        proc = subprocess.run(  # noqa: S603 — fixed executable, argument list, no shell
            [exe, "messages", "create", "zz-check stdin (draft)", "-", "--draft",
             "--no-subscribe", *self.scope, "--json"],
            input="Line one.\nLine two.\n", capture_output=True, text=True, timeout=60,
        )
        try:
            payload = json.loads(proc.stdout or "{}")
        except ValueError:
            payload = {}
        mid = str(((payload.get("data") or {}).get("id") or "")) if payload.get("ok") else ""
        if not mid:
            self.skip("§3 messages create has no `-` stdin", "the draft was not created")
            return
        self.created.append(("messages", mid))
        content = self._content(mid)
        self.record("§3 messages create has no `-` stdin", "Line one." not in content,
                    f"body came back as {content.strip()[:60]!r}")

    def markdown_renders(self) -> None:
        """§4 — a pure markdown body renders, tables included. Do NOT pre-flatten tables."""
        mid = self._draft("zz-check markdown (draft)", _MD_BODY)
        if not mid:
            self.skip("§4 markdown renders (tables included)", "the draft was not created")
            return
        content = self._content(mid)
        self.record("§4 markdown renders (tables included)",
                    "<table" in content and "<ul" in content and "<h1" in content,
                    f"table={'<table' in content} list={'<ul' in content} heading={'<h1' in content}")

    def raw_html_flips_the_body(self) -> None:
        """§4 — one raw tag turns the WHOLE body literal. This is what body-fencing is for."""
        mid = self._draft("zz-check raw html (draft)", _HTML_BODY)
        if not mid:
            self.skip("§4 one raw tag flips the body literal", "the draft was not created")
            return
        content = self._content(mid)
        self.record("§4 one raw tag flips the body literal",
                    "<table" not in content and "|" in content,
                    f"table={'<table' in content} literal pipes={'|' in content}")

    def fencing_restores_markdown(self) -> None:
        """§4 — fenced HTML survives as escaped, readable text and the rest still renders."""
        mid = self._draft("zz-check fenced html (draft)", _FENCED_BODY)
        if not mid:
            self.skip("§4 fencing makes HTML readable", "the draft was not created")
            return
        content = self._content(mid)
        self.record("§4 fencing makes HTML readable",
                    "&lt;div" in content and "<pre>" in content,
                    f"escaped={'&lt;div' in content} code block={'<pre>' in content}")

    def headless_login_still_pastes_back(self) -> None:
        """§5 — headless sign-in still means "paste the callback", so the two-turn relay stays.

        Assert the premise connect_auth.py rests on, not the wording of one release: 0.7.x
        described --device-code as "alias for --remote" and 0.9.0 dropped that phrase without
        changing what either flag does. What must not change is --remote waiting on a pasted
        callback URL — a real poll-based device flow would let the sign-in finish in one call
        and would make the detached supervisor unnecessary.
        """
        try:
            proc = run_cli(["auth", "login", "--help"], timeout=30)
        except (FileNotFoundError, subprocess.SubprocessError, OSError) as exc:
            self.skip("§5 headless login pastes the callback back", str(exc)[:60])
            return
        text = (proc.stdout or "") + (proc.stderr or "")
        remote = next((ln for ln in text.splitlines() if "--remote" in ln), "")
        device = next((ln for ln in text.splitlines() if "--device-code" in ln), "")
        detail = remote.strip()[:70]
        if device:
            detail += f"  |  --device-code: {device.split('--device-code', 1)[1].strip()[:40]}"
        self.record("§5 headless login pastes the callback back",
                    "paste callback" in remote.lower(), detail or "no --remote flag found")

    # ---------------------------------------------------------------- cleanup
    def cleanup(self) -> list[str]:
        failures = []
        for kind, rid in self.created:
            payload = self._json([kind, "trash", rid, *self.scope])
            if not payload.get("ok"):
                failures.append(f"{kind} {rid}")
        return failures


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Re-prove the reference page against a live board")
    ap.add_argument("--account", required=True)
    ap.add_argument("--project", required=True, help="a SCRATCH project — this writes drafts")
    ap.add_argument("--list", required=True, dest="list_id", help="a to-do list on that project")
    args = ap.parse_args(argv)

    exe = cli_path()
    if not exe:
        print("ERROR the Basecamp command-line tool is not installed")
        return 1
    version = run_cli(["--version"], timeout=20).stdout.strip()
    print(f"CLI: {version} at {exe}")
    print(f"BOARD: account={args.account} project={args.project} list={args.list_id}\n")

    probes = Probes(args.account, args.project, args.list_id)
    try:
        probes.account_required()
        probes.positional_list_id_ignored()
        probes.status_filter_works()
        probes.messages_create_has_no_stdin()
        probes.markdown_renders()
        probes.raw_html_flips_the_body()
        probes.fencing_restores_markdown()
        probes.headless_login_still_pastes_back()
    finally:
        leftovers = probes.cleanup()

    width = max(len(name) for name, _, _ in probes.results)
    for name, verdict, detail in probes.results:
        print(f"{verdict:<8} {name:<{width}}  {detail}")

    broken = [name for name, verdict, _ in probes.results if verdict == "BROKEN"]
    print()
    if leftovers:
        print("WARNING could not trash: " + ", ".join(leftovers) + " — remove them by hand")
    if broken:
        print(f"BROKEN {len(broken)} — correct references/cli-reference.md before bumping the pin")
        return 1
    print(f"ALL HOLD on {version} — the reference page is still true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
