# Multi-Name Comparison Brief Format

When the user asks to **compare 2–4 names in the same theme** and pick the best
opportunity ("compare SK Hynix, Micron, Samsung", "VST vs CEG vs TLN") produce the
deeper variant below — NOT the single-name compact brief.

Triggered by: "compare X, Y, Z", "which is the best opportunity", "rank them",
"stack them up", "side-by-side".

## Structure (in order)

### 1. Per-name live snapshot
**Pull live prices first** (Operating Rule 5; `live_tape.py` / recipes §7). For each:
```
**Name (TICKER)** — px / 1y / YTD / 1m / 52w range / Fwd P/E (year)E
```
Non-US names: show BOTH local + USD ADR/GDR price.

### 2. Core thesis paragraph
One paragraph per name capturing the *current narrative state* — what changed in the
last ~90 days that makes it interesting *right now*, not the generic description.

### 3. The comparison table
The heart of the output (Telegram rewrites tables to bullet groups — fine):

| Metric | Name A | Name B | Name C |
|---|---|---|---|
| Price (today) | | | |
| 52w range | | | |
| 1y / 1m return | | | |
| Fwd P/E (next-yr-E) | | | |
| LTM P/E | | | |
| Market share / position | | | |
| Geography / FX risk | | | |
| Catalyst momentum | | | |
| Recent narrative change | | | |

Add domain-specific rows as relevant; drop any row where all names rank the same.

### 4. Ranked recommendation
```
🥇 1st: **Name** — one-paragraph why
🥈 2nd: **Name** — why
🥉 3rd: **Name** — why
```
The ranking MUST be defensible from the table. If two are tied, say so + the tiebreaker.

### 5. Recommended allocation
If allocating $100 fresh today: `- $X Name A (reason) …`. This is the actionable
output the user is here for.

### 6. Buy levels for the top pick
Don't-chase price · first scale-in · half-size · full-position · stop-out trigger.

### 7. Risks (what kills the trade)
Numbered, 3–7 items, specific to the cohort.

### 8. Portfolio Watch (compact)
**Positive:** · **Watch closely:** · **Risk:**

### 9. Disclaimer
Standard not-financial-advice line (`safety-boundaries.md`). Flag any contested number.

## What makes a comparison land (illustrative)

- Live data pulled for all names **on the same minute** (multiples move with price).
- Where a podcast host gave explicit sizing, quote it as one corroborating data point
  — but the recommendation is your own, defensible from the live table.
- Concrete buy levels for the #1 pick, not "wait for a pullback".

## Pitfalls

1. **Don't pad the table with junk rows** — every row a real differentiator.
2. **Don't rank by momentum alone** — the most-up name is usually the worst entry;
   forward P/E + catalyst freshness + chart position is the right composite.
3. **Cite the source for any contested number** (market-share estimates vary by
   provider — say which and the month).
4. **If the user holds a position, reference it** — "you already hold X" changes the
   allocation.
5. **Currency consistency** — show forward P/E (currency-neutral) prominently and
   USD-equivalent prices where possible.
