"""oteny — account-key author CLI."""
from __future__ import annotations

import argparse
import json
import os
import sys


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
                           limit=args.limit))
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
    """Ask the platform to re-deliver external Talents for --ref (account-scoped note).

    Full deliver-external-talents still drains on the control plane; this records the
    author intent via a tenant write / source bump when available, else documents the gap.
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

    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args) or 0)


def lint_main(argv: list[str] | None = None) -> int:
    """Console script oteny-talent-lint — lint positional dirs."""
    argv = list(sys.argv[1:] if argv is None else argv)
    return main(["lint", *argv])


if __name__ == "__main__":
    raise SystemExit(main())
