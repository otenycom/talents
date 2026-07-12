---
name: permit-filing
description: "File a permit application on the demo portal"
version: 0.1.0
author: Oteny
license: MIT
metadata:
  hermes:
    tags: [permit, filing, demo, business-bot, portal]
---

# Permit filing — the demo portal, the business-bot way

## Overview

You file **permit applications** from your local records onto the permit portal at
**`$OTENY_PORTAL_BASE_URL`**, capture the **confirmation number** the portal shows
you, and record it back on the application row. This skill is a *worked example* of
the scoped business-bot filing pattern: everything here generalizes — the batch-fill
wizard, the shipped selector map, the write-ahead intent, the fail-closed rules —
and the portal is a small local app you (the author) can run and read.

Your system of record is the local database
`~/.hermes/data/oteny-permit-filer-demo/permits.db` (table `permit_applications`).
Read and write it with the `sqlite3` command in the terminal. *(In a real business
bot this is the client's own system reached over its API seam, and the terminal is
not mounted — see the pattern reference.)*

> **⛔ THE ONE RULE ABOVE ALL: the confirmation number is READ FROM THE PORTAL —
> you NEVER create it.** It only ever comes from the confirmation page the browser
> shows you after a successful *Submit application*. If you cannot reach the portal
> or never saw a confirmation number on the page, you have **not** filed: write
> nothing, mark nothing filed, set the row's `status` to `escalated`, tell the
> owner why, and stop. A fabricated "filed" is worse than no filing.
>
> **Fail closed on any browser trouble.** If a navigation or step errors, is
> blocked, or times out — stop retrying after the SECOND identical error, do not
> improvise another URL, do not write a confirmation, escalate as above.

## Filing checklist (run in order, every time)

> **⚡ Batch-fill rule — one `browser_fill_form` call per wizard page.** Fill every
> independent field on a page in ONE call using the selector map in
> [`references/form-selectors.md`](references/form-selectors.md), with the page's
> *Next* button as `submit_selector`: the tool reads every value back (its
> per-field `ok`/`actual` IS your verify) and clicks next only when every field
> verified. Steps run in order — on the site page, UNCHECK the "local
> municipalities only" filter *before* selecting a non-local municipality, in the
> same call. Fix and re-verify any `ok:false` field before moving on. The final
> *Submit application* is **never** a `submit_selector` — see step 4.

### Step 0 — pick the work

1. Read the next pending application:
   `sqlite3 ~/.hermes/data/oteny-permit-filer-demo/permits.db "SELECT * FROM permit_applications WHERE status='pending' ORDER BY id LIMIT 1;"`
   (or the specific id the owner named). No pending row → say so and stop.

### Step 1 — already filed? (never double-file)

1. If the row already has a `confirmation_no`:
   - a real `P-…` number → it is filed; report the number and **stop**.
   - a `PENDING-…` marker → a previous run may have reached the portal before
     dying. **Never re-file.** Set `status='escalated'`, tell the owner to verify
     on the portal, and stop.

### Step 2 — reachability gate

1. `browser_navigate` to `$OTENY_PORTAL_BASE_URL/portal`. If it errors, is
   blocked, or times out → the portal is unavailable: set `status='escalated'`,
   report it, **stop**. Do not continue, do not invent a number.
2. Before filling each page below, confirm the expected field labels (one
   snapshot). A redesigned page = selectors will miss → halt and escalate, never
   improvise selectors mid-run.

### Step 3 — drive the wizard from the row (one batch per page)

1. Click **“+ New application”** on the dashboard.
2. **Application details** — one `browser_fill_form` call (map §1):
   `applicant_name`, `company`, `permit_type` (a native select), `start_date`
   (dd-mm-yyyy, verbatim from the row), submit = the *Next* button.
3. **Work site** — one call (map §2), ordered: first **uncheck** the "local
   municipalities only" filter (a non-local municipality is unselectable until
   you do), then `municipality` (select), `street`, `house_number`, `postcode`,
   `city`, the `has_insurance` and `night_work` radios (value = `Yes`/`No`
   exactly as in the row), submit = *Next*.
4. **Review** — take a fresh snapshot; check every echoed value against the row.
   Any mismatch → go back and fix that field, or escalate. Then continue to
   step 4 below — the declaration + submit are handled there, never batched.

### Step 4 — write-ahead, then the explicit submit

1. Write the intent BEFORE submitting:
   `sqlite3 ~/.hermes/data/oteny-permit-filer-demo/permits.db "UPDATE permit_applications SET status='filing', confirmation_no='PENDING-' || strftime('%s','now') WHERE id=<id>;"`
   This is the crash fence: if you die between submit and proof, the next run's
   Step 1 sees the marker and never files a duplicate.
2. On the review page: tick the **declaration** checkbox (one `browser_fill_form`
   call, no submit_selector — map §3).
3. Take a **fresh full snapshot**, confirm the declaration is ticked and the
   values are right, then click **Submit application** explicitly
   (`browser_click` on its snapshot ref). If the confirmation page does not load
   or shows no number → the filing failed: fail-closed rule (escalate, keep the
   `PENDING-…` marker so the next run halts too).

### Step 5 — record the proof

1. Read the **Confirmation number: P-……** off the confirmation page (snapshot).
   A value you did not literally see on the page does not exist.
2. Finalize the row:
   `sqlite3 ~/.hermes/data/oteny-permit-filer-demo/permits.db "UPDATE permit_applications SET status='filed', confirmation_no='<the number>', filed_at=datetime('now') WHERE id=<id>;"`
3. Reply to the owner: *"Filed the <permit_type> permit for <applicant_name> —
   confirmation <number>."* Then stop.

## Common pitfalls

- **Never construct a number** — not from the row, not "a plausible P-…". Read it
  or escalate.
- **Never batch the KvK-style interludes of a real portal** (a search that
  populates fields) — this demo has none, your real portal will; those stay
  one-action-at-a-time.
- The `browser_console` JS escape hatch **cannot read form values** (safety
  policy) — verification is `browser_fill_form`'s readback plus snapshots.
- Tool unavailable? Fall back to per-field `browser_type`/`browser_click` with one
  snapshot verify per page — same checklist, slower.

## Related

- First-run setup (create the local db): [`references/first-run.md`](references/first-run.md)
- The selector map: [`references/form-selectors.md`](references/form-selectors.md)
- The generic pattern this instantiates: `business-bot-pattern.md` +
  `browser-authoring.md` + `tools-reference.md` (in the authoring standard).
