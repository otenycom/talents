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
   (`browser_download` retrieves it). Two stores keep a sign-in: website
   passwords (`connect_login` / `list_logins` / `disconnect_login`) and the
   cookie snapshot (`browser_list_profile` / `browser_save_profile` /
   `browser_clear_profile`). Check "am I already signed in?" before routing a
   login. Never print a profile id.
2. **The bot sees pages as accessibility trees, not DOM.** After
   `browser_navigate`, and after each `browser_type` / `browser_click` /
   `browser_focus` (and a CDP aim), the wrap echoes `generation` and
   `tree`. Same hash: the result stays tiny — keep last `@eN`, do not
   call `browser_snapshot`. Hash changed: that same result already
   carries the full tree (`this-snapshot`, `@eN`, named, nth). Call
   `browser_snapshot` only when there is no tree yet. First look is
   navigate or the first attached aim result. `browser_scroll` peeks
   once at the end. `browser_press` and `browser_back` peek under that
   same rule. So do `browser_dialog`, `browser_console` when
   `expression` runs page JS, and mutating `browser_cdp`. Vision,
   images, download, the cookie jar, logs-only console, read-only CDP,
   and human handoff stay without a peek. `value_matched` is not on
   the model type JSON. Trust `confirm` / `confirm_text` on the
   type result.

   `match` (`set value matches input`): continue.
   `differ` (`set value differs from input`) with `set_value`:
   look at that one value; if it is a format of what you sent,
   continue and do not retype.
   `differ` without `set_value`: the tool already failed
   (empty); do not blindly retype the same `@eN` after a dead
   confirm, and use a named selector only if the tool result
   says the write did not land and you still need that field.
   `unseen` (`set value could not be verified`): do not retype.
   Do not call `browser_snapshot` for this class; continue only
   if a later attached tree already shows the field, otherwise
   stop that field because the host already fail-closed.

   Elements are `[ref=eN]` with roles and visible
   labels — **never CSS ids or classes**. Your bot cannot "read the
   selectors off the page", and the JS escape hatch is policy-gated
   (see fact 3). Consequence: **if your skill needs CSS selectors, the
   skill must ship them** — see the selector map below. Prefer
   role+name locators the attached tree already shows.
3. **JS evaluation is safety-gated.** `browser_console(expression=…)` refuses to
   read form values, cookies, storage, or network primitives (a prompt-injected page
   must not be able to steer the bot into exfiltration). So a skill can never verify
   a form via JS — verification is the attached tree after the native click or type.

## Which tool for which job

| Job | Tool | Why |
| --- | --- | --- |
| Open a page | `browser_navigate(url)` | Returns a compact snapshot too — no separate snapshot call needed after navigating. |
| See the page | Last aim result, or `browser_snapshot(full?)` | After type, click, scroll, press, or back the wrap already echoes `generation` + `tree`. Use that tree. Call `browser_snapshot` only when no tree exists yet, or when you asked for `full=true`. |
| Fill a form page | `browser_click(ref)` / `browser_type(ref, text)` | One native action at a time. Use the last attached tree or hash for the next aim. Prefer `role=group[name=…] >> role=radio[name=…]` and `role=combobox[name=…]`. There is no batch fill tool. |
| A login / 2FA wall | `browser_request_human(reason)` — or better, a stored login via `connect_login` | Hand off **once**, then wait. Never type a password from chat; never re-click sign-in on a 2FA/rate-limit wall. |
| Check the cookie snapshot | `browser_list_profile` | Returns `{exists}` only. Website passwords are `list_logins`. |
| Save the cookie snapshot | `browser_save_profile` | Marks save-on-close. Result is `{ok, saved:false, when:"on_close"}`. A persist-false window cannot save. |
| Forget the cookie snapshot | `browser_clear_profile` | Drops the jar. Passwords stay. The owner can also Clear on OtenyBot Details. |
| Get a downloaded file | `browser_download(path?)` | The file is in the cloud, not on the box. Never `ls ~/Downloads`, never cookie-plus-curl. |
| Read a picture-only page | `browser_vision(question)` | The slowest browser tool — reserve it for what the DOM genuinely cannot tell you. A DOM snapshot answers almost everything. |

