#!/usr/bin/env python3
"""Count the words, lines and characters of the text on stdin (stdlib only).

Started by the model through `talent_run` with the text as `stdin`. Prints one
JSON object so the bot can read the numbers instead of guessing them, and
records the run in the demo's ledger.
"""
from __future__ import annotations

import json
import sys

import _ledger


def main() -> int:
    text = sys.stdin.read()
    words = text.split()
    out = {
        "words": len(words),
        "lines": len(text.splitlines()),
        "characters": len(text),
        "longest_word": max(words, key=len) if words else "",
    }
    print(json.dumps(out, ensure_ascii=False))
    _ledger.record("scripts/word_count.py", [], 0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
