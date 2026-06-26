#!/usr/bin/env python3
"""quarantine - the deterministic backbone of skill-translator (I0).

Translation is an LLM task, but *correctness* is not: SQL, column names, code,
study URLs, technical jargon, and numeric targets must survive a translation
**byte-identical** (the Oteny Talent localization contract, D33).
This module is the deterministic guard around the LLM:

    masked, tokens = extract(text)        # quarantined spans -> placeholders
    translated_masked = <LLM translates masked prose, preserving placeholders>
    translated = restore(translated_masked, tokens)   # spans re-injected verbatim

Because quarantined content is re-injected from ``tokens`` rather than rewritten,
it is *guaranteed* identical. ``check_placeholders`` catches the only way the LLM
can break it: dropping or duplicating a placeholder.

Placeholders are bracketed by private-use characters (U+E000 / U+E001) and the
index inside is written with private-use "digits" (U+E010..U+E019) rather than
ASCII, so the later numeric/jargon patterns can never re-match the digits *inside*
an already-placed placeholder. Private-use codepoints never occur in source prose,
so ``restore`` is an unambiguous pass.
"""
from __future__ import annotations

import re

PH_OPEN = "\uE000"
PH_CLOSE = "\uE001"
_PH_DIGIT0 = 0xE010
_PH_RE = re.compile(PH_OPEN + "([\uE010-\uE019]+)" + PH_CLOSE)


def _encode(i: int) -> str:
    return PH_OPEN + "".join(chr(_PH_DIGIT0 + int(c)) for c in str(i)) + PH_CLOSE


def _decode(body: str) -> int:
    return int("".join(str(ord(c) - _PH_DIGIT0) for c in body))


# Jargon that must stay in English even in a translated bundle. Extend per domain.
DEFAULT_JARGON = [
    "mTOR", "leucine", "TRE", "macros", "BMR", "TDEE", "NAFLD", "VAT", "WHtR",
    "HDL", "LDL", "ALAT", "ASAT", "eGFR", "HbA1c", "Mifflin-St Jeor",
    "HBM3E", "HBM4", "HBM", "13F", "13F-HR", "IPO", "M&A", "ETF", "ADR", "GDR",
    "Polymarket", "SEC EDGAR", "EDGAR", "Apify", "Yahoo Finance",
]


# Ordered: earlier patterns mask first; their inner content is then hidden from
# later patterns (e.g. a URL inside a fenced block is masked by the block).
def _build_patterns(jargon):
    pats = [
        ("fence", re.compile(r"```.*?```", re.S)),                 # fenced code blocks
        ("dnt", re.compile(r"\[\[DNT\]\].*?\[\[/DNT\]\]", re.S)),  # explicit keep
        ("inline", re.compile(r"`[^`\n]+`")),                      # inline code
        ("url", re.compile(r"https?://[^\s)>\]]+")),               # study URLs / endpoints
        # numeric targets: numbers, ranges (1.6-2.2, 150-300), with a trailing
        # unit/percent/slash run (g/kg, kg/wk, min/wk, %, kg, cm, mmol/L, x).
        ("num", re.compile(
            r"\d[\d.,]*\s*[–-]\s*\d[\d.,]*(?:\s*[%×x]|\s*[A-Za-z/µμ°]+(?:/[A-Za-z]+)?)?"
            r"|\d[\d.,]*\s*(?:[%×x]|[A-Za-z/µμ°]+(?:/[A-Za-z]+)?)"
            r"|\d[\d.,]*")),
    ]
    if jargon:
        jpat = r"\b(?:" + "|".join(
            re.escape(j) for j in sorted(jargon, key=len, reverse=True)) + r")\b"
        pats.append(("jargon", re.compile(jpat)))
    return pats


def extract(text: str, jargon=None):
    """Return (masked_text, tokens) where tokens maps placeholder-id -> literal."""
    jargon = DEFAULT_JARGON if jargon is None else jargon
    tokens: dict[int, str] = {}
    counter = [0]
    masked = text

    def repl(m):
        i = counter[0]
        counter[0] += 1
        tokens[i] = m.group(0)
        return _encode(i)

    for _name, pattern in _build_patterns(jargon):
        masked = pattern.sub(repl, masked)
    return masked, tokens


def restore(masked: str, tokens: dict) -> str:
    """Re-inject quarantined literals. Repeats until stable (defensive)."""
    def repl(m):
        return tokens[_decode(m.group(1))]
    prev, cur = None, masked
    while prev != cur:
        prev, cur = cur, _PH_RE.sub(repl, cur)
    return cur


def check_placeholders(translated_masked: str, tokens: dict):
    """Verify the LLM preserved every placeholder exactly once.

    Returns dict {ok, missing, extra, duplicated}.
    """
    from collections import Counter
    found = [_decode(b) for b in _PH_RE.findall(translated_masked)]
    expected = set(tokens)
    seen = set(found)
    counts = Counter(found)
    return {
        "ok": seen == expected and all(c == 1 for c in counts.values()),
        "missing": sorted(expected - seen),
        "extra": sorted(seen - expected),
        "duplicated": sorted(k for k, c in counts.items() if c > 1),
    }


def quarantined_spans(text: str, jargon=None) -> list[str]:
    """The multiset (sorted) of spans that WOULD be quarantined in ``text``."""
    _masked, tokens = extract(text, jargon=jargon)
    return sorted(tokens.values())


def verify(original: str, translated: str, jargon=None):
    """Assert the translated text preserved all quarantined spans byte-identical.

    Returns dict {ok, only_in_original, only_in_translated}.
    """
    from collections import Counter
    ca = Counter(quarantined_spans(original, jargon=jargon))
    cb = Counter(quarantined_spans(translated, jargon=jargon))
    return {
        "ok": ca == cb,
        "only_in_original": sorted((ca - cb).elements()),
        "only_in_translated": sorted((cb - ca).elements()),
    }


def roundtrip(text: str, jargon=None) -> bool:
    """Self-test: mask then restore (no translation) must be the identity."""
    masked, tokens = extract(text, jargon=jargon)
    return restore(masked, tokens) == text
