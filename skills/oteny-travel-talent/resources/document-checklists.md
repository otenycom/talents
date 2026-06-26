# Document Checklists (shipped reference data — prompt templates, ALWAYS verify live)

Generic document prompts the `trip-planner` seeds as `todos` (category `document`). Entry
rules depend on **nationality + destination + date** and **change** — every item here is a
**prompt to check**, never a statement of fact. When the tenant asks specifics, check live
via `travel`/`web_search` **and** point them to the official source (the destination
government/embassy, the airline, the IATA Travel Centre). See
[`../references/safety-boundaries.md`](../references/safety-boundaries.md).

## Always
- [ ] **Passport valid** well past the trip — many countries require **≥ 6 months'**
  validity beyond your return date. *(Verify the exact rule for your nationality +
  destination.)*
- [ ] Boarding passes / e-tickets saved offline; booking references noted.
- [ ] Accommodation confirmations (some borders ask for proof of onward/return travel +
  a stay address).
- [ ] Travel insurance details + emergency numbers saved offline.

## Visas & travel authorizations *(check whether YOUR passport needs one)*
- [ ] **Visa** required in advance? *(nationality-dependent — verify with the embassy/
  official portal; allow processing time.)*
- [ ] **ESTA (USA) / eTA (Canada / others)** — a quick online authorization, **not** a
  visa, but required **before you fly**. Apply early; use the **official government site**
  only.
- [ ] **Schengen** day count — some passports are capped at **90 days in any 180**; check
  your remaining allowance.
- [ ] **Transit visa** — needed if you change planes in some countries even without leaving
  the airport? *(verify per layover country.)*

## Health *(destination + personal — verify with a clinic / official health authority)*
- [ ] Required or recommended **vaccinations** for the destination?
- [ ] Proof-of-vaccination / health-entry forms required on arrival?
- [ ] Prescription meds: enough supply, in original packaging, legal at the destination?
- [ ] Travel health insurance covers the activities you plan (e.g. skiing, diving)?

## Driving (if relevant)
- [ ] Driving licence accepted, or an **International Driving Permit** required? *(verify.)*
- [ ] Car documents / rental confirmation; toll/vignette needs for the route?

## Family / minors (if relevant)
- [ ] Each child's own passport/ID + any required **parental-consent letter** for travel
  with one parent or a guardian? *(country-specific — verify.)*

> The bot will help you **find and verify** each of these against the official source — it
> does not decide your eligibility, and it never books or pays.
