# Writing your first Oteny Talent

Welcome. This is the doc to read **before** you write your first Talent. You have
never written one, and that's fine — by the end you'll understand what a Talent is,
how its files fit together, and how a change you make in git reaches a live bot. We
lean toward the newer pattern most readers will want: a **scoped business bot** (a
single-job bot that converses inside a chat channel) — the kind of bot **Barney** is
(more on Barney below).

This is a guide for humans, so it reads as prose. (A Talent's own files follow a
stricter "checklist-first" style for the bot to execute — that rule is for the bot,
not for this page.)

---

## 1. What a Talent actually is

A **Talent** is a folder of plain files — markdown instructions plus a few small YAML
manifests — that gives a bot a focused role: a flat-belly coach, a stock analyst, a
posted-worker filing desk. Two ideas matter most, and they're what make Talents safe:

**A Talent is instructions plus a *request* for tools — not raw power.** A Talent does
not *contain* the ability to run shell commands, drive a browser, or write to a
database. It can only *ask* for those capabilities, by listing them in its profile.
The thing that actually decides what the bot can do is the **host harness** (the bot's
Hermes runtime on its own private machine). The harness reads the request and mounts
*only* what it's willing to grant. A Talent can never grant itself a tool the harness
withholds.

**So the prompt can't escape the toolbox.** Even a buggy — or maliciously
prompt-injected — Talent can, at worst, misbehave with the exact tools the harness
already gave it. It cannot reach for a shell that was never mounted, touch another
bot, or read Oteny's keys. The wall is between bots, enforced by the platform, not by
trust in the Talent's text.

That's *why* it's safe to let a domain team own a Talent. The CrewRadar team can edit
Barney's instructions and field maps all day without the power to do anything outside
the locked toolbox the platform handed Barney. The Talent is powerful inside its bot
and powerless outside it.

---

## 2. The anatomy of a Talent bundle

A Talent is a self-contained directory. Here are the files you'll meet, the load-bearing
ones first:

| File / dir | What it is |
| --- | --- |
| `agent-profile.yaml` | The contract: the persona, which child skills load, the **tool request**, the routing, and a `version:`. Start here. |
| `SKILL.md` (+ child skill dirs) | The markdown playbooks the bot reads — the actual know-how. A simple Talent has one; a richer one composes several. |
| `required_artifacts.yaml` | The bot's "setup goal" — every thing that must exist before it can work (a database, a profile file, registered routing), each with a machine-checkable condition. |
| `references/` | Longer docs the skills link to, pulled on demand (kept out of the always-loaded context). |
| `scripts/selfcheck.py` | The first-run judge — confirms the bot has everything `required_artifacts.yaml` lists before it serves. |
| `migrations.yaml`, `neutralize.yaml`, `tests/` | Forward-only data reconciliation, how to make a test-clone safe, and the author's behavioral tests (never delivered to a real bot). Skip these until you need them. |

The single most important file is **`agent-profile.yaml`**. It is the whole contract.
Here is a real, minimal one — Barney's conversational foundation, trimmed for clarity:

```yaml
bot: oteny-barney-talent          # internal slug — never user-facing
display_name: Barney              # the name a person sees
tagline: "Your posted-worker (MFNL) desk — files Cuneus's notifications and keeps the proof."
version: 0.1.0                    # Talent semver — bump on every change

skills:                           # the composing skills delivered together
  - oteny-barney-talent
voice_skill: oteny-barney-talent  # which skill carries the persona

base_language: en                 # always author in English; the bot replies in the owner's language
model_tier: builder               # GLOBAL on the agent, not per-Talent

# The TOOL ALLOWLIST — exactly the tools this bot gets. Nothing else mounts.
toolset_contribution: [send_message, memory, todo]
delivery: baked
price: free

routing:
  channel: discuss                # converse inside an Odoo Discuss channel
  channel_prompt: |
    You are the owner's Oteny bot, acting as their posted-worker (MFNL) desk in this
    Odoo Discuss channel. Load the oteny-barney-talent skill and follow its triage and
    hard rules. Never ask for a password or a one-time code in chat. Reply in the
    operator's language; keep replies short and chat-friendly.
  signature: "oteny-barney-talent"

seed_memory: null                 # nothing baked; identity accrues in the data plane
```

A few fields are worth naming plainly:

- **`bot:`** — the internal slug. It keys the bot's data and routing, so never rename
  it without a migration; it's never shown to a user.
