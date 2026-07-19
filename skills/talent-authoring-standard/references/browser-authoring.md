# Authoring browser-driving skills — the secure-browser discipline

How to write a Talent skill that drives a real website (a portal filing, an export,
a booking) through the Oteny secure cloud browser. This is the **authoring-side**
counterpart of the `oteny-web-operator` skill your bot already carries on its box:
that skill teaches the *bot* the operating rules at runtime; this page teaches *you*
(and your AI coding session) how to write skill instructions that use the browser
correctly. Exact per-tool parameters, result shapes, and worked examples:
[`tools-reference.md`](tools-reference.md). The end-to-end business-bot architecture
(scope-lock, the system-of-record seam, fail-closed): 
[`business-bot-pattern.md`](business-bot-pattern.md).

## The mental model — three facts everything else follows from

1. **The browser is remote.** Your bot drives a real browser running in the cloud,
   not on its own machine. A file the browser downloads is *not* on the bot's disk
   (`browser_download` retrieves it); a login persists in the cloud session across
   turns and days (check "am I already signed in?" before routing a login).
2. **The bot sees pages as accessibility trees, not DOM.** `browser_snapshot`
   returns elements as `[ref=eN]` reference ids with roles and visible labels —
   **never CSS ids or classes**. Native `browser_click`/`browser_type` take those
   refs. Your bot cannot "read the selectors off the page", and the JS escape hatch
   is policy-gated (see fact 3). Consequence: **if your skill needs CSS selectors
   (for `browser_fill_form`), the skill must ship them** — see the selector map below.
3. **JS evaluation is safety-gated.** `browser_console(expression=…)` refuses to
   read form values, cookies, storage, or network primitives (a prompt-injected page
   must not be able to steer the bot into exfiltration). So a skill can never verify
   a form via JS — verification is `browser_fill_form`'s built-in readback, or a
   snapshot.

## Which tool for which job

| Job | Tool | Why |
| --- | --- | --- |
| Open a page | `browser_navigate(url)` | Returns a compact snapshot too — no separate snapshot call needed after navigating. |
| See the page | `browser_snapshot(full?)` | The accessibility tree with `[ref=eN]` ids. Over ~8000 chars it is truncated/summarized — prefer one snapshot per page, at the page boundary. |
| Fill a whole form page | **`browser_fill_form(steps, submit_selector?)`** | One call fills every independent field through the real engine, **reads every value back** (the per-field `ok`/`actual` IS your verify), and clicks next **only when all fields verified**. The default for any multi-field form. |
| One click / one field | `browser_click(ref)` / `browser_type(ref, text)` | For single interactions and for anything `browser_fill_form` must not batch (see below). Take the ref from the latest snapshot. |
| A login / 2FA wall | `browser_request_human(reason)` — or better, a stored login via `connect_login` | Hand off **once**, then wait. Never type a password from chat; never re-click sign-in on a 2FA/rate-limit wall. |
| Get a downloaded file | `browser_download(path?)` | The file is in the cloud, not on the box. Never `ls ~/Downloads`, never cookie-plus-curl. |
| Read a picture-only page | `browser_vision(question)` | The slowest browser tool — reserve it for what the DOM genuinely cannot tell you. A DOM snapshot answers almost everything. |

## The selector map — your skill ships the selectors

`browser_fill_form` targets fields by CSS/Playwright selector or by visible label.
Snapshots don't expose CSS ids (fact 2), so the bot can't derive selectors at
runtime — **you** derive them once, at authoring time, from your portal's DOM in
your own browser devtools, and ship them in the skill:

- Put a per-page map in your skill's `references/` (e.g. `form-selectors.md`): one
  section per wizard page listing each field's selector, the control type, and the
  page's submit button.
- Text inputs and selects usually have stable ids (`#first_name`); radios often
  have only a name — target one option as `input[name=group][value=Yes]`; a
  checkbox without an id the same way.
- `label="Visible field label"` targeting works too (it matches what snapshots
  show) — useful when ids are unstable, ambiguous when labels repeat (six Yes/No
  radio groups on one page — use the name+value form there).
