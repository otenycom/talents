# Oteny Talents

The open catalog of **Talents** for your [OtenyBot](https://oteny.com) — your own private
AI assistant on Telegram. A **Talent** is a ready-made personality and know-how that gives
your OtenyBot a focused role: **FlatbellyBot** the flat-belly coach, **ShopBot** the shared
aisle-sorted grocery list, **StockBot** the numbers-first stock analyst, **TravelBot** the
travel concierge.

Everything here is **open** ([Apache-2.0](LICENSE)) — read any Talent end to end, learn from
it, and publish your own. Oteny does the hard part — hosting your OtenyBot, running it
safely, and covering the model bills — so a great Talent is all you bring.

> Browse the live store at **[oteny.com/bots](https://oteny.com/bots)**.
> Want to write one? Start at **[oteny.com/bots/build](https://oteny.com/bots/build)**.

---

## How Oteny Talents work — the 2-minute picture

If you read nothing else, read this. It explains *what a Talent actually is*, *why it's safe
to run a stranger's Talent*, and *how a Talent gets from this repo onto a live bot*.

**A Talent runs on its own private server, sealed off from everyone else's.** A Talent ships a
**persona** (a voice + a job), a bundle of **skills** (markdown playbooks the bot reads), and
often its own **scripts** the bot runs as tools (a first-run check, a data migration, a custom
view); it composes the **tools Oteny provides** — web search, a database, a browser, a scheduler
— by *requesting* them in `agent-profile.yaml`. Each user's OtenyBot gets its **own always-on private
computer** — a real machine of its own, where it remembers what you tell it, keeps its own
data, runs automations on a schedule while you're away, and grows its own tools and skills over
time. The hard wall is *between* bots: a Talent can never reach another user's bot, their data,
or Oteny's keys and control plane. So a Talent is powerful inside its own bot and
powerless outside it — even an unreviewed one can, at worst, only affect the bot running it,
never yours. That's why the catalog can be fully open.

**Oteny runs the bot; you bring the Talent.** Each user gets their own OtenyBot in an isolated
sandbox (its own memory, its own database, its own schedule). Oteny provisions it, keeps it
running, and pays the model bills. A Talent is dropped *into* that bot — it never sees a
server, a key, or another user.

**A Talent reaches a live bot by git delivery.** When a Talent's bundle changes here, Oteny
fetches it at the pinned version, runs the lint gate, and delivers it to every bot using it —
*staged, swapped in, self-checked, and rolled back automatically if the self-check fails*. So
a content push reaches the bot with no servers and no downtime.

**Two independent clocks.** The **store/website** (what's listed at oteny.com/bots) and the
**per-bot delivery** (what's actually running on a tenant) update on their own schedules — a
Talent can be live on bots before its store page changes, or vice-versa. Don't assume one
implies the other.

---

## What's in this repo

```
skills/
├── talent-authoring-standard/   the RUBRIC a Talent must meet (+ the lint rules that enforce it)
├── oteny-talent-authoring/      the HOW-TO: create → edit → package → publish
├── oteny-talent-dev-loop/       the TEST/SHIP loop: clone → reload → test → traces → green → tag
├── oteny-flatbelly-talent/      a private flat-belly coach          ┐
├── oteny-shopbot-talent/        one shared grocery list, by aisle   │ the four reference
├── oteny-stock-talent/          terse, numbers-first stock research │ Talents — read these
├── oteny-travel-talent/         a private travel concierge          ┘ as worked examples
└── _shared/                     scripts every bundle reuses byte-identical (selfcheck, migrate, …)
tests/                           the catalog's own unit + scenario tests (CI runs them per PR)
TOOLS.md                         the catalog of tools a Talent may request
```

The first three `skills/` entries are the **author docs** — the rubric, the how-to, and the
test/ship loop. The four `*-talent/` bundles are **reference Talents** you can copy from.

### A Talent bundle, file by file

Each marketable Talent is a self-contained directory:

| File / dir | What it is |
| --- | --- |
| `agent-profile.yaml` | The bundle's contract: persona, which child skills load, the tool request, and a `version:` (semver). |
| `SKILL.md` + child skills | The markdown playbooks the bot reads — the actual know-how. |
| `references/` | Longer docs the skills link to (kept out of the always-loaded context). |
| `scripts/selfcheck.py` | The first-run judge — confirms the bot has everything the Talent needs before it serves. |
| `required_artifacts.yaml` | What `selfcheck` checks for (a database, a config row, …). |
| `migrations.yaml` | Ordered, forward-only steps that reconcile a bot's stored data when the Talent's shape changes. |
| `neutralize.yaml` | How to make a *clone* of this Talent safe to test (disable live emails/crons, point seams at staging). Required if the Talent does anything outbound. |
| `tests/` | The author's own tests — `scenarios/*.yaml` (behavioral) + `unit/` + `fixtures/`. **Never delivered to a bot.** |

Some bundle docs link to **Oteny platform skills** (e.g. `index-reconciler`, which wires the
Talent's routing) that run on the bot's machine, not in this catalog — so a few in-bundle
links resolve only once the Talent is delivered.

---

## The three workflows

### 1. Author a Talent — write the persona + skills

Read the **[talent-authoring-standard](skills/talent-authoring-standard)** (the rubric: numbered,
verifiable do-lists — the "airline-pilot checklist" rule), then follow
**[oteny-talent-authoring](skills/oteny-talent-authoring)** (create → edit → package → publish,
with helper scripts). See **[TOOLS.md](TOOLS.md)** for every tool a Talent may request.

### 2. Test & ship a Talent — prove it *behaves*, not just that it lints

Linting proves the bundle is well-formed; it never sends the bot a message. To prove behavior,
the **[oteny-talent-dev-loop](skills/oteny-talent-dev-loop)** stands the Talent up on a real,
disposable, **neutralized clone** of a bot and runs your `tests/scenarios/*.yaml` against it —
then lets you read the bot's debug traces, fix, and re-run in minutes:

```
lint-talent → clone → reload (your branch) → test → traces → fix → green → tag a release
```

This is also the only honest way to prove a **migration** works against real prior-shape data
before it reaches a paying customer. (Today Oteny and trusted partners drive this loop via the
Oteny dev CLI; one-push `commit → staging → green/red` for self-serve authors is rolling out.)

### 3. Publish — open a PR, get verified

Run the gate locally, open a PR, and a reviewer verifies it (see [CONTRIBUTING.md](CONTRIBUTING.md)):

```bash
python skills/talent-authoring-standard/scripts/lint_upgrade_safe.py skills/<your>-talent
# exit 0 = pass, 1 = fail; add --json for machine-readable output
```

The **same lint rules** gate your PR, Oteny's delivery, and the on-device self-check — so a
green PR means no surprise rejections. CI ([`.github/workflows/talent-lint.yml`](.github/workflows/talent-lint.yml))
runs it on every push. A merged Talent lists as **Community** until a reviewer marks it
**Verified**; a clean automated test run can pre-clear that review.

---

## Where to go for what

| I want to… | Read |
| --- | --- |
| Understand what a Talent is and how it's delivered | this page (above) |
| Learn to write my first Talent, from scratch (newcomer's guide) | [`docs/writing-a-talent.md`](docs/writing-a-talent.md) |
| Know the rules a Talent must satisfy | [`skills/talent-authoring-standard/`](skills/talent-authoring-standard) |
| Write or edit a Talent step by step | [`skills/oteny-talent-authoring/`](skills/oteny-talent-authoring) |
| Test, clone, debug, and ship a Talent | [`skills/oteny-talent-dev-loop/`](skills/oteny-talent-dev-loop) |
| See which tools a Talent can request | [`TOOLS.md`](TOOLS.md) |
| Copy a working example | any `skills/*-talent/` bundle |
| Open a PR | [`CONTRIBUTING.md`](CONTRIBUTING.md) |

---

## Licensing

This catalog is **Apache-2.0** (see [LICENSE](LICENSE) + [NOTICE](NOTICE)) — open content,
contribute freely. The Oteny platform that hosts and runs these Talents is proprietary and is
not part of this repo. Paid third-party Talents may ship under a separate commercial licence,
and a business's private Talents are not published here.
