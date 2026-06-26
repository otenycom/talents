#!/usr/bin/env python3
"""translate_bundle — orchestrate a quarantine-safe, LLM-driven translation.

The LLM does the prose rewrite; this CLI enforces that SQL/code/URLs/numbers/
jargon survive byte-identical (see ``quarantine.py``). Workflow the skill follows:

    1.  mask     a file   -> emits masked text + a token sidecar (.qtokens.json)
    2.  <LLM translates the masked text into the target language, keeping every
        ⟦placeholder⟧ token exactly where it is>
    3.  unmask   the translated masked text + sidecar -> the final translated file
        (refuses to write if any placeholder was dropped/duplicated)
    4.  verify   original vs translated -> asserts protected spans are identical

Plus ``roundtrip`` for a no-LLM self-test of a file.

Usage:
    translate_bundle.py mask     SKILL.md              > SKILL.masked.md   # + SKILL.md.qtokens.json
    translate_bundle.py unmask   SKILL.translated.md   SKILL.md.qtokens.json > SKILL.nl.md
    translate_bundle.py verify   SKILL.md SKILL.nl.md
    translate_bundle.py roundtrip SKILL.md
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import quarantine  # noqa: E402


def cmd_mask(args) -> int:
    text = Path(args.file).read_text()
    masked, tokens = quarantine.extract(text)
    sidecar = Path(args.sidecar) if args.sidecar else Path(args.file + ".qtokens.json")
    sidecar.write_text(json.dumps({str(k): v for k, v in tokens.items()},
                                  ensure_ascii=False, indent=2))
    sys.stdout.write(masked)
    print(f"\n[masked {len(tokens)} spans -> {sidecar}]", file=sys.stderr)
    return 0


def cmd_unmask(args) -> int:
    masked = Path(args.masked).read_text()
    tokens = {int(k): v for k, v in json.loads(Path(args.sidecar).read_text()).items()}
    chk = quarantine.check_placeholders(masked, tokens)
    if not chk["ok"]:
        print(f"❌ placeholder mismatch: {chk}", file=sys.stderr)
        return 2
    out = quarantine.restore(masked, tokens)
    if args.out:
        Path(args.out).write_text(out)
        print(f"[wrote {args.out}]", file=sys.stderr)
    else:
        sys.stdout.write(out)
    return 0


def cmd_verify(args) -> int:
    res = quarantine.verify(Path(args.original).read_text(), Path(args.translated).read_text())
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0 if res["ok"] else 1


def cmd_roundtrip(args) -> int:
    ok = quarantine.roundtrip(Path(args.file).read_text())
    print("OK" if ok else "FAIL")
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="quarantine-safe bundle translator")
    sub = ap.add_subparsers(dest="cmd", required=True)

    m = sub.add_parser("mask")
    m.add_argument("file")
    m.add_argument("--sidecar")
    m.set_defaults(fn=cmd_mask)

    u = sub.add_parser("unmask")
    u.add_argument("masked")
    u.add_argument("sidecar")
    u.add_argument("--out")
    u.set_defaults(fn=cmd_unmask)

    v = sub.add_parser("verify")
    v.add_argument("original")
    v.add_argument("translated")
    v.set_defaults(fn=cmd_verify)

    r = sub.add_parser("roundtrip")
    r.add_argument("file")
    r.set_defaults(fn=cmd_roundtrip)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
