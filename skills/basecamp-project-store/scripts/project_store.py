#!/usr/bin/env python3
"""project_store — read a Basecamp board and report what changed, deterministically.

The skill's checklist calls this instead of stringing raw commands together, so the parts that
must not vary — which list is the bot's own, what "changed since last time" means, and what
survives the board's editor — are decided in code rather than by the model.

    project_store.py brief                     # the messages that hold the rules, as text
    project_store.py queue                     # the bot's OWN list: open todos + their notes
    project_store.py open-facts                # the read-only lists, for the pre-publish check
    project_store.py digest                    # what changed since last run, or NO-CHANGES
    project_store.py body --file <path>        # fence raw HTML so the body stays markdown

Reading the board's *shape* — which projects exist, which lists and messages are on one — is
the command-line tool's own job (`projects list`, `todolists list`, `messages list`), so it is
not wrapped here. What IS wrapped is everything where a wrong answer is silent: which list is
this bot's own, what "changed since last time" means, and what survives the board's editor.

Standard library only. Account and project come from the profile; --account / --project
override them. Exit code is 0 whenever the command ran; a real failure prints one ERROR line.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import data_dir, id_list, read_profile, run_cli  # noqa: E402

_STATE = "digest_state.json"


# --------------------------------------------------------------------------- #
# Board access                                                                  #
# --------------------------------------------------------------------------- #
def _scope(args) -> tuple[str, str]:
    profile = read_profile()
    account = (getattr(args, "account", None) or profile.get("account_id") or "").strip()
    project = (getattr(args, "project", None) or profile.get("project_id") or "").strip()
    return account, project


def _call(args_list: list[str], *, timeout: int = 60) -> tuple[bool, object, str]:
    """Run a read command and unwrap the envelope -> (ok, data, error)."""
    try:
        proc = run_cli([*args_list, "--json"], timeout=timeout)
    except FileNotFoundError:
        return False, None, "the Basecamp command-line tool is not installed"
    except subprocess.TimeoutExpired:
        return False, None, "the board did not answer in time"
    except (subprocess.SubprocessError, OSError) as exc:
        return False, None, f"could not run the command-line tool ({exc})"
    try:
        payload = json.loads(proc.stdout or "{}")
    except ValueError:
        return False, None, (proc.stderr or proc.stdout or "unreadable answer").strip()[:200]
    if not payload.get("ok"):
        return False, None, str(payload.get("error") or "the board refused the request")[:200]
    return True, payload.get("data"), ""


def _todos(account: str, project: str, list_id: str, *, completed: bool = False) -> list[dict]:
    """Todos on ONE list. --list is the only thing that scopes: a list id passed as a bare
    argument is accepted and ignored, and you silently get the whole project instead.

    `--status completed` really does filter, but only from CLI 0.8 on — 0.7.x accepted it and
    returned the OPEN todos, so a digest run there would have called every open todo 'done'.
    install_cli.sh pins the version this bundle was verified against; do not unpin it."""
    argv = ["todos", "list", "--list", list_id, "--account", account, "--in", project]
    if completed:
        argv += ["--status", "completed"]
    ok, data, err = _call(argv)
    if not ok:
        raise RuntimeError(err)
    return [t for t in (data or []) if isinstance(t, dict)]


def _messages(account: str, project: str) -> list[dict]:
    ok, data, err = _call(["messages", "list", "--account", account, "--in", project])
    if not ok:
        raise RuntimeError(err)
    return [m for m in (data or []) if isinstance(m, dict)]


# --------------------------------------------------------------------------- #
# The board's editor speaks HTML; chat does not                                 #
# --------------------------------------------------------------------------- #
class _Text(HTMLParser):
    """Board markup -> readable plain text: paragraphs break, list items become bullets."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in ("br", "p", "div", "h1", "h2", "h3", "h4", "pre"):
            self.parts.append("\n")
        elif tag == "li":
            self.parts.append("\n- ")

    def handle_endtag(self, tag):
        if tag in ("p", "div", "h1", "h2", "h3", "h4", "ul", "ol", "pre"):
            self.parts.append("\n")

    def handle_data(self, data):
        self.parts.append(data)


def to_text(markup: str | None) -> str:
    if not markup:
        return ""
    parser = _Text()
    parser.feed(markup)
    text = "".join(parser.parts)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# --------------------------------------------------------------------------- #
