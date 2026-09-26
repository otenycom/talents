"""oteny — account-key author CLI."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

from .box import BoxAccessError


def _emit(obj) -> None:
    print(json.dumps(obj, indent=2, default=str))


def _client(args):
    from .client import client_from_key_file
    key = args.api_key_file or os.environ.get("OTENY_ACCOUNT_KEY") or os.environ.get(
        "OTENY_API_KEY_FILE")
    if not key:
        raise SystemExit(
            "pass --api-key-file or set OTENY_ACCOUNT_KEY to your account key file")
    return client_from_key_file(
        key, base_url=getattr(args, "base_url", None) or os.environ.get("OTENY_BASE_URL"))


def cmd_test(args) -> int:
    from .runner import run_scenarios_for_clone
    if not args.bundle_dir:
        raise SystemExit("--bundle-dir is required (local Talent checkout; no deploy key)")
    client = _client(args)
    report = run_scenarios_for_clone(
        client, args.ref, args.bundle,
        bundle_dir=args.bundle_dir,
        shared_dir=args.shared_dir,
        scenario_globs=args.scenario or None,
        transport=args.transport,
        junit=args.junit,
    )
    _emit(report)
    return 0 if report.get("ok") else 1


def cmd_traces(args) -> int:
    from .traces import build_traces_dto
    client = _client(args)
    _emit(build_traces_dto(client, args.ref, session=args.session, since=args.since,
                           limit=args.limit, photos=bool(getattr(args, "photos", False))))
    return 0


def cmd_lint(args) -> int:
    from .lint import lint_talent_dir
    dirs = args.dirs or []
    if not dirs:
        raise SystemExit("pass one or more Talent bundle directories")
    ok = True
    for d in dirs:
        out = lint_talent_dir(d, catalog_dir=args.catalog_dir)
        _emit(out)
        ok = ok and bool(out.get("ok"))
    return 0 if ok else 1


def cmd_inspect(args) -> int:
    from .box import AuthorBoxAccess
    client = _client(args)
    _emit(AuthorBoxAccess(client).inspect(args.ref))
    return 0


def cmd_shell(args) -> int:
    from .box import AuthorBoxAccess
    client = _client(args)
    with AuthorBoxAccess(client).shell(args.ref) as sh:
        if args.cmd:
            print(sh(args.cmd), end="" if str(args.cmd).endswith("\n") else "\n")
            return 0
        print(f"# box shell open for {args.ref} — pass --cmd '…' (interactive TTY TBD)",
              file=sys.stderr)
        return 2


def cmd_request_staging_run(args) -> int:
    client = _client(args)
    out = client.call(
        "hh.talent.staging_run", "request_staging_run",
        source_id=args.source_id, commit_sha=args.commit or None)
    _emit(out)
    return 0 if out.get("accepted") else 1


def cmd_staging_run_status(args) -> int:
    client = _client(args)
    out = client.call(
        "hh.talent.staging_run", "staging_run_status", run_id=args.run_id)
    _emit(out)
    return 0


def cmd_clone(args) -> int:
    """Account-key clone gate — platform worker drains infra."""
    client = _client(args)
    out = client.call(
        "hh.tenant", "request_clone",
        source_ref=args.source, cloner_uid=args.cloner_uid or "",
        internal=False, no_neutralize=bool(args.no_neutralize))
    _emit(out)
    return 0 if out.get("accepted") or out.get("ok") else 1


def cmd_logs(args) -> int:
    """Account-scoped logs via harvest traces (+ optional inspect gateway tail)."""
    from .traces import build_traces_dto
    client = _client(args)
    dto = build_traces_dto(client, args.ref, limit=args.limit)
    if args.gateway_tail:
        from .box import AuthorBoxAccess
        dto["gateway_log_tail"] = AuthorBoxAccess(client).gateway_log_tail(args.ref)
    _emit(dto)
    return 0


def cmd_selfcheck(args) -> int:
    from .box import AuthorBoxAccess
    client = _client(args)
    script = args.script or (
        f"test -x ~/.hermes/skills/talents/{args.bundle}/scripts/selfcheck.py && "
        f"python3 ~/.hermes/skills/talents/{args.bundle}/scripts/selfcheck.py --json "
        f"|| python3 -c 'print({{\"ok\": false, \"error\": \"no selfcheck\"}})'"
    )
    with AuthorBoxAccess(client).shell(args.ref) as sh:
        out = sh(script)
    try:
        _emit(json.loads(out))
    except json.JSONDecodeError:
        print(out)
    return 0


def cmd_migrate_talent(args) -> int:
    from .box import AuthorBoxAccess
    client = _client(args)
    cmd = (
        f"python3 ~/.hermes/skills/talents/{args.bundle}/scripts/migrate.py "
        f"--json 2>/dev/null || echo '{{\"ok\": false, \"error\": \"no migrate.py\"}}'"
    )
    with AuthorBoxAccess(client).shell(args.ref) as sh:
        out = sh(cmd)
    try:
        _emit(json.loads(out))
    except json.JSONDecodeError:
        print(out)
    return 0


def cmd_reload(args) -> int:
    """Ask the platform to re-deliver external Talents for --ref (account-scoped).

    Calls ``hh.tenant.request_talent_reload``, which enqueues a forced talents
    converge. Falls back with a hint if that seam is missing on an older Odoo.
    """
    client = _client(args)
    # Prefer an explicit Odoo method if present; otherwise surface honesty.
    try:
        out = client.call("hh.tenant", "request_talent_reload", ref=args.ref)
        _emit(out)
        return 0 if out.get("accepted") or out.get("ok") else 1
    except RuntimeError as e:
        _emit({
            "ok": False,
            "ref": args.ref,
            "error": str(e),
            "hint": (
                "request_talent_reload seam missing — use request-staging-run for CI, "
                "or wait for the deliver-external-talents belt / Path B inline delivery"),
        })
        return 2


# ── the devbot environment: repository credentials, dev branches, promote mode ────── #
# Each verb is one account-scoped seam. The platform checks the caller owns the bot and
# the repository; the CLI only carries the call. A repository token never rides argv:
# it comes from a file or stdin.
_CRED = "hh.talent.repo_credential"
_BRANCH = "hh.talent.dev_branch"
_SOURCE = "hh.talent.source"
# States a dev branch rests in; --wait polls until one of them, with no job pending.
_BRANCH_REST = {"open", "green", "red", "promoted", "closed", "failed"}
# The rest states a verb counts as success when it waits.
_WAIT_OK = {"test": {"green"}, "promote": {"promoted"}, "open": {"open"},
            "close": {"closed"}}


def _call(args, model: str, method: str, **kw) -> int:
    out = _client(args).call(model, method, **kw)
    _emit(out)
    return 0 if out.get("ok") else 1


def _wait_branch(args, client, branch_id: int, verb: str) -> int:
    """Poll a dev branch until it rests (no job, a rest state) or --wait runs out.
    Exit 0 when it rests where the verb wanted, 1 when it rests elsewhere, 2 on the
    deadline — so a script ends on a fact, never a guess."""
    deadline = time.monotonic() + args.wait
    while True:
        out = client.call(_BRANCH, "dev_branch_status", dev_branch_id=branch_id)
        if not out.get("ok"):
            _emit(out)
            return 1
        if not out.get("job") and out.get("state") in _BRANCH_REST:
            _emit(out)
            return 0 if out["state"] in _WAIT_OK.get(verb, _BRANCH_REST) else 1
        if time.monotonic() >= deadline:
            _emit({**out, "timed_out": True})
            return 2
        time.sleep(5)


def _branch_verb(args, method: str, verb: str, **kw) -> int:
    client = _client(args)
    out = client.call(_BRANCH, method, **kw)
    if not out.get("ok") or not getattr(args, "wait", 0):
        _emit(out)
        return 0 if out.get("ok") else 1
    return _wait_branch(args, client, int(out.get("dev_branch_id") or kw["dev_branch_id"]), verb)


def cmd_repo_key_create(args) -> int:
    return _call(args, _CRED, "repo_credential_create", repo=args.repo)


def cmd_repo_key_check(args) -> int:
    return _call(args, _CRED, "repo_credential_check", repo=args.repo)


def cmd_repo_key_list(args) -> int:
    return _call(args, _CRED, "repo_credentials")


def cmd_repo_key_remove(args) -> int:
    return _call(args, _CRED, "repo_credential_remove", repo=args.repo)


def cmd_repo_token_set(args) -> int:
    if args.token_stdin:
        token = sys.stdin.read().strip()
    elif args.token_file:
        with open(args.token_file, encoding="utf-8") as fh:
            token = fh.read().strip()
    else:
        token = os.environ.get("OTENY_REPO_TOKEN", "").strip()
    if not token:
        raise SystemExit("pass --token-file, --token-stdin, or set OTENY_REPO_TOKEN")
    return _call(args, _CRED, "repo_credential_set_token", repo=args.repo, token=token,
                 username=args.username or "")


def cmd_branch_open(args) -> int:
    return _branch_verb(args, "dev_branch_open", "open", source_id=args.source_id,
                        name=args.name, delete_branch_on_close=args.delete_branch_on_close)


def cmd_branch_list(args) -> int:
    return _call(args, _BRANCH, "dev_branches", source_id=args.source_id)


def cmd_branch_status(args) -> int:
    return _call(args, _BRANCH, "dev_branch_status", dev_branch_id=args.id)


def cmd_branch_test(args) -> int:
    return _branch_verb(args, "dev_branch_test", "test", dev_branch_id=args.id)


def cmd_branch_promote(args) -> int:
    return _branch_verb(args, "dev_branch_promote", "promote", dev_branch_id=args.id)


def cmd_branch_close(args) -> int:
    return _branch_verb(args, "dev_branch_close", "close", dev_branch_id=args.id,
                        delete_branch=args.delete_branch)


def cmd_link_add_git(args) -> int:
    return _call(args, _SOURCE, "talent_link_add_git", bot_ref=args.ref, slug=args.slug,
                 repo=args.repo, repo_subpath=args.path, branch=args.branch)


def cmd_link_promote_mode(args) -> int:
    return _call(args, _SOURCE, "set_promote_mode", source_id=args.source_id,
                 promote_mode=args.set)


def _add_devbot_verbs(sub) -> None:
    """``repo-key``, ``repo-token``, ``branch`` and ``link`` — the devbot environment."""
    rk = sub.add_parser("repo-key", help="Your repository deploy keys").add_subparsers(
        dest="repo_key_cmd", required=True)
    for name, func, needs_repo, text in (
            ("create", cmd_repo_key_create, True, "Generate a deploy key; prints its public half"),
            ("check", cmd_repo_key_check, True, "Ask the platform to check read and write access"),
            ("list", cmd_repo_key_list, False, "Your repository credentials (no secrets)"),
            ("remove", cmd_repo_key_remove, True, "Remove a credential (revoke it at the host too)")):
        p = rk.add_parser(name, help=text)
        _add_auth(p)
        if needs_repo:
            p.add_argument("--repo", required=True)
        p.set_defaults(func=func)

    rt = sub.add_parser("repo-token", help="A repository-scoped HTTPS token").add_subparsers(
        dest="repo_token_cmd", required=True)
    p = rt.add_parser("set", help="Store a token for any git host (read from a file or stdin)")
    _add_auth(p)
    p.add_argument("--repo", required=True, help="The repository's https:// URL")
    source = p.add_mutually_exclusive_group()
    source.add_argument("--token-file", default=None)
    source.add_argument("--token-stdin", action="store_true")
    p.add_argument("--username", default="",
                   help="Only when the host needs one (Bitbucket: x-token-auth)")
    p.set_defaults(func=cmd_repo_token_set)

    br = sub.add_parser("branch", help="Dev branches: open, test, promote, close").add_subparsers(
        dest="branch_cmd", required=True)
    p = br.add_parser("open", help="Open a dev branch on one of your Talent links")
    _add_auth(p)
    p.add_argument("--source-id", type=int, required=True, help="The Talent link's id")
    p.add_argument("--name", required=True, help="lower-case, digits and dashes")
    p.add_argument("--delete-branch-on-close", action="store_true")
    p.add_argument("--wait", type=int, default=0, help="Seconds to wait for the dev bot")
    p.set_defaults(func=cmd_branch_open)
    p = br.add_parser("list", help="Your dev branches")
    _add_auth(p)
    p.add_argument("--source-id", type=int, default=None)
    p.set_defaults(func=cmd_branch_list)
    for name, func, text in (("status", cmd_branch_status, "One dev branch"),
                             ("test", cmd_branch_test, "Save the dev bot's edits, then test"),
                             ("promote", cmd_branch_promote, "Ship the green commit")):
        p = br.add_parser(name, help=text)
        _add_auth(p)
        p.add_argument("--id", type=int, required=True)
        if name != "status":
            p.add_argument("--wait", type=int, default=0, help="Seconds to wait for the result")
        p.set_defaults(func=func)
    p = br.add_parser("close", help="End a dev branch and free its dev bot")
    _add_auth(p)
    p.add_argument("--id", type=int, required=True)
    p.add_argument("--delete-branch", action="store_true", default=None)
    p.add_argument("--wait", type=int, default=0)
    p.set_defaults(func=cmd_branch_close)

    lk = sub.add_parser("link", help="Settings of one Talent link").add_subparsers(
        dest="link_cmd", required=True)
    p = lk.add_parser("add-git", help="Link a Talent from your repository onto your bot")
    _add_auth(p)
    p.add_argument("--ref", required=True, help="The bot's ref")
    p.add_argument("--slug", required=True)
    p.add_argument("--repo", required=True)
    p.add_argument("--path", required=True, help="The Talent's folder inside the repository")
    p.add_argument("--branch", required=True, help="The provider branch the bot follows")
    p.set_defaults(func=cmd_link_add_git)
    p = lk.add_parser("promote-mode", help="How a green dev branch reaches the provider branch")
    _add_auth(p)
    p.add_argument("--source-id", type=int, required=True)
    p.add_argument("--set", required=True, choices=("fast_forward", "pull_request"))
    p.set_defaults(func=cmd_link_promote_mode)


def _add_auth(p: argparse.ArgumentParser) -> None:
    p.add_argument("--api-key-file", default=None,
                   help="Account API key file (or OTENY_ACCOUNT_KEY)")
    p.add_argument("--base-url", default=None, help="Default https://oteny.odoo.com")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="oteny", description="Oteny author CLI (account key)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("test", help="Run graded live scenarios")
    _add_auth(p)
    p.add_argument("--ref", required=True)
    p.add_argument("--bundle", required=True)
    p.add_argument("--bundle-dir", required=True)
    p.add_argument("--shared-dir", default=None)
    p.add_argument("--scenario", action="append", default=[])
    p.add_argument("--transport", choices=("auto", "discuss", "cli"), default="auto")
    p.add_argument("--junit", default=None)
    p.set_defaults(func=cmd_test)

    p = sub.add_parser("traces", help="Structured debug traces")
    _add_auth(p)
    p.add_argument("--ref", required=True)
    p.add_argument("--session", default=None)
    p.add_argument("--since", default=None)
    p.add_argument("--limit", type=int, default=5)
    p.add_argument("--photos", action="store_true",
                   help="Attach each archived page's photo (visible text, aim, "
                        "option list — never HTML) to its page_snapshot row")
    p.set_defaults(func=cmd_traces)

    p = sub.add_parser("lint", help="Offline Talent lint")
    p.add_argument("dirs", nargs="*")
    p.add_argument("--catalog-dir", default=None)
    p.set_defaults(func=cmd_lint)

    p = sub.add_parser("inspect", help="Redacted box snapshot")
    _add_auth(p)
    p.add_argument("--ref", required=True)
    p.set_defaults(func=cmd_inspect)

    p = sub.add_parser("shell", help="Account-scoped box shell exec")
    _add_auth(p)
    p.add_argument("--ref", required=True)
    p.add_argument("--cmd", default=None)
    p.set_defaults(func=cmd_shell)

    p = sub.add_parser("logs", help="Account-scoped logs / harvest")
    _add_auth(p)
    p.add_argument("--ref", required=True)
    p.add_argument("--limit", type=int, default=5)
    p.add_argument("--gateway-tail", action="store_true")
    p.set_defaults(func=cmd_logs)

    p = sub.add_parser("selfcheck", help="Run Talent selfcheck on the box")
    _add_auth(p)
    p.add_argument("--ref", required=True)
    p.add_argument("--bundle", required=True)
    p.add_argument("--script", default=None)
    p.set_defaults(func=cmd_selfcheck)

    p = sub.add_parser("migrate-talent", help="Run Talent migrate.py on the box")
    _add_auth(p)
    p.add_argument("--ref", required=True)
    p.add_argument("--bundle", required=True)
    p.set_defaults(func=cmd_migrate_talent)

    p = sub.add_parser("clone", help="Request an author clone (gate)")
    _add_auth(p)
    p.add_argument("--source", required=True)
    p.add_argument("--cloner-uid", default="")
    p.add_argument("--no-neutralize", action="store_true")
    p.set_defaults(func=cmd_clone)

    p = sub.add_parser("reload", help="Request Talent reload for a bot")
    _add_auth(p)
    p.add_argument("--ref", required=True)
    p.set_defaults(func=cmd_reload)

    p = sub.add_parser("request-staging-run", help="Enqueue CI staging grade")
    _add_auth(p)
    p.add_argument("--source-id", type=int, required=True)
    p.add_argument("--commit", default=None)
    p.set_defaults(func=cmd_request_staging_run)

    p = sub.add_parser("staging-run-status", help="Poll staging run")
    _add_auth(p)
    p.add_argument("--run-id", type=int, required=True)
    p.set_defaults(func=cmd_staging_run_status)

    _add_devbot_verbs(sub)

    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args) or 0)
    except BoxAccessError as exc:
        # One sentence, not a traceback: the platform's own answer is the message.
        print(f"box access: {exc}", file=sys.stderr)
        return 1


def lint_main(argv: list[str] | None = None) -> int:
    """Console script oteny-talent-lint — lint positional dirs."""
    argv = list(sys.argv[1:] if argv is None else argv)
    return main(["lint", *argv])


if __name__ == "__main__":
    raise SystemExit(main())
