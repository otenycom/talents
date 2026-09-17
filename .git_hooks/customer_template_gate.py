#!/usr/bin/env python3
"""One customer is never the template (D389).

Barney, the Cuneus posted-workers filer on meldloket.postedworkers.nl, is one
customer. He may appear in a shared file as a named worked example or as
history, in a comment or a docstring. He may not appear as a default, a
fixture for a generic test, a string a tenant reads, or a recipe. Measured on
2026-09-17, every plugin fix made for him had landed in a shared file under his
name, and the next author inherited it as the default.

The customer's workflow engine is the second family (D391): the platform
speaks to the business's Odoo only through Oteny's bridge module ``oteny.bot``,
so an engine's model name or work verb in platform code is the same failure.

This gate fails a commit or a push when one of the words below appears in
CODE — an identifier, a string literal, a default value, an f-string — under
the shared trees. Comments and docstrings are exempt, because provenance is
allowed: a comment that names a plan file is history, not a recipe. A test
file whose name carries ``barney`` is exempt too, because that test exists to
prove his own path. A line that ends in ``# customer-template: allow`` is
exempt, for the one honest case: a genericity guard that lists the words in
order to assert their absence. Every run prints a census of live hatches.

Usage:
    customer_template_gate.py            whole tree (the CI verdict, the pre-push twin)
    customer_template_gate.py FILE...    the staged files (the commit hook)
    customer_template_gate.py --list-rules
"""
from __future__ import annotations

import ast
import io
import os
import re
import subprocess
import sys
import tokenize
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WORDS = (
    # the customer and the site
    "meldloket", "postedworkers", "mfnl", "p652", "barney", "cuneus",
    # the customer's workflow engine and its work verbs (the platform speaks only
    # to the bridge `oteny.bot`, whose verbs are work_consume/work_probe/work_release)
    "riverflow", "rivercreds", "bot_claim", "bot_run_claim", "bot_token_check",
    "bot_work_queue",
)
# An engine verb is matched as an identifier (``bot_claim``, ``bot_claim_token``), never
# inside another word (``crm_bot_claim`` is the CRM bot's claim, not the engine's).
WORD_RE = re.compile("|".join(w if not w.startswith("bot_") else r"(?<![A-Za-z_])" + w for w in WORDS),
                     re.IGNORECASE)
ALLOW = "customer-template: allow"

# The shared trees an author reads: the standard, the demo bundles, the runner, the tests.
SCOPES = ("skills", "packages", "tests", "scripts")
EXCLUDED_PREFIXES = ()
TEXT_SUFFIXES = {".yaml", ".yml", ".json", ".toml", ".sh", ".txt", ".xml", ".js", ".html"}


def _tracked(paths: list[str] | None) -> list[Path]:
    if paths:
        return [REPO / p for p in paths]
    out = subprocess.run(["git", "-C", str(REPO), "ls-files", "--", *SCOPES],
                         capture_output=True, text=True, check=False).stdout.split("\n")
    return [REPO / p for p in out if p]


def in_scope(rel: str) -> bool:
    rel = rel.replace(os.sep, "/")
    if not any(rel == s or rel.startswith(s + "/") for s in SCOPES):
        return False
    if any(rel.startswith(p) for p in EXCLUDED_PREFIXES):
        return False
    name = Path(rel).name.lower()
    if rel.startswith("tests/") and "barney" in name:
        return False
    return True


def _docstring_lines(src: str) -> set[int]:
    """Every line of every docstring, so a string that documents is exempt."""
    lines: set[int] = set()
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return lines
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", None) or []
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                for ln in range(body[0].lineno, body[0].end_lineno + 1):
                    lines.add(ln)
    return lines


def findings_python(src: str, rel: str) -> list[tuple[int, str]]:
    doc = _docstring_lines(src)
    src_lines = src.split("\n")
    out: list[tuple[int, str]] = []
    seen: set[int] = set()
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(src).readline))
    except (tokenize.TokenError, SyntaxError):
        return out
    for tok in toks:
        if tok.type in (tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT,
                        tokenize.DEDENT, tokenize.ENCODING):
            continue
        kinds = {tokenize.NAME, tokenize.STRING}
        fstring_middle = getattr(tokenize, "FSTRING_MIDDLE", None)
        if fstring_middle is not None:
            kinds.add(fstring_middle)
        if tok.type not in kinds:
            continue
        ln = tok.start[0]
        if ln in seen or ln in doc:
            continue
        if not WORD_RE.search(tok.string):
            continue
        line = src_lines[ln - 1] if ln - 1 < len(src_lines) else ""
        if ALLOW in line:
            continue
        seen.add(ln)
        out.append((ln, line.strip()[:160]))
    return out


def findings_text(src: str, rel: str) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for i, line in enumerate(src.split("\n"), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("<!--"):
            continue
        if ALLOW in line or not WORD_RE.search(line):
            continue
        out.append((i, stripped[:160]))
    return out


def scan(paths: list[str] | None) -> tuple[dict[str, list[tuple[int, str]]], int]:
    findings: dict[str, list[tuple[int, str]]] = {}
    hatches = 0
    for path in _tracked(paths):
        rel = str(path.relative_to(REPO)) if path.is_absolute() else str(path)
        if not in_scope(rel) or not path.is_file():
            continue
        try:
            src = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        hatches += src.count(ALLOW)
        if path.suffix == ".py":
            hits = findings_python(src, rel)
        elif path.suffix in TEXT_SUFFIXES or path.suffix == "":
            hits = findings_text(src, rel)
        else:
            continue
        if hits:
            findings[rel] = hits
    return findings, hatches


def main(argv: list[str]) -> int:
    if "--list-rules" in argv:
        print(__doc__)
        return 0
    paths = [a for a in argv if not a.startswith("--")]
    findings, hatches = scan(paths or None)
    total = sum(len(v) for v in findings.values())
    if findings:
        print("One customer is never the template (D389): a customer's name, form or field "
              "sits in shared code.")
        for rel, hits in sorted(findings.items()):
            print(f"{rel} — {len(hits)} line(s)")
            for ln, line in hits[:12]:
                print(f"  {rel}:{ln}: {line}")
            if len(hits) > 12:
                print(f"  … {len(hits) - 12} more")
        print("Fix: a named worked example or history belongs in a comment or a docstring; "
              "a default, a generic fixture, a tenant-facing string or a recipe is rewritten "
              "neutral. A genericity guard that lists the words to assert their absence "
              f"ends its line with `# {ALLOW}`.")
    print(f"Customer-template census: {len(findings)} file(s), {total} line(s), "
          f"{hatches} live allow hatch(es).")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
