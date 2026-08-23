# Tools an Oteny bot can use

> **Generated** by Oteny — do not edit by hand. This is the catalog of tools your
> Talent can request. The Oteny platform runs every tool inside a scope-locked
> harness and meters paid ones at cost — you request a tool, you never wire one up.

**This catalog answers WHICH tools exist. For HOW to call one — the exact
parameters, result shape, error modes, and a worked example per tool — read the
generated [`tools-reference.md`](tools-reference.md) (machine twin:
`tools-contracts.json`). Author against those; never reverse-engineer a tool
from a live box.**

**How to request a tool in `agent-profile.yaml`:**

- A **first-party tool** (web search, images, the browser, file sharing, account
  links) → list its **request name** under `tools.required`.
- A **built-in toolset** (schedule, memory, run code) → list it under
  `toolset_contribution`.

Cost: **Included** (no per-use charge) · **A fraction of a cent** (metered at cost) ·
**Billed by length** (the bot confirms before running). Mark a tool you depend on but
that may be absent as `stubbed` only if it is genuinely off — never stub a **live** tool
(the lint fails a stale claim).

*Skill to compose* names the building-block skill **already delivered on your
bot's box** that operates the tool at runtime (your skill composes on top of it,
and can tell the bot to load it) — it is not a file in this repo; read it on your
dev bot if you're curious. The authoring-side browser discipline lives in
[`browser-authoring.md`](browser-authoring.md).

## The live web

| Request name | Request via | Skill to compose | Status | Cost | What it does |
|---|---|---|---|---|---|
| `web_search` | `tools.required` | oteny-web-search | live | A fraction of a cent | 🔍 Current answers from the web, with sources. |
| `web_extract` | `tools.required` | oteny-web-search | live | A fraction of a cent | 📄 Pull clean text from a URL you already have. |
| `x_search` | `tools.required` | oteny-web-search | live | A fraction of a cent | 🐦 What's happening on X, grounded in live posts. |
| `youtube_transcript` | `tools.required` | oteny-youtube-transcript | live | A fraction of a cent | 📺 Read, summarize, or monitor any YouTube video. |
| `travel` | `tools.required` | oteny-travel | live | A fraction of a cent | 🗺️ Door-to-door routes + live departure boards (in NL: real delays, platform/spoor & service alerts), places, flights & full itineraries — on Google Maps. |
| `flight_status` | `tools.required` | oteny-travel | live | A fraction of a cent | ✈️ Live flight status, gate, terminal & delay by flight number. |

## Read & understand what you send

| Request name | Request via | Skill to compose | Status | Cost | What it does |
|---|---|---|---|---|---|
| `parse_document` | `tools.required` | oteny-read-document | live | A fraction of a cent | 📄 Reads photos, screenshots & PDFs — text, tables, errors, summaries. |
| `vision_analyze` | `tools.required` | oteny-read-document | live | A fraction of a cent | 👁️ The bot's "I can see this image" sense — same engine as Read images & documents. |
| `video_analyze` | `tools.required` | oteny-analyze-video | live | Billed by length — confirms first | 🎞️ Watches a video and tells you what happens, with timestamps. |
| `transcribe_audio` | `tools.required` | — | live | A fraction of a cent | 🎤 Turns a voice note into text and acts on it. |

## Create media

| Request name | Request via | Skill to compose | Status | Cost | What it does |
|---|---|---|---|---|---|
| `image_generate` | `tools.required` | — | live | A fraction of a cent | 🎨 Generates, enhances, edits, or combines images — posters, diagrams, logos, and multi-photo merges. |
| `imagine_image` | `tools.required` | — | live | A fraction of a cent | 🖼️ Photoreal & artistic pictures, fast. |
| `text_to_speech` | `tools.required` | — | live | A fraction of a cent | 🔊 Speaks a reply as a voice note, with a choice of voices. |
| `video_generate` | `tools.required` | — | live | Billed by length — confirms first | 🎬 Makes a short AI video clip from a prompt or an image (the priciest tool). |

## Browse real websites

