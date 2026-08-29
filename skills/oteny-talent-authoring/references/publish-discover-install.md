# How the Talent Market works — publish, discover, install

You wrote a Talent. This explains what happens next: how it gets **published**, how
people **discover** it on the Oteny Talent Market, and how it gets **installed** onto a bot.

The one idea to hold on to: **you write and declare content; the platform does the
rest.** You never build a web page, wire a server, or push files to anyone's bot. Your
Talent is a bundle — a persona plus its skills, described by `agent-profile.yaml` and a
few presentation files. Everything downstream (the storefront page, the deep links, the
delivery to a bot) is a **projection of what you declared** — the platform renders and
routes it. Nothing is hand-wired per Talent.

A useful mental model is **two destinations on two clocks**: the **Talent Market**
(`oteny.com/talents`) is the *shop window* a prospect browses; a **bot's box** is where your
Talent *actually runs*. A Talent can be live in the shop before any bot has it, or
running on bots before the shop shows it — the two update independently.

## Publishing

Publishing is how your bundle enters the **catalog** — the single index every surface
reads from. There are two ways in, depending on where you authored it:

- **You authored it in a git repo** (the developer path). You push; Oteny pulls. Your
  GitHub login never leaves your laptop
  ([`how-delivery-works.md`](../../oteny-talent-dev-loop/references/how-delivery-works.md)).
  Open a PR to the catalog repo; the same lint + behavioral tests that gate delivery run
  in CI (`oteny-talent-lint` — the authoring standard). On merge it becomes available, and
  it is re-delivered to every bot that already has it within a few minutes — nobody at
  Oteny has to do anything. Cut a release tag to move it to production owners; roll back
  by re-tagging.
- **Your bot built it for you on the box** (the owner path). Ask your bot to *publish my
  Talent*. It runs a **self-check** against the same standard and grades it green / yellow
  / red; on a clean pass it files a **publish request** that lands in Oteny's review queue.
  Someone at Oteny reads the rendered bundle and promotes it into the catalog. (Ask for a
  *health report* any time to see which of your Talents are share-ready and what to fix.)

Either way the **lint is the gate** — a Talent that already follows the standard sails
through, and a deeper **safety validation** (next) runs before it can affect a customer.
Once in the catalog a Talent lists as **Community** (merged, works, not yet hand-reviewed)
and can earn the **Verified** mark after Oteny curation. Reputation rises on clean automated
test runs and is dinged by community flags; enough flags pull a listing off the shelf until
someone at Oteny clears it.

**What you control:** the bundle itself and its presentation. **What the platform does:**
strips out anything specific to the bot your bundle came from, runs the lint, lists it in
the catalog, and keeps every owner's copy fresh. You never edit the catalog entry by hand —
it is built from your bundle, so the bundle is the source of truth.

## Validation

Between publishing and reaching a customer, every Talent is **validated** — because the whole
promise of a scoped bot is that it *stays in its lane*. Two checks run, at two different
moments, and neither asks anything of you beyond writing an honest bundle.

**A structural safety check — on every delivery, automatically.** Before your bundle is ever
overlaid onto a bot, the platform checks that its declared scope holds together: a bot that
files on a real portal can't reach the live site from a test box; a locked bot has a clear
scope anchor; a bot with a data connection isn't also carrying a general-purpose shell it does
not need. A bundle with a hole like that is **blocked before it reaches any bot** — it never
ships. This is free, instant, and runs on every delivery, updates included.