- **`display_name:` / `tagline:`** — the human-facing name and one-line pitch.
- **`version:`** — a semver label over the delivered commit. Bump it on every change.
- **`skills:`** — the list of composing skills delivered together. Each is its own
  directory with its own `SKILL.md`. A simple Talent lists just one.
- **`toolset_contribution:`** — the tool allowlist. The single most important line for
  a scoped bot (see §3).
- **`routing:`** — where and how the bot converses (see §4). `channel_prompt` is the
  standing instruction injected for the bot in that channel.
- **`seed_memory:`** — an optional starter memory file. Leave it `null` and let
  per-bot state accrue in the data plane; never bake one person's data into the bundle.

And **`required_artifacts.yaml`** declares the setup goal — for example, "a SQLite db
at this path with these tables" or "a profile file with these fields filled." It's
what `selfcheck.py` walks to decide the bot is ready. A bundle whose "done" state is
vague can't be validated or self-heal, so this file is where a careful author starts.

---

## 3. The toolset allowlist *is* the locked toolbox

This is the heart of the business-bot pattern, so it gets its own section.

`toolset_contribution` lists **exactly** the tools the bot is allowed to use. The
harness mounts that set and nothing else. Less is safer — every tool you *don't*
request is a thing a hijacked bot has no way to reach.

Compare two real shapes:

- **A broad B2C bot** (a personal assistant) requests the wide set —
  `[terminal, execute_code, cron, send_message]` (Flatbelly's actual line). It can run
  shell, write code, schedule jobs. That breadth is the product: it's *your* private
  assistant.
- **A scoped business bot** (Barney) requests only what its job needs —
  `[send_message, memory, todo]`. **No** terminal, **no** code execution, **no** cron,
  **no** open-web, **no** browser. Barney converses and remembers; it does not run a
  shell or browse the internet, because its job in that milestone doesn't need to.

So when you author a scoped bot, the discipline is: **list the minimum and stop.** If
the job is "answer questions about our HR records and file one form," you do not
request a terminal just in case. You request the lookup tool, `send_message`, and
maybe `memory`. When the job later grows (Barney's filing layer adds a secure browser,
a mailbox reader, and a scoped data connection), you add those *then*, deliberately.

One subtlety that makes this trustworthy: the allowlist is only a *request*. On a
genuinely locked-down instance, the platform *also* disables the generic toolsets at
the gateway — so even if a prompt-injected Talent tried to ask for a shell, there
would be no shell mounted to call. The allowlist is your declaration of intent; the
gateway is the enforcement. Together they're why "Barney has no terminal" is a real
property and not a hope.

---

## 4. Channel routing — where the bot talks

The `routing.channel` field says *where* the bot lives. Two values cover almost
everything you'll write:

- **`channel: telegram`** — a **personal bot**. The owner gets their own private bot on
  Telegram and DMs it (or invites it to topic groups). This is the B2C shape —
  Flatbelly, the stock analyst, the travel concierge.
- **`channel: discuss`** — a **business bot** that converses inside an **Odoo Discuss
  channel** — the chat built into Odoo, where a team already works all day. This is the
  Barney shape: the bot sits in a dedicated channel (e.g. "HR and Barney" inside
  CrewRadar), the team posts to it there, and it replies there. There's no public
  inbound and no separate app to open.

Alongside `channel` you write a **`channel_prompt`** — the standing instruction the
bot carries in that channel. It says who the bot is, which skill to load first, and
the hard rules ("never ask for a password in chat," "reply in the operator's
language"). Keep it tight; it's injected on every turn.

---

## 5. The dev loop — from your git repo to a live bot

You don't need server access to ship a Talent. The platform delivers it for you. The
end-to-end loop (this is the **D124 "external git Talent source"** pattern, already
live in production):

1. **Author in your own git repo.** The Talent lives in *your* repo, in the folder you
   own (Barney lives in the radar repo at `oteny_barney/talents/oteny-barney-talent/`).
   You edit it with the git workflow you already use.
2. **Open a PR.** A published **`oteny-talent-lint`** CI check runs the
   `talent-authoring-standard` against your changed Talent and reports pass/fail with
   the exact violations **inline in the PR**, before merge. Lint must be green to ship.
3. **Merge to a branch → it auto-delivers to a staging bot in seconds** (this is
   **follow mode**: a bot pointed at a branch picks up the merged commit on the next
   poll). Now you can test it live.
4. **Cut a release tag → it delivers to production** (this is **pinned mode**: a
   production bot is pinned to a tag, so it only moves when you cut a new release —
   *you* decide when). Tag convention is a trailing semver that matches your
   `agent-profile.yaml: version:`.
5. **Rollback = re-tag the previous version.** No SSH, no Oteny ops, no new tool.

Every delivery is staged, swapped in, self-checked, and **rolled back automatically**
if the self-check fails — so a push reaches the bot with no downtime and no way to
brick it. The whole UX is git. The platform owns the VM; you never touch it.

(There's also a deeper, optional loop — `clone` a disposable neutralized copy of a
real bot, run your behavioral `tests/scenarios/*.yaml` against it live, and read its
debug traces — documented in `skills/oteny-talent-dev-loop/`. Reach for it when you
need to *prove behavior*, especially a data migration, before a paying customer sees
it.)

---

## 6. Worked example: Barney

**Barney** is the reference scoped business bot, and the one to study when you write
your own. In one breath: it's a private, isolated AI "back-office employee" that does
one tedious legal chore for a crewing agency (filing the Dutch posted-worker
notification, "MFNL"), and reports back inside the Odoo Discuss chat the team already
uses. A human stays in charge — Barney can be set to ask for a "yes" before it files.

Everything in this guide shows up concretely in Barney:

- It lives in the **radar** repo at `oteny_barney/talents/oteny-barney-talent/`, owned
  by the team that knows the domain — not by Oteny.
- It **routes to Discuss** (`channel: discuss`), not Telegram.
- Its toolset is **minimal** (`[send_message, memory, todo]` in its first milestone) —
  the locked toolbox in §3.
- It's **delivered from the radar repo** by the git loop in §5 (follow a branch for
  staging, a pinned tag for production).

Open Barney's `agent-profile.yaml` and `SKILL.md` and read them top to bottom — they
are the cleanest template for a new scoped bot. The generic authoring delta for this
class — Discuss routing, the locked toolset, the `/json/2/` data plane, and the stub
doubles — is [`skills/talent-authoring-standard/references/business-bot-pattern.md`](../skills/talent-authoring-standard/references/business-bot-pattern.md).
The full design story (why it's isolated, the locked-toolbox enforcement, the round-trip
it automates) lives in the hermeshost repo at `skills/design/cuneus-hr-bot.md`.

---

## 7. Common pitfalls

A few real ones that bite newcomers:

- **Requesting tools you don't need.** "I'll add `terminal` just in case" is the
  opposite of the discipline. For a scoped bot, list the minimum and stop — every
  unused tool is attack surface a hijacked bot could reach for.
- **Treating the prompt as the guard.** Don't rely on `channel_prompt` saying "don't
  run shell" to keep a bot safe — rely on **not requesting** the tool (and, on a locked
  instance, on the gateway disabling it). The prompt is guidance; the allowlist is the
  fence.