- Add a **portal-change check** to your skill: before filling each page, confirm
  the expected labels are present (one snapshot). If the portal was redesigned,
  selectors miss, `browser_fill_form` reports those fields `ok:false` — your skill
  must halt and escalate, never improvise new selectors mid-run.

## When may a skill go selector-free?

Selectors ship in the skill because the model **can't read CSS ids off the page**
(fact 2) — that is why the map exists at all (D214). But a `label=`/role locator matches
the accessible name the snapshot *does* show, so a
site with clean labels can be driven **without any harvested CSS ids** — the skill then
targets fields by their visible label alone. Go selector-free **only when all of these
hold**:

- **Every field grades resilient with a label-first front rung.** `selector-audit` (the
  static verb, D232) reports each field `resilient` with a `label=` or role+accessible-name
  as the **first** ladder rung — not an id demoted to a fallback.
- **`label=` + `page_digest` cover every step, including submit.** No wizard step needs a
  raw id or an id-shaped submit selector; the page's *Continue*/*OK* is reachable by
  role+name.
- **Labels are unique per page.** No repeated `Yes`/`No` groups where a bare label is
  ambiguous (there you still need the `name[value=…]` form — not selector-free).
- **Fill-verify is green on a label-only manifest.** A dry run (`browser-diff` after an
  observe pass) shows every field resolving 1:1 with no id in the ladder.

Absent all four, keep the **default for third-party sites: label-first rungs FIRST,
harvested ids as later rungs** — the resilience ladder, not a selector-free skill. The
ladder degrades gracefully (a renamed id falls through to the label); a bare-id-only skill
misses mid-filing on the first re-skin.

## Batching discipline (the short form)

One `browser_fill_form` call per form page; steps run in order (sequence
unlock-then-set interactions — e.g. untick a filter checkbox before selecting the
option it hides). Prefer `submit_selector` for boring wizard Next/Continue when the
fill report is all `ok` (the server scales the batch budget with field count and
reserves time for that click — do not assume a flat 75 s). **If the tool says
submit was skipped after a verified fill** (fields all `ok`, skip reason mentions
reserved time / budget), **click that Next button once** — do not re-run the same
`steps` batch. **Never batch across a server round-trip**: a search that
populates fields, a cascade where each pick loads the next — those stay
one-action-at-a-time with the native tools. **Never** pass an irreversible/final
submission as `submit_selector` — final submits get a fresh full snapshot and an
explicit click, per your skill's fail-closed rules. If the tool reports
*unavailable*, fall back to per-field `browser_type`/`browser_click` with one
snapshot verify per group. Full rationale and the never-batch list:
[`business-bot-pattern.md`](business-bot-pattern.md) §6.

## Logins and credentials

Your skill never handles a password. Route logins:

- **Recurring login** → the owner saves it once via `connect_login` (a secure
  link — the credential never transits chat); the browser auto-signs-in on that
  site from then on, even on a schedule.
- **One-off login / 2FA / captcha the solver missed** → `browser_request_human`,
  exactly once, then wait for the owner's "done". The session resumes logged in.
- Write the pre-check into your skill: navigate first and *check whether you are
  already signed in* (logins persist) before routing anything.

## Fail-closed wiring (what your skill must say)

A blocked navigation, a repeated identical browser error, a page that doesn't
match the portal-change check, or a missing confirmation value all mean **the job
did not happen**: write nothing to your system of record, advance no state,
escalate per your workflow, stop. Never let the bot construct a "plausible" value
(a confirmation number, a reference id) — those are read off the page or they
don't exist. The full pattern (write-ahead intent, proof-from-the-page, the
idempotency fences): [`business-bot-pattern.md`](business-bot-pattern.md) §4.

## Verifying your assumptions on a live box

After you declare the browser tools in `agent-profile.yaml` and commission a dev
bot, sanity-check the mounted surface before writing the whole skill: ask the bot
*"list your available tools and their parameter schemas"* (the runtime carries the
same contracts as [`tools-reference.md`](tools-reference.md) — they cannot
diverge), and run one `browser_fill_form` against your own stub page to see the
readback shape with your own eyes. The dev-loop recipe:
[`oteny-talent-dev-loop`](../../oteny-talent-dev-loop/SKILL.md).
