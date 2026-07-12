# Demo portal form selectors — the per-page `browser_fill_form` map

One `browser_fill_form` call per wizard page: `steps=[{selector, value}, …]` plus
the page's *Next* button as `submit_selector`. Text inputs and selects carry
`id == name` (so `#field_name` works); **radios carry a name only** — target one
option as `input[name=field][value=Yes]`; same for checkboxes without an id. Each
wizard page has exactly one `button[type=submit]`.

*How this file was made (do the same for your portal):* run the portal locally
(`python3 scripts/demo_portal.py --port 8099`), open it in your own browser, and
read the ids/names off the DOM in devtools. The bot cannot do this at runtime —
snapshots show accessibility refs and labels, never CSS ids — which is exactly why
the skill ships this map.

## §1 — Application details (`Next` = `button[type=submit]`)

| Field | Selector | Control |
| --- | --- | --- |
| Applicant name | `#applicant_name` | text |
| Company | `#company` | text |
| Permit type | `#permit_type` | native select — pass the option's visible text |
| Start date (dd-mm-yyyy) | `#start_date` | text |

## §2 — Work site (`Next` = `button[type=submit]`)

**Order matters:** step 1 is `{"selector": "#local_only", "value": "false"}` — the
filter checkbox starts CHECKED and hides/disables the non-local municipality
options until unchecked. Then:

| Field | Selector | Control |
| --- | --- | --- |
| Municipality | `#municipality` | native select |
| Street | `#street` | text |
| House number | `#house_number` | text |
| Postcode | `#postcode` | text |
| City | `#city` | text |
| Liability insurance? | `input[name=has_insurance][value=Yes]` (or `=No`) | radio |
| Night work? | `input[name=night_work][value=Yes]` (or `=No`) | radio |

## §3 — Review page

The declaration checkbox is `input[name=declaration]` — a single `check` step,
**no** `submit_selector`. The **Submit application** button is clicked explicitly
by ref after a fresh snapshot (the skill's step 4) — an irreversible action is
never part of a batch.