- **Shipping with a red lint.** The same `talent-authoring-standard` lint gates your
  PR, the platform's delivery, *and* the on-device self-check. A green PR means no
  surprise rejection later; a red one never ships. Run it locally before you open the PR.
- **Baking one person's data into the bundle.** Names, ids, tokens, timezones, a
  specific account — none of that belongs in the delivered files (it's lost on the next
  update and isn't shareable). Per-bot state lives in the data plane; the bundle holds
  only the method.
- **A paragraph for a `description`.** The bot's skill index truncates a skill's
  `description` to ~60 characters to route on it — make it a sharp trigger naming the
  words a matching message contains, not prose.

---

## What to read next

- **[`skills/talent-authoring-standard/`](../skills/talent-authoring-standard/SKILL.md)** —
  the rubric a Talent must meet (and the lint that enforces it). The "must" list.
- **[`skills/oteny-talent-authoring/`](../skills/oteny-talent-authoring/SKILL.md)** —
  the step-by-step how-to: create → edit → package → publish.
- **[`skills/oteny-talent-dev-loop/`](../skills/oteny-talent-dev-loop/SKILL.md)** —
  the test/ship loop: clone → reload → test → traces → green → tag.
- **[`TOOLS.md`](../TOOLS.md)** — every tool a Talent may request.
- **A worked example to copy** — any `skills/*-talent/` bundle (Flatbelly is the
  fullest B2C one; Barney, in the radar repo, is the scoped-business one).