## The selector map — your skill ships the selectors

Native click and type target the snapshot ref, or a role+name locator you
ship. Snapshots don't expose CSS ids (fact 2), so the bot can't derive CSS
selectors at runtime — **you** derive role+name (and any CSS fallback) once,
at authoring time, and ship them in the skill:

- Put a per-page map in your skill's `references/` (e.g. `form-selectors.md`): one
  section per wizard page listing each field's selector, the control type, and the
  page's **named** advance control. Do not assume every page uses the same Next
  label. A later page may say *Summary* or *OK* where earlier pages said *Next*.
  Derive that name from an observed live trace, never from the stub.
  Scroll the target into view **before** the native click. A control below the
  fold misses, then costs a whole model turn.
- Text inputs and selects usually have stable ids (`#first_name`); radios often
  have only a name — target one option as `input[name=group][value=Yes]`; a
  checkbox without an id the same way.
- `label="Visible field label"` targeting works too (it matches what snapshots
  show) — useful when ids are unstable, ambiguous when labels repeat (six Yes/No
  radio groups on one page — use the name+value form there).
- Add a **portal-change check** to your skill: before filling each page, confirm
  the expected labels are present (use the last attached tree). If the portal was redesigned,
  selectors miss, the native click or type fails — your skill
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

## Fill discipline (the short form)

One native click or type at a time. Type by the printed name, not a
chat sticker. Worked snapshot (role vs neighbour widgets vs remint):
[`business-bot-pattern.md`](business-bot-pattern.md) §4g. The tree is
available **after** the action — do not snapshot to start the next
field. Same hash: keep last `@eN`. Hash changed: use the attached
tree (`this-snapshot`). Call
`browser_snapshot` only when there is no tree yet. Sequence
unlock-then-set interactions (untick a filter before selecting the option
it hides) as separate actions. **Never batch across a server round-trip**:
a search that populates fields, a cascade where each pick loads the next.
**Never** treat an irreversible/final submission as a silent next-click —
use the last attached tree, then click that named control. Full rationale:
[`business-bot-pattern.md`](business-bot-pattern.md) §6.

`TOOLS.md` and `tools-reference.md` are **generated** from the platform
catalog (`python -m hermeshost tools-catalog`). Do not hand-edit them.
The bot-facing contract for native click / type / snapshot / navigate is
the `hh-browser` schema wrap (plugin `1.9.15`). A later catalog generate
picks that up. Do not invent a second contract. There is no
`browser_fill_form`. Do not write "never `@eN`".

## Logins and credentials

Your skill never handles a password. Two stores stay separate. Route logins:

- **Website passwords** → the owner saves them once via `connect_login` (a
  secure link — the credential never transits chat). List with `list_logins`.
  Forget with `disconnect_login`.
- **Cookie snapshot** → `browser_list_profile` (`{exists}` only),
  `browser_save_profile` (save on close, not now), `browser_clear_profile`
  (whole jar). Never print a profile id.
- **One-off login / 2FA / captcha the solver missed** → `browser_request_human`,
  exactly once, then wait for the owner's "done". The session resumes logged in.
- Write the pre-check into your skill: navigate first and *check whether you are
  already signed in* before routing anything.

The platform sets persist and attach. A signed-in / live-view window is
persist-true and attaches the snapshot. A scheduled or isolated window is
persist-false and still attaches. A page-read (`web_extract`) is persist-false
and attach-false. At most one persist-true window is live. A second persist-true
window adopts it. Persist-false plus attach while a writer is live returns HTTP
409 `session_jar_in_use`. A sixth new window returns HTTP 409 `session_cap`.
Do not retry 409. The per-bot new-window cap is 5. A fleet idle ceiling of 4
closes the oldest idle window. That idle close is not a 409, and it is not
"max 1 browser". One live isolated turn per bot is a workflow rule — see
[`business-bot-pattern.md`](business-bot-pattern.md).

## Fail-closed wiring (what your skill must say)