# Making a body survive the editor                                              #
# --------------------------------------------------------------------------- #
_HTML_TAG = re.compile(r"<[a-zA-Z/][^>\n]*>")


def fence_raw_html(lines: list[str]) -> tuple[list[str], int]:
    """Put any bare HTML line inside a fenced block.

    The board converts a markdown body to rich text — headings, bullets and TABLES all render
    — but only while the body is markdown. One raw tag anywhere flips the whole body into
    pass-through HTML, and then every other construct in it stays literal: the table posts as
    a paragraph of bars, the bullets as hyphens, the heading as a hash. Meanwhile the tag
    itself renders as markup, so it is invisible to whoever reads the board.

    Fencing fixes both halves at once: the rest of the body renders as markdown, and the tag
    survives inside <pre><code> as readable, copy-pasteable escaped text. Lines already inside
    a fence are left alone."""
    out: list[str] = []
    fenced = 0
    in_fence = False
    for line in lines:
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            out.append(line)
            continue
        if not in_fence and _HTML_TAG.search(line):
            out.extend(["```", line, "```"])
            fenced += 1
            continue
        out.append(line)
    return out, fenced


def prepare_body(text: str) -> tuple[str, int]:
    lines, fenced = fence_raw_html(text.split("\n"))
    return "\n".join(lines), fenced


# --------------------------------------------------------------------------- #
# Change tracking for the recurring summary                                     #
# --------------------------------------------------------------------------- #
def snapshot(todos: list[dict], messages: list[dict]) -> dict:
    return {
        "todos": {
            str(t.get("id")): {
                "title": t.get("title") or t.get("content") or "",
                "completed": bool(t.get("completed")),
                "updated_at": t.get("updated_at") or "",
            }
            for t in todos if t.get("id")
        },
        "messages": {
            str(m.get("id")): {
                "subject": m.get("subject") or "",
                "updated_at": m.get("updated_at") or "",
            }
            for m in messages if m.get("id")
        },
    }


def diff(previous: dict, current: dict) -> dict:
    """What a person would call news. An empty result means the run posts nothing at all."""
    old_t = (previous or {}).get("todos") or {}
    new_t = current.get("todos") or {}
    old_m = (previous or {}).get("messages") or {}
    new_m = current.get("messages") or {}

    added, done, reopened, touched = [], [], [], []
    for tid, cur in new_t.items():
        was = old_t.get(tid)
        if was is None:
            added.append(cur["title"])
            continue
        if cur["completed"] and not was["completed"]:
            done.append(cur["title"])
        elif was["completed"] and not cur["completed"]:
            reopened.append(cur["title"])
        elif cur["updated_at"] and cur["updated_at"] != was.get("updated_at"):
            touched.append(cur["title"])

    messages = [
        cur["subject"] for mid, cur in new_m.items()
        if mid not in old_m or cur["updated_at"] != (old_m[mid] or {}).get("updated_at")
    ]
    still_open = sum(1 for cur in new_t.values() if not cur["completed"])
    return {"added": added, "completed": done, "reopened": reopened,
            "updated": touched, "messages": messages, "still_open": still_open}


def _state_path() -> Path:
    return data_dir() / _STATE


