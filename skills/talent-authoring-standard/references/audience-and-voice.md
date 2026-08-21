# Audience & voice — who the words are for

Before you write a line in a Talent bundle, name the **reader**. Mixing audiences
is the usual failure mode: a tool API shown as if the owner should run it, or
platform jargon leaking into chat replies.

## Three audiences (keep them fenced)

| Audience | Who | Where their words live | Voice |
| --- | --- | --- | --- |
| **End-user (owner)** | The person chatting with the bot | Store copy (`tagline`, `long_md`), bot **replies**, and any owner-facing "what to type" sections in `SKILL.md` / `references/` | Plain English. Chat sentences. No tool names, no shell, no internal product names. |
| **Bot (weak model)** | The agent executing the Talent | Triage, numbered checklists, **Bot notes** footers, script paths, tool names | Checklist-first (check 11). Literal `input → check → reply/act`. |
| **Talent author / platform eng** | You (or an AI coding agent) building the bundle | This repo's authoring skills, HermesHost `skills/` design library — **not** shipped Talent runtime copy | Runbooks, decisions, seams, code maps. |

A shipped Talent teaches the **bot** how to serve the **owner**. Authoring skills
teach **you** how to build Talents. Do not put author/platform prose into a
delivered `SKILL.md` body that the bot re-reads every turn.

## Owner-facing: type-this, not call-this

Owners never invoke broker tools or scripts. If a capability needs a tool, the
doc's **owner** surface is the chat line they send; the **bot** surface is the
tool call.

**Shape (worked example: WebsiteBot / `odoo-website`):**

1. **What the owner types** — copy-paste chat blocks (`Send:` / fenced messages).
2. **What to expect back** — DNS rows, confirm questions, public URL — still plain
   English.
3. **Bot notes** (footer, clearly labelled) — `attach_site_domains(...)`,
   `host_website(...)`, script paths — only for the model when those lines arrive.

| Fail (API / eng voice) | Pass (owner chat) |
| --- | --- |
| "Call `attach_site_domains` with `domain=example.com`" | `Attach my domain example.com to site mysite (include www).` |
| "Run `host_website(local_port=8069, …)`" | `Put my site online.` → confirm → `Yes, go ahead.` |
| "Invoke `list_site_domains` until SSL active" | `What's the status of my custom domains on site mysite?` |

If the owner asks how to "run `attach_site_domains()`", the bot tells them the
plain sentence and **you** call the tool.

Use **`example.com` / generic `<slug>`** in Talent docs — not customer canaries or
internal lab hostnames.

## Store copy vs runtime instructions

- **`long_md` / tagline / Talent Market** — only the owner. Lead with what they *say*
  and what they *get*. Same type-this honesty as runtime refs.
- **`SKILL.md` + `references/`** — dual: owner phrases first where the flow is
  conversational; bot checklists immediately after (or in a **Bot notes** section).
- **`channel_prompt`** — bot-facing, but remind it: owners type plain sentences;
  never ask them to run tools by name.

## Checklist-first still applies

Audience fencing does **not** replace the airline-pilot bar — it sits on top.
See [`checklist-first.md`](checklist-first.md). Owner sections stay short; bot
sections stay numbered and verifiable.

## Published-copy hygiene

No internal vocabulary in any shipped file (check 4 / [`copy-and-tools.md`](copy-and-tools.md)).
`HermesHost`, `Dnn`, lifecycle milestone names, etc. belong in the platform design
library, not in a Talent the owner (or a public catalog reader) sees.

**The author-facing references are published too — hold them to the same bar.**
[`publish-discover-install.md`](../../oteny-talent-authoring/references/publish-discover-install.md)
is rendered verbatim as **oteny.com/talents/how-it-works**, so the third audience above is
not a private one: an author is an outsider, and a word only Oteny can resolve is just as
broken there as in owner chat. The words that slip in, and what to write instead: the
catalog named by its Odoo model id → just **the catalog**; "a delivery belt" → **it is
re-delivered**; "sanitizes per-tenant state out" → **strips out anything specific to the
bot it came from**; a bundle "overlaid" onto a "provisioned" bot "at commission" → files
are **copied into the bot's private box**, the bot is **built already being your Talent**;
"the scope-lock harness … and metering" → **the locked scope, the delivery, and what its
usage costs**; "no operator step" → **nobody at Oteny is in the loop**.

**What stays:** the names you actually type — `agent-profile.yaml`, `long_md`,
`teaser.yaml`, a tool name in Bot notes. Those are your interface, not jargon. The test is
whether the reader can resolve the word from where they sit.

Fix a failure **here**, then regenerate the page on Oteny's side (`scripts/talents_docs_to_website.py`);
Oteny's test suite scans the rendered page, so a regression in this repo breaks their build.