A blocked navigation, a repeated identical browser error, a page that doesn't
match the portal-change check, or a missing confirmation value all mean **the job
did not happen**: write nothing to your system of record, advance no state,
escalate per your workflow, stop. Never let the bot construct a "plausible" value
(a confirmation number, a reference id) — those are read off the page or they
don't exist. The full pattern (write-ahead intent, proof-from-the-page, the
idempotency fences): [`business-bot-pattern.md`](business-bot-pattern.md) §4.

## What sits under the browser tools — the `hh-browser` platform plugin

The browser tools are not part of your Talent. Oteny delivers them as a platform plugin,
`hh-browser`, versioned and shipped independently of anything you write. That matters to you
in three places, because each one looks like a bug in your skill and is not.

**A slow browser call is usually not a slow site.** Every raw-CDP call runs a
private-page safety probe first, and that probe has its own timeout. When it fires, one
click can cost five seconds while the site itself answered instantly. Before you tune your
skill for a "slow portal", ask Oteny to split the calls on that probe. Tuning against the
wrong cause is how a skill grows waits it never needed.

**A field readback can be masked.** Browser output passes a secret redactor before the bot
sees it, and a long unbroken digit run after a `+` looks like a secret. So a phone number
typed as `+35226310828` reads back as `+352****0828`, while `+352 26310828` comes back
whole. Never have your skill re-type a value because the readback "looks wrong". Verify from
the attached tree's validity state instead.

**Prefer the named selector, and pass it without an `@`.** The `@` form means a snapshot
ref. A named selector carrying one resolves to nothing. Your skill should state **one**
click method rather than banning several, because a rule that forbids every available path
pushes the bot onto the raw-CDP escape hatch the rule was written to prevent.

**That advice only became true on 2026-08-28, and the history is worth knowing.** A
`role=…` or `text=…` selector used to fail on the host, whatever the Talent said. The
browser CLI's resolver has two branches only, an `xpath=` prefix and
`document.querySelector`, so a Playwright engine prefix arrived at `querySelector` as
literal text and matched nothing. It returned `Element not found` every time.

On a real production filing that pushed the bot onto raw mouse events at three model round
trips per click. `hh-browser` 1.9.4 now translates a named selector into the `xpath=` form
the daemon does resolve, inside the same call, and it tries an exact match before a
substring match. So a named selector is now one round trip and it works. CSS and `xpath=`
always worked, if you need to reach past a name.

## When the bot is right and the page disagrees — read the recording

A snapshot records what the bot asked for, and a trace records what the tool did. Neither
records a tooltip, a validation banner, or a modal the bot never read into its context. So
when your skill looks correct and the portal still refuses, the session recording is the
only witness.

Oteny keeps a video of every cloud-browser session and pulls it with
`hermeshost/scripts/steel_sessions.py`, which lists sessions for a day and extracts frames
for a chosen window. Ask for the window around the failing timestamp rather than the whole
session. There is no structured event stream, so the answer comes from reading frames.

It settles the question authors get wrong most often, which is whether a rejection is bad
client data or bad formatting. On the Barney MFNL filing the portal refused
`+35226310828` and accepted `+352 26310828`. Those are the same eleven digits, and the only
difference is one space. The record had said "client data, the bot cannot fix this", and the
frames showed a formatting rule the skill can normalise for. So when a case blames the
customer's data, check the recording before you write that into a skill.

**Do not infer a validation rule from `value_len` alone.** A snapshot that records a
length is not a rejection. A stub double that rejects a value the real site accepted is
a false red: a skill change that matches production then fails the stub. Copy the
observed accept and reject strings, and leave the double until those strings are known.

## Verifying your assumptions on a live box

After you declare the browser tools in `agent-profile.yaml` and commission a dev
bot, sanity-check the mounted surface before writing the whole skill: ask the bot
*"list your available tools and their parameter schemas"* (the runtime carries the
same contracts as [`tools-reference.md`](tools-reference.md) — they cannot
diverge), and run one native click or type against your own stub page to see
the attached tree after the fill. The dev-loop recipe:
[`oteny-talent-dev-loop`](../../oteny-talent-dev-loop/SKILL.md).
