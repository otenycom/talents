#!/usr/bin/env python3
"""live_tape — free live price puller (Yahoo Finance), the keep-it tool for OtenyStockTalent.

No API key. Run BEFORE any sizing/allocation/comparison brief (Operating Rule 5).

Usage:
    live_tape.py NVDA TSM 005930.KS
    live_tape.py --json NVDA
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request

URL = "https://query1.finance.yahoo.com/v8/finance/chart/{t}?interval=1d&range=1y"
UA = "Mozilla/5.0"


def quote(ticker: str, timeout: int = 15) -> dict:
    req = urllib.request.Request(URL.format(t=ticker), headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.load(resp)
    meta = data["chart"]["result"][0]["meta"]
    px = meta.get("regularMarketPrice")
    lo, hi = meta.get("fiftyTwoWeekLow"), meta.get("fiftyTwoWeekHigh")
    # Some KRX tickers return 0.0 for the 52w meta — fall back to the close array.
    if not lo or not hi:
        try:
            closes = [c for c in data["chart"]["result"][0]["indicators"]["quote"][0]["close"] if c]
            lo, hi = (lo or min(closes)), (hi or max(closes))
        except Exception:
            pass
    return {"symbol": meta.get("symbol", ticker), "px": px, "ccy": meta.get("currency"),
            "lo52": lo, "hi52": hi, "exch": meta.get("exchangeName")}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Free live price puller (Yahoo Finance)")
    ap.add_argument("tickers", nargs="+")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    out, rc = [], 0
    for t in args.tickers:
        try:
            out.append(quote(t))
        except Exception as e:
            out.append({"symbol": t, "error": str(e)})
            rc = 1
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        for q in out:
            if "error" in q:
                print(f"=== {q['symbol']} ===  ERR {q['error']}")
            else:
                print(f"{q['symbol']}  px={q['px']} {q['ccy']}  "
                      f"52w={q['lo52']}-{q['hi52']}  exch={q['exch']}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
