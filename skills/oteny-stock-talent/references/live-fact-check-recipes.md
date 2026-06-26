# Live Fact-Check Recipes

Verify corporate-action, holdings, and price claims **before** stating them in a brief.
Every recipe runs through a **declared script** —
`python3 ~/.hermes/skills/talents/oteny-stock-talent/scripts/fact_check.py <cmd>` (or
`live_tape.py` for prices) — so it never trips the gateway's approval gate (improvised
`python3 -c`/heredocs do). All endpoints are unauthenticated, free, and reachable from
a cloud host; no API key.

Triggered by any claim about IPO status, recent M&A, fund holdings, or "X just
launched/filed Y." The model's training cutoff is months behind real time; do NOT trust
priors on these.

> Shorthand below: `FC=~/.hermes/skills/talents/oteny-stock-talent/scripts/fact_check.py`.

## 1. Latest price + 52w range

Use the dedicated helper (free Yahoo Finance):

```bash
python3 ~/.hermes/skills/talents/oteny-stock-talent/scripts/live_tape.py NVDA
```

Non-US tickers: append `.L`, `.AS`, `.PA`, `.HK`, `.KS`, `.TW`, etc. — Yahoo returns
the currency natively. For crypto use `BTC-USD`/`ETH-USD`; indices `^GSPC`/`^IXIC`/
`^DJI`/`^VIX`; FX `EURUSD=X`; commodities `CL=F`/`GC=F`.

## 2. Ticker search (does it exist? what exchange?)

Use BEFORE asserting "X just IPO'd as ticker Y" — confirms the listing trades.

```bash
python3 ~/.hermes/skills/talents/oteny-stock-talent/scripts/fact_check.py search "Pershing Square"
```

## 3. Latest 13F holdings via SEC EDGAR

SEC asks for a User-Agent with a real contact email — the script takes `--contact`
(substitute the tenant's email; never hardcode a person). First list the filing
indexes for the manager's CIK, then parse the `infotable.xml` from one of them:

```bash
python3 ~/.hermes/skills/talents/oteny-stock-talent/scripts/fact_check.py edgar-13f 1336528 --contact <tenant-email>
```
```bash
python3 ~/.hermes/skills/talents/oteny-stock-talent/scripts/fact_check.py edgar-holdings "https://www.sec.gov/Archives/edgar/data/<CIK>/<accession>/infotable.xml" --contact <tenant-email>
```

**Always cite the period of report and filing date.** A 13F filed Feb reflects
positions as of Dec 31 of the prior year — not "current." (Don't have the CIK? Run
`search` on the manager name, or open EDGAR full-text search in a browser.)

## 4. Company press / corporate actions (live IR page)

Fetch + strip an IR page to readable text near a heading (faster than browser
automation, never rate-limits):

```bash
python3 ~/.hermes/skills/talents/oteny-stock-talent/scripts/fact_check.py extract "<ir-page-url>" --anchor "latest news"
```

## 5. Web-search fallback (Bing, no API key)

DDG HTML scraping is broken (empty result pages); the script uses Bing with en-US
locale flags so you don't get localized garbage. Snippets alone are often enough for a
date + headline confirmation.

```bash
python3 ~/.hermes/skills/talents/oteny-stock-talent/scripts/fact_check.py websearch "Samsung HBM4 Nvidia qualification"
```

## 6. Multi-exchange tickers for non-US names

| Company | Primary (local) | USD proxy |
|---|---|---|
| Samsung Elec. | `005930.KS` (KRW) | `SMSN.IL` (LSE GDR, USD) |
| SK Hynix | `000660.KS` (KRW) | `HXSCL` OTC (thin) |
| TSMC | `2330.TW` (TWD) | `TSM` (NYSE ADR, USD) |
| ASML | `ASML.AS` (EUR) | `ASML` (NASDAQ ADR, USD) |
| Tencent | `0700.HK` (HKD) | `TCEHY` OTC ADR |

**Pattern:** for a non-US name pull BOTH the local listing AND the USD ADR/GDR (the
user's broker may only have one) with `live_tape.py`. For some KRX tickers
`fiftyTwoWeekLow` returns `0.0` — treat the latest close as truth.

## When NOT to bother

- Long-running facts that don't change (a company is a US LNG exporter; NVDA makes
  GPUs) — training is fine.
- Direction/sentiment ("hyperscalers are spending more on capex") — fine; exact figures
  ("AMZN spent exactly $X") — verify.
- Pure framework analysis ("is the SaaS de-rating thesis sound") — priors are the
  value-add.

The rule: **time-sensitive corporate facts get verified; framework analysis doesn't.**

## Pitfalls

1. **SEC requires a User-Agent with contact info** — pass `--contact <tenant-email>`,
   never a baked person.
2. **Yahoo's chart endpoint occasionally returns empty for thin tickers** — fall back
   to the IR site (`extract`).
3. **13F is delayed and incomplete** — filed within 45 days of quarter end, US long
   equity ≥ $200K only; no shorts/options/non-US. State the period.
4. **Closed-end fund vs operating-company vehicles can share a manager** — don't
   conflate different wrappers (different tax, different discount-to-NAV).
