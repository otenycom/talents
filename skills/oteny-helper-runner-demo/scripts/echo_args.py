#!/usr/bin/env python3
"""Echo the arguments the model passed, one per line, with their position (stdlib only).

Started by the model through `talent_run` with `argv`. It proves that arguments
reach a helper unchanged, in order, and that a helper's own exit code is what
the bot sees: `--fail` exits 3 on purpose. Every run lands in the demo's ledger.
"""
from __future__ import annotations

import sys

import _ledger


def main(argv: list[str]) -> int:
    code = 0
    if "--fail" in argv:
        print("failing on request", file=sys.stderr)
        code = 3
    else:
        for i, arg in enumerate(argv, 1):
            print(f"{i}: {arg}")
        if not argv:
            print("(no arguments)")
    _ledger.record("scripts/echo_args.py", argv, code)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
