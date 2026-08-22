# Demo portal form selectors — the per-page native-click map

Fill each wizard page with `browser_snapshot`, then one `browser_click` or
`browser_type` at a time. Prefer role+name locators the snapshot already
shows. A stub id attribute is a text-field fallback only — not a radio or combobox
primary. After a radio or select, snapshot and confirm the value stuck.
Do not write a checked property or `element.value` through CDP.

*How this file was made (do the same for your portal):* run the portal locally
(`python3 scripts/demo_portal.py --port 8099`), open it in your own browser, and
read the accessible names off the page. The bot cannot derive CSS ids at
runtime — snapshots show roles and labels — which is exactly why the skill
ships this map.

## §1 — Application details (`Next` = `role=button[name="Next"]`)

| Field | Primary | Fallback |
| --- | --- | --- |
| Applicant name | label `Applicant name` | `#applicant_name` |
| Company | label `Company` | `#company` |
| Permit type | `role=combobox[name="Permit type"]` then the option text | `#permit_type` |
| Start date (dd-mm-yyyy) | label `Start date (dd-mm-yyyy)` | `#start_date` |

## §2 — Work site (`Next` = `role=button[name="Next"]`)

**Order matters:** uncheck `Show local municipalities only` first. The
filter starts CHECKED and hides the non-local municipality options.

| Field | Primary | Fallback |
| --- | --- | --- |
| Municipality | `role=combobox[name="Municipality"]` then the option text | `#municipality` |
| Street | label `Street` | `#street` |
| House number | label `House number` | `#house_number` |
| Postcode | label `Postcode` | `#postcode` |
| City | label `City` | `#city` |
| Liability insurance? | `role=group[name="Does the applicant hold liability insurance?"] >> role=radio[name=/^\s*Yes\s*$/]` (or `No`) | — |
| Night work? | `role=group[name="Will work happen at night?"] >> role=radio[name=/^\s*Yes\s*$/]` | — |

## §3 — Review page

The declaration checkbox is the label that starts with `I declare`. Click
it. Then take a **fresh snapshot** and click **Submit application** by
ref. An irreversible action is never a silent next-click.