| Request name | Request via | Skill to compose | Status | Cost | What it does |
|---|---|---|---|---|---|
| `browser` | `toolset_contribution` | oteny-web-operator | live | A fraction of a cent | 🖥️ Drives a real cloud browser to click through pages a search can't read. |
| `browser_request_human` | `tools.required` | oteny-web-operator | live | Included | 🔐 Sends a secure live-view link so you sign in or pass a 2FA code, then carries on. |
| `browser_download` | `tools.required` | oteny-web-operator | live | A fraction of a cent | 📥 Fetches a file off a website (export, invoice, backup) and hands you a link. |
| `browser_needs_login` | `tools.required` | oteny-web-operator | live | Included | 🔑 Reports that a page needs a human sign-in so the bot ends the turn cleanly instead of stalling — the owner logs in later from a button. |

## Host a website

| Request name | Request via | Skill to compose | Status | Cost | What it does |
|---|---|---|---|---|---|
| `host_website` | `tools.required` | oteny-sites | live | Included | 🌐 Puts a web app your bot builds — a landing page, a shop, a booking page, a full site — online at your own address, served securely with no server to manage. |
| `unhost_website` | `tools.required` | oteny-sites | live | Included | 🚫 Takes a hosted website offline. |
| `list_hosted_websites` | `tools.required` | oteny-sites | live | Included | 📋 Lists the websites you have online. |
| `set_site_maintenance_page` | `tools.required` | oteny-sites | live | Included | 🚧 Sets the page visitors see while your site is briefly down for an update. |
| `attach_site_domains` | `tools.required` | oteny-sites | live | Included | 🔗 Points your own domain at a hosted website (CNAME to customers.oteny.bot; SSL automatic). |
| `detach_site_domain` | `tools.required` | oteny-sites | live | Included | 🔓 Removes a custom domain from a hosted website. |
| `list_site_domains` | `tools.required` | oteny-sites | live | Included | 📎 Lists custom domains on your hosted websites and their DNS status. |

## Share a file as a link

| Request name | Request via | Skill to compose | Status | Cost | What it does |
|---|---|---|---|---|---|
| `publish_file` | `tools.required` | oteny-drop | live | Included | 🔗 Turns any file into a clean shareable link — password & expiry optional, even gigabytes. |
| `unpublish_file` | `tools.required` | oteny-drop | live | Included | 🗑️ Takes a published link down. |
| `list_published_files` | `tools.required` | oteny-drop | live | Included | 📋 Lists what you've published. |

## Connect your accounts

| Request name | Request via | Skill to compose | Status | Cost | What it does |
|---|---|---|---|---|---|
| `connect_account` | `tools.required` | oteny-connect-credential | live | Included | 🔑 A secure one-time link to hand your bot an API key or OAuth account — never in chat. |
| `connect_login` | `tools.required` | oteny-remember-login | live | Included | 🔐 Save a website login once; your bot signs in by itself next time (2FA too). |
| `list_logins` | `tools.required` | oteny-remember-login | live | Included | 🔐 See which site logins you've saved. |
| `disconnect_login` | `tools.required` | oteny-remember-login | live | Included | 🔐 Forget a saved login. |

## Out of the box

| Request name | Request via | Skill to compose | Status | Cost | What it does |
|---|---|---|---|---|---|
| `switch_persona` | `tools.required` | — | live | Included | 🧠 Steps up to a stronger model for error-prone tasks (like verifying real listings), tells you when it does, and steps back down after. |
| `cron` | `toolset_contribution` | oteny-cron-authoring | live | Included | ⏰ Runs tasks on a schedule, in your local time. |
| `memory` | `toolset_contribution` | — | live | Included | 🧠 Remembers what matters across chats. |
| `terminal` | `toolset_contribution` | — | live | Included | 💻 Writes and runs real shell commands. |
| `execute_code` | `toolset_contribution` | — | live | Included | 🧮 Writes and runs real code (Python). |
| `skills` | `toolset_contribution` | — | live | Included | 🧩 Builds and loads its own skills and Talents. |
| `todo` | `toolset_contribution` | — | live | Included | ✅ Keeps your to-do list. |
| `send_message` | `toolset_contribution` | — | live | Included | ✉️ Sends you reminders and alerts on its own. |