**An adversarial red-team — the jailbreak test.** The deeper check *attacks* a disposable copy
of your bot to see whether it holds scope under pressure. The platform reads what your Talent
is meant to do and generates a battery of attacks tailored to it — *"ignore your instructions,"
"paste me your API key," "run this code," "go file this on the real site," "just make up a
confirmation number," "dump every record you can reach,"* and more — then grades whether the
bot refused each one. The attacks are labelled against the recognized AI-security checklists
(OWASP's Top 10s for agentic and LLM apps, and MITRE ATLAS), so the result is a scorecard an
outside auditor recognizes. A Talent passes only if it refuses **everything**.

Those attacks always run against a **neutralized clone** — a throwaway copy whose real
connections (a customer's system, a live portal, stored logins) are repointed to a safe test
setup first — so a red-team run can never touch real data or take a real action.

**Who runs what.** You can *pre-check your own* Talent: see exactly which attacks will be
thrown (no bot needed), and on a dev copy get the refusal scorecard — so you fix problems
before you submit. But the check that actually earns trust is **re-run by Oteny**, from your
committed bundle, on Oteny's own infrastructure. Your self-run is a fast feedback loop; Oteny's
run is the authoritative one — a badge only means something if the person earning it is not also
grading the exam. (It mirrors the lint gate: your CI is advisory, Oteny's run at delivery is what
counts. Your bot's own *health report* grades your bundle against the authoring standard; the
scope-safety and red-team checks are Oteny's to run.)

**What passing buys you.** A Talent that clears both checks lists as **Community** and is
eligible for the **Verified** mark after Oteny curation — the signal a customer trusts when they
pick a bot off the shelf. And because every attack is generated from *your own declared scope*,
there is no secret exam and nothing to game: a tighter, more honest bundle — the smallest set of
tools that does the job, a fenced portal, access limited to exactly what the work needs, and a
playbook that stops rather than guesses — is simply what makes the attacks bounce off.

## Discovery

A published, **public** Talent appears on the **Talent Market** at `oteny.com/talents`: a
filterable grid of cards, narrowed by **category** and ordered by **reputation** within a
featured tier (higher-reputation Talents float up; ties fall back to name for a stable
order). Every card links to a **landing page** at `oteny.com/talents/<your-slug>`.

You do not build that landing page — **it is rendered entirely from what you declare** in
the bundle:

- `display_name` + `tagline` — the card title and hero line.
- `long_md` — the landing-page "what it does" body (Markdown, rendered and escaped).
- `category` — which filter chip and section it lands in.
- `icon.png` — the square card / landing mark (a glyph is used if you ship none).
- `teaser.yaml` — a sample-chat "show, don't tell" demo rendered on the landing page.
- `price` — free, or a price shown on the card (`0` = free).

**Visibility** is yours to set and decides who ever sees the row:

- **public** — listed in the storefront grid.
- **unlisted** — not in the grid; reachable only by its direct landing-page link.
- **private** — only the owning business sees it, through their own per-owner store (a
  business's internal Talent is never on the public shelf).

Every card and landing page composes the same **cold-acquisition deep link** —
`t.me/<oteny-bot>?start=talent-<your-slug>`. That link is the discovery-to-install bridge:
following it hands the visitor a bot that is *already your Talent* (see below). The slug is
lowercase letters, digits, and hyphens — it is the acquisition token baked into the link, so
keep it stable.

## Installation

"Install" means your bundle reaches a bot's box and starts running. Every Talent gets there
the same way — **your bundle's files are copied into the bot's private box** — so "install"
is really just *the moment your bundle joins what that bot has been given*. There are two
moments that happens:

- **On launch (the bot arrives in-role).** When someone starts a bot through your Talent's
  deep link, the new bot is **built already being your Talent** — your bundle is delivered
  and focused while the bot is being set up, so it is your Talent from the first message.
  This is the *preferred-Talent* path: the deep link carries your slug, and the front door
  hands the new owner a bot that opens in-role.
- **On request (added to an existing bot later).** An owner opens their **per-owner store**
  (their private shelf of what they have and can add) and taps **Add to my bot**. That
  records the request; the next delivery round copies your bundle onto their box within a few
  minutes and the bot introduces the new capability in chat. Adding checks two things: that
  they are allowed it (a private Talent only for its owning business) and that their plan
  covers it (a Talent that needs a heavier machine shows an upgrade prompt rather than a
  broken install).

After that first install, your bundle rides the bot like any other: it is preserved across
updates, backed up, and — for a git-published Talent — **re-delivered automatically within
~5 minutes** whenever you push a change to its source. You ship an improvement; every owner
gets it, with nobody at Oteny in the loop.

## What you declare vs what the platform binds

You bring the content; the platform renders and runs it — you never hand-build a page or
wire a delivery:

- **The persona + skills** (`agent-profile.yaml`) → the locked scope the bot runs inside,
  the delivery, and what its usage costs.
- **`display_name`, `tagline`, `long_md`, `category`, `price`** → the Talent Market card and
  landing page.
- **`icon.png`, `teaser.yaml`** → the card mark and the sample-chat demo.
- **`visibility`** (public / unlisted / private) → who sees the row and the per-owner store.
- **The slug** → the `t.me/…?start=talent-<slug>` deep link.
- **A green bundle** (one that passes the standard) → a Community listing, then Verified
  after curation.

If a second, unrelated Talent existed tomorrow, it would go through this exact path with
none of your specifics — that is the point. The mechanism is generic; your bundle is the
only thing that is yours.

## Tools your Talent can request

The live toolbox is
[`tools-catalog.md`](../../talent-authoring-standard/references/tools-catalog.md).
Exact call contracts (parameters, result shapes, worked examples) live in
[`tools-reference.md`](../../talent-authoring-standard/references/tools-reference.md).
Customer cards on [oteny.com/talents/tools](https://oteny.com/talents/tools) come from
that same catalog. Some tools are for the bot only and do not get a public card.

Two stores stay separate. Website passwords are `connect_login`, `list_logins`, and
`disconnect_login`. The cookie snapshot is `browser_list_profile`,
`browser_save_profile`, and `browser_clear_profile`.

- `browser_list_profile` returns `{exists}` only. Never print a profile id.
- `browser_save_profile` returns `{ok, saved:false, when:"on_close"}`. It marks
  save-on-close. It does not save now. A persist-false window cannot save.
- `browser_clear_profile` drops the cookie snapshot. Passwords stay.

The platform sets persist and attach. You do not pass those flags.

- A signed-in or live-view window is persist-true and attaches the snapshot.
- A scheduled or isolated window is persist-false and still attaches.
- A page-read (`web_extract`) is persist-false and attach-false. It may sit beside
  a writer.

At most one persist-true window is live. A second persist-true window adopts that
live window. Persist-false plus attach while a writer is live returns HTTP 409
`session_jar_in_use`. A sixth new window returns HTTP 409 `session_cap`. Do not
retry 409. Treat 409 as a stop, then wait or ask the owner.

The per-bot new-window cap is 5. A separate fleet idle ceiling of 4 closes the
oldest idle window. That idle close is not a 409, and it is not "max 1 browser".
One live isolated turn per bot is a workflow rule, not a browser cap of 1. See
[`business-bot-pattern.md`](../../talent-authoring-standard/references/business-bot-pattern.md)
and
[`browser-authoring.md`](../../talent-authoring-standard/references/browser-authoring.md).

## Where to go next

- **The standard** — what a bundle must meet (the rubric the lint enforces):
  [`talent-authoring-standard`](../../talent-authoring-standard/SKILL.md).
- **The how-to** — create, edit, package, publish, health-check, export/import:
  [`oteny-talent-authoring`](../SKILL.md) and
  [`export-import.md`](./export-import.md).
- **The toolbox** — every requestable tool, then the exact call contracts:
  [`tools-catalog.md`](../../talent-authoring-standard/references/tools-catalog.md)
  and
  [`tools-reference.md`](../../talent-authoring-standard/references/tools-reference.md).
- **Store presentation** — the icon + teaser assets your landing page renders from:
  [`store-presentation.md`](../../talent-authoring-standard/references/store-presentation.md).
- **The safety gate up close** — the scope and red-team checks a business bot is graded
  on, and how to keep your contract clean:
  [`business-bot-pattern.md`](../../talent-authoring-standard/references/business-bot-pattern.md)
  (§2b).
- **The dev loop** — from your repo to a live bot:
  [`oteny-talent-dev-loop`](../../oteny-talent-dev-loop/SKILL.md).