def load_state() -> dict:
    try:
        return json.loads(_state_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(state: dict) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


# --------------------------------------------------------------------------- #
# Commands                                                                      #
# --------------------------------------------------------------------------- #
def cmd_brief(args) -> int:
    account, project = _scope(args)
    profile = read_profile()
    ids = id_list(args.message or ",".join(id_list(profile.get("brief_message_ids"))))
    if not (account and project):
        print("ERROR no board — ask the owner for the board link")
        return 0
    if not ids:
        print("NO-BRIEF no brief messages are recorded for this board")
        return 0
    for mid in ids:
        ok, data, err = _call(["messages", "show", mid, "--account", account, "--in", project])
        if not ok:
            print(f"ERROR message {mid}: {err}")
            continue
        record = data if isinstance(data, dict) else {}
        print(f"--- {record.get('subject') or mid} ({mid}) ---")
        print(to_text(record.get("content")))
        print()
    return 0


def _print_todos(title: str, todos: list[dict], *, notes: bool) -> None:
    print(f"{title} ({len(todos)})")
    for todo in sorted(todos, key=lambda t: t.get("position") or 0):
        mark = "x" if todo.get("completed") else " "
        print(f"  [{mark}] {todo.get('id')}\t{todo.get('title') or todo.get('content')}")
        if notes:
            body = to_text(todo.get("description"))
            for line in body.splitlines():
                print(f"        {line}")


def cmd_queue(args) -> int:
    account, project = _scope(args)
    profile = read_profile()
    work = (profile.get("work_todolist_id") or "").strip()
    if not (account and project and work):
        print("ERROR no work list — the board is not connected yet")
        return 0
    try:
        todos = _todos(account, project, work)
    except RuntimeError as exc:
        print(f"ERROR {exc}")
        return 0
    _print_todos("OPEN", todos, notes=not args.brief)
    if not todos:
        print("QUEUE-EMPTY nothing open on this bot's list")
    return 0


def cmd_open_facts(args) -> int:
    account, project = _scope(args)
    profile = read_profile()
    lists = id_list(profile.get("read_todolist_ids"))
    if not (account and project):
        print("ERROR no board — the board is not connected yet")
        return 0
    if not lists:
        print("NO-READ-LISTS nothing to check before publishing")
        return 0
    total = 0
    for list_id in lists:
        try:
            todos = _todos(account, project, list_id)
        except RuntimeError as exc:
            print(f"ERROR list {list_id}: {exc}")
            continue
        total += len(todos)
        _print_todos(f"STILL-OPEN {list_id}", todos, notes=not args.brief)
    print(f"OPEN-FACTS {total}")
    if total:
        print("HOLD anything still open stays a visible placeholder, never a guess")
    return 0


def cmd_digest(args) -> int:
    account, project = _scope(args)
    profile = read_profile()
    work = (profile.get("work_todolist_id") or "").strip()
    if not (account and project and work):
        print("ERROR no work list — the board is not connected yet")
        return 0
    try:
        todos = _todos(account, project, work) + _todos(account, project, work, completed=True)
        messages = _messages(account, project)
    except RuntimeError as exc:
        print(f"ERROR {exc}")
        return 0

    current = snapshot(todos, messages)
    previous = load_state()
    if not previous:
        # Nothing to compare against. Record today and stay quiet: the first summary must not
        # be a dump of the whole board.
        if not args.dry_run:
            save_state(current)
        print("NO-CHANGES first run — the board state is now recorded")
        return 0

    changes = diff(previous, current)
    if not args.dry_run:
        save_state(current)
    if not any(changes[k] for k in ("added", "completed", "reopened", "updated", "messages")):
        print("NO-CHANGES nothing moved — send no message")
        return 0

    print(f"CHANGES since the last summary (still open: {changes['still_open']})")
    for label, key in (("Done", "completed"), ("New on the list", "added"),
                       ("Reopened", "reopened"), ("Notes or comments changed", "updated"),
                       ("Messages changed", "messages")):
        items = changes[key]
        if items:
            print(f"{label}: {len(items)}")
            for item in items:
                print(f"  • {item}")
    return 0


def cmd_body(args) -> int:
    path = Path(args.file).expanduser()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"ERROR cannot read {path} ({exc})")
        return 0
    prepared, fenced = prepare_body(text)
    if args.stdout:
        print(prepared)
    else:
        path.write_text(prepared, encoding="utf-8")
    print(f"BODY-READY html_fenced={fenced} file={path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Read a Basecamp board")
    ap.add_argument("--account", help="override the account from the profile")
    ap.add_argument("--project", help="override the project from the profile")
    sub = ap.add_subparsers(dest="cmd", required=True)

    brief = sub.add_parser("brief")
    brief.add_argument("--message", help="comma-separated message ids (default: the profile's)")
    queue = sub.add_parser("queue")
    queue.add_argument("--brief", action="store_true", help="titles only, no notes")
    facts = sub.add_parser("open-facts")
    facts.add_argument("--brief", action="store_true", help="titles only, no notes")
    digest = sub.add_parser("digest")
    digest.add_argument("--dry-run", action="store_true",
                        help="report without recording the new state")
    body = sub.add_parser("body")
    body.add_argument("--file", required=True, help="the markdown body to prepare, rewritten in place")
    body.add_argument("--stdout", action="store_true", help="print instead of rewriting the file")

    args = ap.parse_args(argv)
    return {
        "brief": cmd_brief, "queue": cmd_queue, "open-facts": cmd_open_facts,
        "digest": cmd_digest, "body": cmd_body,
    }[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
