# Tool reference — the contracts behind the catalog

> **Generated** by Oteny (`python -m hermeshost tools-catalog --format reference`) —
> do not edit by hand. The [tools-catalog](tools-catalog.md) tells you WHICH tools
> exist and how to request them; this reference is the **contract**: the exact
> parameters, the result shape, the error modes, and one worked example per tool —
> written so you (and your AI coding session) can author correct tool calls without
> ever reading platform source or a live box. The description under each tool is the
> SAME text your bot sees at runtime, so what you write in a skill and what the bot
> experiences never diverge.

**How to read an entry.** *Request via* is where the name goes in your
`agent-profile.yaml` (`tools.required` for a first-party tool, `toolset_contribution`
for a built-in toolset). *Parameters* is the JSON schema your bot's tool call must
satisfy. *Result* / *Errors* are what comes back. The example is a real call.

Your bot's **system-of-record seam** (e.g. an Odoo `/json/2/` uplink tool) is declared
by YOUR Talent, not listed here — see `business-bot-pattern.md` §3. For the
browser-driving discipline (selector maps, batching, fail-closed), read
[`browser-authoring.md`](browser-authoring.md) next to this file.

## The live web

### `web_search` — Web search

*first-party tool · request via `tools.required` · status **live** · cost A fraction of a cent*

> Search the web for current, real-world information and get a grounded answer with a Sources list. Use this for anything time-sensitive or factual you can't answer from memory (news, prices, schedules, 'latest X'). Prefer this over improvising a curl scrape — it is grounded and cited.

**Parameters**

```json
{
  "type": "object",
  "properties": {
    "query": {
      "type": "string",
      "description": "What to search for."
    }
  },
  "required": [
    "query"
  ]
}
```

**Result** — {text} — a grounded answer with a deduped 'Sources:' footer folded into the text ('…answer…\n\nSources:\n- <Title>: <url>'). Single key.

**Errors / edges** — {error:'query is required'} on an empty query. Plus the shared platform set: {error:'out_of_credits', message} → the owner tops up with /oteny_topup; {error:'tool temporarily unavailable'} → transient, retry once later; {error:'tool error (status N)'} → report, don't loop.

**Example**

```json
{
  "query": "ECB deposit rate today"
}
```

→

```json
{
  "text": "The ECB deposit facility rate is 2.00% \u2026\n\nSources:\n- ECB key interest rates: https://www.ecb.europa.eu/\u2026"
}
```

**Authoring notes** — Grounded + cited — prefer it over improvising a curl scrape for anything time-sensitive or factual. Flat price per query.

### `x_search` — X (Twitter) search

*first-party tool · request via `tools.required` · status **live** · cost A fraction of a cent*

> Search X (Twitter) for live posts and get a grounded answer with sources. A strong source for real-time and breaking news — general AND specialized — plus trending topics and what a specific @handle is posting. Pass the user's topic, question, or @handle as a non-empty `query`. Complements `web_search`: either works for news, so use whichever fits (or both). Use `web_search` instead for marketplace, shopping or auction LISTINGS and item prices (eBay, Marktplaats, …) — X can't browse those.

**Parameters**

```json
{
  "type": "object",
  "properties": {
    "query": {
      "type": "string",
      "description": "What to look up on X — a handle (e.g. @NousResearch), a topic, or a question."
    }
  },
  "required": [
    "query"
  ]
}
```

**Result** — {text} — a grounded answer with url citations folded in as a 'Sources:' footer. Single key.

**Errors / edges** — Empty query → {error:'query is required', message} (use an @handle or topic; do NOT retry empty; non-X web/news/marketplace searches go to web_search). Plus the shared platform set.

**Example**

```json
{
  "query": "what is @NousResearch posting this week"
}
```

→

```json
{
  "text": "NousResearch announced \u2026\n\nSources:\n- https://x.com/NousResearch/status/\u2026"
}
```

**Authoring notes** — Only `query` is honored — put handles, date hints, and operators IN the query text (extra args are ignored). Strong for real-time/breaking news and what a specific @handle posts; flat price per call.

### `youtube_transcript` — YouTube transcripts

*first-party tool · request via `tools.required` · status **live** · cost A fraction of a cent*

> Fetch the transcript of a specific YouTube video (and optionally summarize or answer a question about it). Use whenever the user shares a YouTube link or asks you to watch / summarize / monitor a video or channel — a web search can't read the video's audio. Pass the video URL or id as `url`.

**Parameters**

```json
{
  "type": "object",
  "properties": {
    "url": {
      "type": "string",
      "description": "A YouTube video URL or video id."
    },
    "prompt": {
      "type": "string",
      "description": "Optional focus, e.g. 'summarize the key points' or a question."
    }
  },
  "required": [
    "url"
  ]
}
```

**Result** — {transcript, title?} — the FULL raw transcript ('(transcript empty)' when the video has none usable).

**Errors / edges** — {error:'no transcript found for that video'} · a provider failure surfaces as {error:'tool call failed'}. Plus the shared platform set.

**Example**

```json
{
  "url": "https://www.youtube.com/watch?v=abc123",
  "prompt": "key points"
}
```

→

```json
{
  "transcript": "welcome back everyone, today we're looking at \u2026",
  "title": "Q2 earnings breakdown"
}
```

**Authoring notes** — `prompt` is NOT applied server-side — you always get the raw transcript back; summarize/answer yourself after it returns. A bare video id works as `url`. Flat price per video.

### `travel` — Travel, transport & places

*first-party tool · request via `tools.required` · status **live** · cost A fraction of a cent*

> Travel, transport & places — real door-to-door routing from Google Maps (real stops, lines & times) with a tappable Google Maps link on every answer. Handles: driving distance + time; public transport & trains (`transit` — routes, transfers, the next departure); `departures` (the next transit departure on a route); place lookup (name → address, rating, open-now); resolving a pasted Google Maps link to an exact spot (`resolve_url`); flights / multi-step itineraries / journeys (`plan`). Structured `action`s — `place_lookup`, `distance`, `transit`, `departures` — take plain place NAMES as `origin`/`destination` (or `query` for a single place); flights (options, times, status & delays) and multi-step itinerary / journey planning (`action: plan` — put the full natural-language question in `query`). No place-ids needed. **When the user pastes a Google Maps link (`maps.app.goo.gl/…`, `maps.google.com/…`, a 'share my location'/dropped-pin link) — e.g. 'I'm here, how do I get home' — call `action: resolve_url` with the link in `url` FIRST to get the EXACT coordinates, then use the returned `latlng` as `origin`. NEVER guess the place from the link's text/slug — that lands kilometres off.** Use this (not `web_search`) for anything about getting somewhere. Don't re-resolve a place or re-request a route you already looked up this conversation — reuse the earlier result (results are cached, so a re-ask wastes a turn). Set `static_map: true` to ALSO return an in-chat image of the route (a real Google map) when the user wants to SEE one — the tappable map link is always included regardless.

**Parameters**

```json
{
  "type": "object",
  "properties": {
    "action": {
      "type": "string",
      "enum": [
        "place_lookup",
        "distance",
        "transit",
        "departures",
        "resolve_url",
        "plan"
      ],
      "description": "Travel operation: `place_lookup`, `distance`, `transit`, `departures` (next transit departure on a route), `resolve_url` (turn a pasted Google Maps link into exact coordinates — pass the link in `url`), or `plan` for flights / itineraries / journeys / any free-form travel question (put it in `query`)."
    },
    "url": {
      "type": "string",
      "description": "For `resolve_url`: the Google Maps link the user pasted (maps.app.goo.gl/…, maps.google.com/…, a shared-location pin). Resolved server-side to exact coordinates + a named address."
    },
    "query": {
      "type": "string",
      "description": "A single place name (place_lookup), OR the full natural-language travel question for `plan` (e.g. 'flights Amsterdam→JFK next Tuesday with current delays', 'plan a 3-day Rome itinerary')."
    },
    "origin": {
      "type": "string",
      "description": "Origin place name (distance/transit)."
    },
    "destination": {
      "type": "string",
      "description": "Destination place name (distance/transit)."
    },
    "static_map": {
      "type": "boolean",
      "description": "Set true to ALSO return an in-chat image of the route (a real Google Static Map). Use only when the user wants to SEE a map; the tappable Google Maps deeplink is always included anyway."
    }
  },
  "required": [
    "action"
  ]
}
```

**Result** — `text` is always present; route/place actions add {deeplink, source, as_of} (transit also nl_overlay); resolve_url adds {lat, lng, latlng, address, place_id}; plan adds {grounded, n_sources}. With static_map:true the result also carries media:'MEDIA:<path>' — a route map image; relay that token in your reply to deliver it.

**Errors / edges** — {error:'origin and destination are required'} · {error:'a place name is required'} · resolve_url without a Google Maps link → {error, fallback_hint}. A provider failure never raises: you get {text:"I couldn't reach …", deeplink, error, fallback_hint} — obey the fallback_hint (share the deeplink; do NOT retry with variations). Plus the shared platform set.

**Example**

```json
{
  "action": "transit",
  "origin": "Rotterdam Centraal",
  "destination": "Duisburg Hbf"
}
```

→

```json
{
  "text": "Leave 14:25: ICE 123 direct, arrives 16:12 \u2026",
  "deeplink": "https://www.google.com/maps/dir/\u2026",
  "source": "google_routes",
  "as_of": "2026-07-12T09:00Z"
}
```

**Authoring notes** — One tool, six actions (place_lookup · distance · transit · departures · resolve_url · plan). ALWAYS relay the deeplink — every answer carries a tappable map link. Repeat lookups within minutes are cached (free).

### `flight_status` — Flight status & gate

*first-party tool · request via `tools.required` · status **live** · cost A fraction of a cent*

> Live flight STATUS by flight number — real scheduled vs actual times (delay), status (expected/boarding/departed/arrived/cancelled), terminal, gate, and route. Structured data from an aviation feed, NOT a web guess. **Use this — never `web_search` or `travel plan` — for a flight's status/gate/delay/cancellation** (those invent gates and numbers). Pass the flight number in `flight` (e.g. 'KL1001', 'BA430'). If a flight isn't found or the feed is down, it says so and gives a Google Flights link — never guess a gate/status.

**Parameters**

```json
{
  "type": "object",
  "properties": {
    "flight": {
      "type": "string",
      "description": "The flight number (IATA or ICAO, with or without a space), e.g. 'KL1001', 'BA 430', 'AF1640'."
    }
  },
  "required": [
    "flight"
  ]
}
```

**Result** — Found: {flight, status, cancelled, dep_airport, arr_airport, dep_scheduled, dep_estimated, arr_scheduled, arr_estimated, dep_terminal, dep_gate, arr_terminal, arr_gate, delay_min, distance_km, text, deeplink, found:true} — `text` is ready to relay. Not found: {text, deeplink, found:false, fallback_hint}.

**Errors / edges** — {error:'a flight number is required (e.g. KL1001)', fallback_hint} · a provider failure → {text:"I couldn't reach live flight status…", deeplink, error, fallback_hint} — share the deeplink, don't retry variations. Plus the shared platform set.

**Example**

```json
{
  "flight": "KL1001"
}
```

→

```json
{
  "flight": "KL1001",
  "status": "departed",
  "delay_min": 12,
  "dep_airport": "AMS",
  "arr_airport": "LHR",
  "text": "KL1001 departed AMS 09:12 (+12 min), arriving LHR ~09:35 \u2026",
  "deeplink": "https://www.google.com/travel/flights?q=KL1001",
  "found": true
}
```

**Authoring notes** — Structured live data from an aviation feed, not a web guess. Results are briefly cached; a not-found lookup is not charged.

## Read & understand what you send

### `parse_document` — Read images & documents

*first-party tool · request via `tools.required` · status **live** · cost A fraction of a cent*

> Understand an IMAGE or a PDF: extract/transcribe text, read tables, describe a photo or screenshot, or answer a question about a document. Pass a local file path, an http(s) URL, or a data: URL as `source`, and an optional `prompt` to focus the read (e.g. 'just the totals table', 'what does this error say?'). Handles multi-page PDFs and images uniformly.

**Parameters**

```json
{
  "type": "object",
  "properties": {
    "source": {
      "type": "string",
      "description": "Local path, http(s) URL, or data: URL of the image/PDF."
    },
    "prompt": {
      "type": "string",
      "description": "Optional focus for the extraction/answer."
    }
  },
  "required": [
    "source"
  ]
}
```

**Result** — {text} — the extraction/answer, single key. Without a `prompt` it extracts/transcribes and summarizes, preserving tables as markdown.

**Errors / edges** — {error:'source is required'} · {error:'source is not valid base64'} · a size cap: {error:'document exceeds N MB limit'} → pass an http(s) link instead of a local file. Plus the shared platform set.

**Example**

```json
{
  "source": "/home/user/invoice.pdf",
  "prompt": "just the totals table"
}
```

→

```json
{
  "text": "| Item | Total |\n| Hosting | \u20ac12.50 |\n\u2026"
}
```

**Authoring notes** — IMAGE or PDF; `source` takes a local path, an http(s) URL, or a data: URL (local files are encoded for you). Metered by document size — cost scales with pages.

### `vision_analyze` — See an image

*first-party tool · request via `tools.required` · status **live** · cost A fraction of a cent*

> Read an image or document so you can see/understand it. Accepts a URL, a local file path, or a data URL. Works on any model — the image is understood by a dedicated perception engine and the result comes back as text. Call this any time the user references an image, screenshot, or PDF.

**Parameters**

```json
{
  "type": "object",
  "properties": {
    "image_url": {
      "type": "string",
      "description": "Image URL (http/https), local file path, or data: URL to read."
    },
    "question": {
      "type": "string",
      "description": "Optional question about the image/document."
    }
  },
  "required": [
    "image_url"
  ]
}
```

**Result** — {text} — what the image/document shows, or the answer to `question`. Same engine and contract as parse_document (image_url→source, question→prompt).

**Errors / edges** — Identical to parse_document: source required / not valid base64 / the MB size cap. Plus the shared platform set.

**Example**

```json
{
  "image_url": "https://example.com/screenshot.png",
  "question": "what does this error say?"
}
```

→

```json
{
  "text": "The dialog reports 'disk full \u2014 free 2 GB and retry'."
}
```

**Authoring notes** — Call whenever the user references an image, screenshot, or PDF — the image is understood by a dedicated perception engine and the result comes back as text, on any model.

### `video_analyze` — Understand a video

*first-party tool · request via `tools.required` · status **live** · cost Billed by length — confirms first*

> Watch and understand a VIDEO: describe what happens, the actions and their timestamps, and answer a question about it. Use this for video files or links (for a still image or PDF use parse_document instead). Pass the video's local path, an http(s) link, or a YouTube link as `video_url`, and what you want to know as `question`. Optional: `detail`='detailed' for fine cues (costs more), `fps` below 1 (e.g. 0.25) for long/slow footage to save cost, `clip` to look at only part of a long video. This is a paid tool billed by video length — for a long clip, confirm with the user first. It DESCRIBES observable behaviour with evidence; it does not diagnose.

**Parameters**

```json
{
  "type": "object",
  "properties": {
    "video_url": {
      "type": "string",
      "description": "Local path, http(s) URL, file:// URL, or YouTube URL of the video."
    },
    "question": {
      "type": "string",
      "description": "What you want to know about the video."
    },
    "detail": {
      "type": "string",
      "enum": [
        "overview",
        "detailed"
      ],
      "description": "overview = cheaper low-res (default); detailed = high-res for fine cues (costs more)."
    },
    "fps": {
      "type": "number",
      "description": "Frames sampled per second (default 1). Use below 1 (e.g. 0.25) for long, mostly-static footage to save cost."
    },
    "clip": {
      "type": "object",
      "properties": {
        "start": {
          "type": "number"
        },
        "end": {
          "type": "number"
        }
      },
      "description": "Optional second offsets to analyse only part of a long video."
    }
  },
  "required": [
    "video_url",
    "question"
  ]
}
```

**Result** — {text} — what happens in the video, actions with timestamps, or the answer to `question`.

**Errors / edges** — {error:'video_url is required'} · a size cap: {error:'video exceeds N MB limit; share an http(s) link for a longer/larger video'} · a processing failure surfaces as {error:'tool call failed'}. Plus the shared platform set.

**Example**

```json
{
  "video_url": "https://youtu.be/abc123",
  "question": "what product is demonstrated and when?",
  "detail": "overview"
}
```

→

```json
{
  "text": "0:00\u20130:40 unboxing; 0:40\u20132:10 the vendor demonstrates \u2026"
}
```

**Authoring notes** — Billed by video length — confirm with the user before long clips. Cost levers: detail:'overview' (default), fps below 1 (e.g. 0.25) for mostly-static footage, clip:{start,end} to analyse only a segment. One long call — it can take minutes.

### `transcribe_audio` — Understand a voice note

*first-party tool · request via `tools.required` · status **live** · cost A fraction of a cent*

> Transcribe a voice note or audio file to text (speech→text). Use whenever the user sends a voice message or audio file, or asks you to transcribe/understand spoken audio. Pass the audio as `source` (a local file path, an http(s) URL, or a data: URL). Returns the transcript text. Do NOT use this to SPEAK text — that is `text_to_speech`.

**Parameters**

```json
{
  "type": "object",
  "properties": {
    "source": {
      "type": "string",
      "description": "Audio file: local path, http(s) URL, or data: URL (e.g. a voice note)."
    },
    "language": {
      "type": "string",
      "description": "Optional language hint, e.g. 'en'."
    }
  },
  "required": [
    "source"
  ]
}
```

**Result** — {text, language?} — the transcript; `language` only when the provider reports it. Text-only (no file is produced).

**Errors / edges** — {error:'source is required'} · {error:'source is not valid base64 audio'} · a size cap: {error:'audio exceeds N MB limit', bytes}. Plus the shared platform set.

**Example**

```json
{
  "source": "/home/user/voice-note.ogg"
}
```

→

```json
{
  "text": "Hoi, kun je de afspraak naar dinsdag verzetten?",
  "language": "nl"
}
```

**Authoring notes** — Speech→text (a voice note, a recording). To SPEAK text use text_to_speech. Priced per minute of audio.

## Create media

### `image_generate` — Generate & edit images

*first-party tool · request via `tools.required` · status **live** · cost A fraction of a cent*

> Generate (or EDIT) an image and deliver it to the user as a native photo. Best for images that need ACCURATE PROMPT-FOLLOWING or READABLE TEXT — posters, infographics, diagrams, signs, UI mockups, logos with words — or for editing/refining an image the user shared (pass `source`). Backed by Gemini Nano Banana. DEFAULT to `quality:"standard"` (fast, cheap — a few cents). Escalate to `quality:"high"` (Nano Banana Pro) only for complex text/typography or precise edits, and 2K/4K only when needed — those cost noticeably more, so tell the user the higher cost and get a yes first. For a photorealistic or artistic picture with no important text, prefer `imagine_image`. Do NOT use this to ANALYZE an image — that is `vision_analyze`. Never shell out to an image CLI; this is the metered, delivered image path.

**Parameters**

```json
{
  "type": "object",
  "properties": {
    "prompt": {
      "type": "string",
      "description": "What to draw/generate. Be specific: subject, style, composition, colors, mood, and any exact text to render."
    },
    "quality": {
      "type": "string",
      "enum": [
        "standard",
        "high"
      ],
      "description": "standard = fast/cheap (default). high = Nano Banana Pro for text-heavy images or precise edits; costs more — confirm with the user first."
    },
    "image_size": {
      "type": "string",
      "enum": [
        "1K",
        "2K",
        "4K"
      ],
      "description": "Output resolution. 1K (default) suits chat/social; 2K/4K cost more — confirm first."
    },
    "aspect_ratio": {
      "type": "string",
      "description": "e.g. '1:1', '16:9', '9:16', '4:3', '3:4'. Default '1:1'."
    },
    "source": {
      "type": "string",
      "description": "Optional input image to EDIT (local path, http(s) URL, or data: URL)."
    }
  },
  "required": [
    "prompt"
  ]
}
```

**Result** — {success: true, image: '<abs path>', text: '<caption>'} — the photo is delivered to the user AUTOMATICALLY; never paste the path into your reply.

**Errors / edges** — {error:'image_blocked', reason, message} → rephrase; do NOT retry the identical prompt. {error:'prompt is required'}. Editing: {error:'source is not valid base64'} · {error:'input image exceeds N MB limit'}. Plus the shared platform set.

**Example**

```json
{
  "prompt": "poster reading 'GRAND OPENING SATURDAY' in bold art-deco lettering, teal and gold",
  "aspect_ratio": "3:4"
}
```

→

```json
{
  "success": true,
  "image": "/home/user/.hermes/media/img_0012.png",
  "text": "Here's the image."
}
```

**Authoring notes** — Best for ACCURATE PROMPT-FOLLOWING and READABLE TEXT (posters, diagrams, logos) and for EDITING a shared image (pass `source`). quality:'high' costs more — confirm first. Fast photoreal/stylized → imagine_image.

### `imagine_image` — Photoreal & artistic images

*first-party tool · request via `tools.required` · status **live** · cost A fraction of a cent*

> Generate a PHOTOREALISTIC or ARTISTIC/stylized image FAST and deliver it to the user. Best for lifelike photos, creative illustration, scenes, characters, product/lifestyle shots, and 'imagine this' visuals where vivid realism or style matters more than embedded text. Backed by xAI Grok Imagine. Use `image_generate` instead when the image must contain accurate TEXT/labels/diagrams or you need to EDIT an existing image. Never shell out to an image CLI; this is a metered, delivered image path.

**Parameters**

```json
{
  "type": "object",
  "properties": {
    "prompt": {
      "type": "string",
      "description": "What to imagine. Describe the subject, style, lighting, mood, and composition."
    },
    "resolution": {
      "type": "string",
      "enum": [
        "1k",
        "2k"
      ],
      "description": "Output resolution. 1k (default) suits chat; 2k costs a little more."
    },
    "aspect_ratio": {
      "type": "string",
      "description": "e.g. '1:1', '16:9', '9:16', '4:3'. Default '1:1'."
    }
  },
  "required": [
    "prompt"
  ]
}
```

**Result** — {success: true, media: 'MEDIA:<abs path>', text: '<caption>'} — NOT auto-delivered: you MUST relay the MEDIA:<path> token in your reply for the image to reach the user.

**Errors / edges** — {error:'image_failed', message} → rephrase; do NOT retry the identical prompt. {error:'prompt is required'}. Plus the shared platform set.

**Example**

```json
{
  "prompt": "golden-hour photo of a Dutch fishing village, cinematic, 35mm",
  "resolution": "1k",
  "aspect_ratio": "16:9"
}
```

→

```json
{
  "success": true,
  "media": "MEDIA:/home/user/.hermes/media/img_0034.jpg",
  "text": "A warm golden-hour harbor scene."
}
```

**Authoring notes** — FAST photorealistic/artistic generation. Needs readable embedded text or an edit of an existing image → image_generate instead. Flat price per image by resolution.

### `text_to_speech` — Spoken replies (voice)

*first-party tool · request via `tools.required` · status **live** · cost A fraction of a cent*

> Speak text aloud and deliver it to the user as a voice/audio note (text→speech). Use when the user asks you to 'say', 'read aloud', 'send a voice note', or narrate something, or wants audio instead of text. Pass the `text` to speak and optionally a `voice` (eve, ara, rex, sal, leo). Keep it reasonably short; it is billed per character. Do NOT use this to TRANSCRIBE audio — that is `transcribe_audio`.

**Parameters**

```json
{
  "type": "object",
  "properties": {
    "text": {
      "type": "string",
      "description": "The text to speak aloud."
    },
    "voice": {
      "type": "string",
      "enum": [
        "eve",
        "ara",
        "rex",
        "sal",
        "leo"
      ],
      "description": "Voice to use (default eve)."
    },
    "language": {
      "type": "string",
      "description": "Language code, e.g. 'en' (default)."
    }
  },
  "required": [
    "text"
  ]
}
```

**Result** — {success: true, media: 'MEDIA:<abs path>', text: "Here's the audio."} — delivered to the user automatically as a voice/audio note (ogg/opus arrives as a voice bubble).

**Errors / edges** — A length cap: {error:'text exceeds N characters — shorten it or split into multiple calls.', chars} · {error:'tts_failed', message: 'No audio returned.'} · {error:'text is required'}. Plus the shared platform set.

**Example**

```json
{
  "text": "Goedemorgen! Je afspraak is om tien uur.",
  "voice": "eve",
  "language": "nl"
}
```

→

```json
{
  "success": true,
  "media": "MEDIA:/home/user/.hermes/media/tts_0007.ogg",
  "text": "Here's the audio."
}
```

**Authoring notes** — Billed per character — keep it short; narrate at length only when asked. The reverse (speech→text) is transcribe_audio.

### `video_generate` — Short AI videos

*first-party tool · request via `tools.required` · status **live** · cost Billed by length — confirms first*

> Generate a SHORT AI VIDEO CLIP from a text prompt (or animate an `image`) and deliver it to the user. Use when the user asks you to make/generate a video, animation, or short clip. Clips are a few seconds (default 5s, max 10s) at 480p (default) or 720p. Video is the MOST EXPENSIVE tool — it costs per second and a clip is many times the price of an image — so confirm with the user before generating, keep clips short, and use 480p unless they ask for 720p. Generation takes up to a few minutes.

**Parameters**

```json
{
  "type": "object",
  "properties": {
    "prompt": {
      "type": "string",
      "description": "What the video should show (motion, subject, scene). Required unless `image` is given."
    },
    "image": {
      "type": "string",
      "description": "Optional input image to animate (local path, http(s) URL, or data: URL) — image→video."
    },
    "duration": {
      "type": "integer",
      "description": "Clip length in seconds (default 5, max 10)."
    },
    "resolution": {
      "type": "string",
      "enum": [
        "480p",
        "720p"
      ],
      "description": "480p (default, cheaper) or 720p (costs more)."
    },
    "aspect_ratio": {
      "type": "string",
      "description": "e.g. '16:9' (default), '9:16', '1:1'."
    }
  },
  "required": [
    "prompt"
  ]
}
```

**Result** — {success: true, media: 'MEDIA:<abs path>.mp4', text: "Here's the video."} — relay the MEDIA: token in your reply to deliver the clip.

**Errors / edges** — {error:'video_failed', reason?, message} → rephrase; do NOT immediately retry the identical request. {error:'video_timeout', message, request_id} → try a shorter clip or 480p. {error:'prompt is required'} (unless `image` is given). A failure/timeout is NOT charged. Plus the shared platform set.

**Example**

```json
{
  "prompt": "a paper boat drifting down a rain-soaked street, cinematic",
  "duration": 5,
  "resolution": "480p"
}
```

→

```json
{
  "success": true,
  "media": "MEDIA:/home/user/.hermes/media/vid_0002.mp4",
  "text": "Here's the video."
}
```

**Authoring notes** — The PRICIEST tool — billed per second × resolution; CONFIRM with the user before generating. Pass `image` to animate a still (image→video). One long call, up to a few minutes; clips max 10 s.

## Browse real websites

### `browser` — Browse real websites

*built-in toolset · request via `toolset_contribution` · status **live** · cost A fraction of a cent*

**Result** — Each native tool returns JSON with `success` plus its payload (a snapshot text, a click/type acknowledgment). Snapshots identify elements as `[ref=eN]` accessibility refs with roles and visible labels.

**Errors / edges** — A blocked/errored navigation, a timeout, or an 'unstable session' notice means the page is not usable — fail closed per your skill's rules rather than retrying past a second identical error.

**Authoring notes** — The toolset's per-tool surface:

- `browser_navigate(url)` — Open a page. Returns the result plus a compact snapshot.
- `browser_snapshot(full?)` — The page as an accessibility tree. Elements carry `[ref=eN]` reference ids with roles + visible labels — **never CSS ids/classes**.
- `browser_click(ref)` — Click the element with that snapshot ref (e.g. '@e5').
- `browser_type(ref, text)` — Clear the field with that ref, then type `text`.
- `browser_press(key)` — Press a key ('Enter', 'Tab', 'Escape', 'ArrowDown').
- `browser_scroll(direction)` — Scroll 'up' or 'down'.
- `browser_back()` — Browser history back.
- `browser_get_images()` — List the images on the page.
- `browser_vision(question, annotate?)` — Ask a vision model about a screenshot — the SLOWEST browser tool; reserve it for what the DOM genuinely can't tell you.
- `browser_console(clear?, expression?)` — Read console messages / evaluate a JS expression. The safety policy BLOCKS reading form values, cookies, storage, and network primitives from JS — verify form state via snapshots or browser_fill_form's readback, never via JS.

Your bot also carries the delivered `oteny-web-operator` skill (visible on the box) with the operating discipline; the authoring-side counterpart is `browser-authoring.md` in this directory.

### `browser_request_human` — Hand the browser to you

*first-party tool · request via `tools.required` · status **live** · cost Included*

> Hand the live browser to the human owner for a step only a person can do — a real login, two-factor/2FA code, or a captcha the cloud browser could not auto-solve. Sends the owner a secure live-view link in Telegram and pauses; you then resume on the SAME browser session once they reply. Use this ONLY after trying yourself: captchas are auto-solved by the cloud browser, so retry first and reserve handoff for genuine logins/2FA. Logins PERSIST across turns and days (a per-tenant browser profile plus the session is reused between your messages), so before asking for a handoff, navigate to the site and check whether you are ALREADY signed in from an earlier session — only hand off if you actually hit a login or 2FA wall. Bandwidth note: the cloud browser bills by proxy GB (the dominant cost), so for text/DOM-only work block images/media/fonts via browser_cdp (request interception). Prefer web_search/web_extract or curl for plain fetches — the browser is for interaction, not retrieval. If the user wants you to remember this login for next time, offer `connect_login` (a secure link to save it) instead of a fresh handoff each visit.

**Parameters**

```json
{
  "type": "object",
  "properties": {
    "reason": {
      "type": "string",
      "description": "Short reason for the handoff, shown to the owner (e.g. 'to log in to your bank', 'to enter the 2FA code')."
    }
  },
  "required": []
}
```

**Result** — {status:'sent', message} — the owner received a secure live-view link; end your turn and continue when they reply 'done' (the SAME browser session resumes, logged in).

**Errors / edges** — {status:'no_session'} → open the site with browser_navigate first. {status:'no_channel', message with the link} → the owner could not be messaged; relay the link in your reply.

**Example**

```json
{
  "reason": "to enter the 2FA code"
}
```

→

```json
{
  "status": "sent",
  "message": "I've sent you a secure live-view link\u2026 reply 'done' and I'll continue on the same page."
}
```

**Authoring notes** — Hand off ONCE per login wall, then wait — never loop sign-in. Logins persist across sessions and days; check whether you are already signed in before asking. For a recurring login, steer the owner to connect_login instead (stored securely, auto-signs-in every visit).

### `browser_download` — Download a file off a site

*first-party tool · request via `tools.required` · status **live** · cost A fraction of a cent*

> Save a file the cloud browser just downloaded (a database dump, PDF, CSV, spreadsheet, image, or zip) and get a public share link. The browser is REMOTE, so the file is NOT on this machine — you can't find it in a folder, `ls ~/Downloads`, or `curl` it. This retrieves it from the browser and returns an Oteny Drop link (big files stream straight to storage and expire in a few days). Call it right after the download finishes. Omit `path` to list/auto-pick the downloaded file; pass `path` to choose when several were downloaded. For a plain web page or an API response, use `curl` instead — this is only for files the browser itself downloaded.

**Parameters**

```json
{
  "type": "object",
  "properties": {
    "path": {
      "type": "string",
      "description": "Which downloaded file to save, when several exist (the filename from the listing). Omit to auto-pick a single download or list them."
    }
  },
  "required": []
}
```

**Result** — {ok: true, url, name, size, expires_at?} — the file the REMOTE cloud browser downloaded, republished as a share link. With several downloads: {ok, files: [{path, size}], message} → call again with `path`.

**Errors / edges** — {ok:false, files:[], message} → the download hasn't finished; retry. {status:'capped'} → the owner must top up. A large file returns {ok:false, status:'transferring', message} → poll by calling again in ~20s; do NOT re-trigger the download.

**Example**

```json
{
  "path": "export.csv"
}
```

→

```json
{
  "ok": true,
  "url": "https://drop.example/abc/export.csv"
}
```

**Authoring notes** — The browser is REMOTE: a downloaded file is NOT on the bot's machine — never look in ~/Downloads or curl the portal. Trigger the download in the browser, then call this.

### `browser_fill_form` — Fill a whole form at once

*first-party tool · request via `tools.required` · status **live** · cost A fraction of a cent*

> Fill a whole form page in ONE call instead of one field per step. Pass steps=[{selector|label, value, kind?}]: text inputs are filled, native dropdowns selected (by option value or visible label), checkboxes/radios checked — all through the real browser engine with human-like waiting, so it works on dynamic pages where raw JS does not. Every field's value is read BACK and returned (ok/actual per field), so you verify the page in the same call — no extra snapshot needed for the fields themselves. Optionally pass submit_selector (the page's next/continue button): it is clicked ONLY when every field verified, in the same call — so nothing can reset a field between filling and navigating. A submitted call also returns page_digest (headings/labels/buttons of the page you landed on): with the returned title it is usually enough to pick and fill the NEXT page directly (label= steps work straight from its labels) — no snapshot round-trip first. Targeting: selector takes CSS (input#city, input[name=group][value=Yes]) or Playwright selectors; or use label='visible field label' instead. kind is auto-detected for native controls; for a custom widget (a dropdown that is not a real <select>), use explicit kind:'click' steps — click the trigger, then click the option. RULES: batch only INDEPENDENT fields whose values you already hold; never batch across a server response (a search that populates fields stays step-by-step); never use submit_selector for a final/irreversible submission — for those take a fresh snapshot and click explicitly. If this tool reports unavailable, fall back to per-field browser_type/browser_click.

**Parameters**

```json
{
  "type": "object",
  "properties": {
    "steps": {
      "type": "array",
      "description": "The fields to set, in order. Each step: {selector: CSS/Playwright selector} OR {label: visible label}, plus value, plus optional kind (fill|select|check|uncheck|click|press; default auto).",
      "items": {
        "type": "object",
        "properties": {
          "selector": {
            "type": "string"
          },
          "label": {
            "type": "string"
          },
          "value": {
            "type": [
              "string",
              "boolean",
              "null"
            ]
          },
          "kind": {
            "type": "string",
            "enum": [
              "auto",
              "fill",
              "select",
              "check",
              "uncheck",
              "click",
              "press"
            ]
          }
        }
      }
    },
    "submit_selector": {
      "type": "string",
      "description": "Next/continue button to click AFTER every field verifies (never a final submission)."
    },
    "frame_selector": {
      "type": "string",
      "description": "Optional iframe selector when the form lives inside an iframe."
    }
  },
  "required": [
    "steps"
  ]
}
```

**Result** — {ok, results: [{target, kind, ok, requested, actual, error}], submitted, submit_skipped, url, title, page_digest, message}. Every field is read BACK after filling — in one fused end-of-batch readback, so `actual` is the page's FINAL state (a later step that reset an earlier field is caught) — and `ok` is the per-field verify. Readback shapes per kind: fill → the field's text; select → {value, label} of the selected option; check/uncheck (checkboxes AND radios) → the checked-state boolean; click/press → no readback (ok = the action landed). `submitted` is true only when submit_selector was clicked (which happens ONLY when every field verified). A submitted call also carries `page_digest` ({headings, labels, buttons} of the page you landed on) — with `title`, usually enough to decide and target the NEXT page (label= steps work straight from its labels) without a snapshot round-trip first.

**Errors / edges** — {status:'no_session'} → navigate first. {status:'unavailable'} → fill per-field with browser_type/browser_click instead. {status:'bad_request', message} → fix the step shape. A per-field error row (ok:false, error) → fix and re-verify that field before moving on; the submit was NOT clicked.

**Example**

```json
{
  "steps": [
    {
      "selector": "#show_filter",
      "value": "false"
    },
    {
      "selector": "#first_name",
      "value": "Ada"
    },
    {
      "selector": "#country",
      "value": "Portugal",
      "kind": "select"
    },
    {
      "selector": "input[name=consent][value=Yes]",
      "kind": "check"
    },
    {
      "label": "Date of birth (dd-mm-yyyy)",
      "value": "01-02-1990"
    }
  ],
  "submit_selector": "button[type=submit]"
}
```

→

```json
{
  "ok": true,
  "results": [
    {
      "target": "#first_name",
      "kind": "fill",
      "ok": true,
      "requested": "Ada",
      "actual": "Ada",
      "error": null
    },
    "\u2026 one row per step \u2026"
  ],
  "submitted": true,
  "submit_skipped": null,
  "url": "https://portal.example/step2",
  "title": "Step 2",
  "page_digest": {
    "headings": [
      "Step 2 \u2014 Employer"
    ],
    "labels": [
      "Company name",
      "Registration number"
    ],
    "buttons": [
      "Previous",
      "Next"
    ]
  },
  "message": "5/5 fields verified, page submitted"
}
```

**Authoring notes** — One call per FORM PAGE. Steps run in order (sequence unlock-then-set interactions, e.g. uncheck a filter checkbox before selecting the option it hides). Selectors are CSS or Playwright selectors; `label=` targets the visible field label (what snapshots show). Ship your portal's selector map in your skill's `references/` — snapshots expose refs and labels, never CSS ids, so derive the map from your portal's DOM in your own browser devtools. `kind` is auto-detected for native controls; a checkbox accepts either {selector, value: 'false'/'true'} (kind auto) or an explicit kind:'uncheck'/'check' with value omitted — both canonical, pick one; a radio is a check on the option (input[name=g][value=X]). Drive a custom widget (a dropdown that is not a real <select>) with explicit kind:'click' steps. NEVER batch across a server round-trip (a search that populates fields), and NEVER use submit_selector for an irreversible/final submission — take a fresh snapshot and click that explicitly. Full discipline: business-bot-pattern.md §6 and browser-authoring.md.

## Host a website

### `host_website` — Host a website

*first-party tool · request via `tools.required` · status **live** · cost Included*

> Put a web app you're running INSIDE this box on the public internet at https://<name>.oteny.bot — a landing page, a small shop, a booking page, or a full site (e.g. Odoo-in-a-box). Use this when the user asks you to 'put it online', 'host my website', or 'make it public'. FIRST start the app so it listens on 0.0.0.0:<port> (NOT 127.0.0.1, or the tunnel can't reach it), pick a free port in 1024–65535 (never 2222), then call this with that `local_port`. Pass an optional `site_slug` for the subdomain (3–30 chars, lowercase letters/digits/hyphens; defaults to your bot's id). The site is PUBLIC to anyone with the link, served over our brand-quarantined oteny.bot domain — CONFIRM with the owner before the first publish. Pass an optional `ensure_cmd` (a shell command that (re)starts your app) so we can auto-restart it if it goes down. Returns the public `url` and a `status` (provisioning → active within a minute). After hosting, ALWAYS give the URL back to the user. Use `unhost_website` to take it down, `list_hosted_websites` to see what's live.

**Parameters**

```json
{
  "type": "object",
  "properties": {
    "local_port": {
      "type": "integer",
      "description": "The port your app listens on inside the box, 1024–65535 (not 2222). The app MUST bind 0.0.0.0, not 127.0.0.1."
    },
    "site_slug": {
      "type": "string",
      "description": "Optional subdomain (3–30 chars: lowercase letters, digits, hyphens). Defaults to your bot's id. The public site is <site_slug>.oteny.bot."
    },
    "ensure_cmd": {
      "type": "string",
      "description": "Optional shell command that (re)starts your app, run if the site is detected down (self-heal)."
    }
  },
  "required": [
    "local_port"
  ]
}
```

**Result** — {url, status} — status starts 'provisioning' and turns 'active' within about a minute (poll with list_hosted_websites). ALWAYS relay the url.

**Errors / edges** — {error: 'pass `local_port` — the port your app binds (1024–65535, not 2222). Make sure the app listens on 0.0.0.0, not 127.0.0.1.'} · a metered-cap refusal. A 502 on the live site almost always means the app bound 127.0.0.1 instead of 0.0.0.0.

**Example**

```json
{
  "local_port": 8080,
  "site_slug": "my-shop",
  "ensure_cmd": "cd ~/shop && ./run.sh"
}
```

→

```json
{
  "url": "https://my-shop.oteny.bot",
  "status": "provisioning"
}
```

**Authoring notes** — The site is PUBLIC — the bot must confirm with the owner before the first publish. The app must bind 0.0.0.0 (all interfaces).

### `unhost_website` — Take a website down

*first-party tool · request via `tools.required` · status **live** · cost Included*

> Take a public website down — the link stops working. Pass the `site_slug` you published (or omit it if you only have one site). Use when the user asks to take a site offline or make it private. You can only unhost your own sites.

**Parameters**

```json
{
  "type": "object",
  "properties": {
    "site_slug": {
      "type": "string",
      "description": "The subdomain to take down (omit if you only host one site)."
    }
  },
  "required": []
}
```

**Result** — A confirmation object; the public link stops working.

**Errors / edges** — Only the shared platform-error set. Owner-scoped to the bot's own sites.

**Example**

```json
{
  "site_slug": "my-shop"
}
```

→

```json
{
  "ok": true
}
```

**Authoring notes** — Omit site_slug when the bot hosts exactly one site.

### `list_hosted_websites` — List hosted websites

*first-party tool · request via `tools.required` · status **live** · cost Included*

> List the public websites you're hosting (url, status, health, port), so you can answer 'what have I put online?' or pick one to take down. Side-effect-free.

**Result** — The bot's hosted sites: rows carrying url, status, health, port. Side-effect-free.

**Errors / edges** — Only the shared platform-error set.

**Example**

```json
{}
```

→

```json
{
  "sites": [
    {
      "url": "https://my-shop.oteny.bot",
      "status": "active",
      "health": "ok",
      "port": 8080
    }
  ]
}
```

## Share a file as a link

### `publish_file` — Share a file as a link

*first-party tool · request via `tools.required` · status **live** · cost Included*

> Publish a file you've produced to a public, shareable web link (a 'drop'). Use this whenever you've made an artifact the user should open in a browser or share with someone who isn't in this chat — an HTML page or dashboard, a chart or image, a PDF, a CSV/spreadsheet, a screenshot, an archive (.zip/.tar.gz), or any other file (any type, up to 20 MB). It's your built-in way to put a file online — reach for it rather than uploading to an outside file host. Pass the local `file_path` you wrote it to; you get back a public URL (CORS-open, so images embed anywhere, deep-links/players work, and the link works for anyone). Optionally pass `expiry_days` for a throwaway link (default: it stays available as long as your bot does). For a quick paste-bin, pass `text` or `html` inline instead of a file. To restrict access, pass a `password` — the user opens the link and types it to view; note a password-protected file is NOT embeddable (use it for private viewing, not `<img>` embeds). Prefer this over pasting large file contents into chat. After publishing, ALWAYS give the returned URL back to the user in your reply (never a local path). Use `unpublish_file` to take a drop down, `list_published_files` to see what you've published.

**Parameters**

```json
{
  "type": "object",
  "properties": {
    "file_path": {
      "type": "string",
      "description": "Local path to the file you wrote and want to publish."
    },
    "expiry_days": {
      "type": "integer",
      "description": "Optional: auto-expire the link after N days (default: keep while the bot lives)."
    },
    "password": {
      "type": "string",
      "description": "Optional: require this password to view (relay it to the user). A protected file is not embeddable."
    },
    "file_name": {
      "type": "string",
      "description": "Optional friendly download name (defaults to the file's basename)."
    },
    "text": {
      "type": "string",
      "description": "Optional inline plain text to publish instead of a file."
    },
    "html": {
      "type": "string",
      "description": "Optional inline HTML to publish instead of a file."
    }
  },
  "required": []
}
```

**Result** — {url, expires_at?} — the public share link (CORS-open unless password-protected). ALWAYS relay the url to the user; a local path is useless to them.

**Errors / edges** — {error: "could not read '<path>': …"} · {error: 'file is larger than 20 MB — too big to publish'} · a metered-cap refusal (the owner must top up). Password-protected files are not embeddable.

**Example**

```json
{
  "file_path": "/home/user/report.html",
  "expiry_days": 7
}
```

→

```json
{
  "url": "https://drop.oteny.bot/ab12/report.html",
  "expires_at": "2026-07-19"
}
```

**Authoring notes** — For a file YOUR BOT produced locally. A file the REMOTE cloud browser downloaded goes through browser_download instead. Inline modes: pass text= or html= instead of file_path (a paste-bin).

### `unpublish_file` — Take a link down

*first-party tool · request via `tools.required` · status **live** · cost Included*

> Take down a file you previously published with publish_file — the link stops working. Pass the `url` you got back (or its `id`). Use when the user asks to delete/remove a drop or revoke a shared link. You can only unpublish your own files.

**Parameters**

```json
{
  "type": "object",
  "properties": {
    "url": {
      "type": "string",
      "description": "The drop URL to take down."
    },
    "id": {
      "type": "string",
      "description": "The drop id (alternative to url)."
    }
  },
  "required": []
}
```

**Result** — A confirmation object; the link stops working.

**Errors / edges** — {error: "pass the file's `url` (or `id`) to unpublish."} when neither is given. Owner-scoped: you can only unpublish your own files.

**Example**

```json
{
  "url": "https://drop.oteny.bot/ab12/report.html"
}
```

→

```json
{
  "ok": true
}
```

### `list_published_files` — List shared files

*first-party tool · request via `tools.required` · status **live** · cost Included*

> List the files you've published (url, name, size, when, expiry, whether password-protected), so you can answer 'what have I shared?' or pick one to unpublish. Side-effect-free.

**Result** — The bot's published drops: rows carrying url, name, size, created, expiry, password-protected flag. Side-effect-free.

**Errors / edges** — Only the shared platform-error set (temporarily unavailable / cap).

**Example**

```json
{}
```

→

```json
{
  "files": [
    {
      "url": "https://drop.oteny.bot/ab12/report.html",
      "name": "report.html",
      "size": 18234,
      "protected": false
    }
  ]
}
```

## Connect your accounts

### `connect_account` — Connect an account (API key)

*first-party tool · request via `tools.required` · status **live** · cost Included*

> Create a secure, single-use link the user opens to hand you an API key or token for another service (use when they want to connect an account, e.g. 'connect my OpenWeather key'). Never ask for the key in chat. Pass a human-readable `label` (the provider/account name shown on the form) and the UPPER_SNAKE_CASE `env_var` the key should be delivered as, then send the user the returned link. After they submit, the value appears as that environment variable for your tools within a few minutes.

**Parameters**

```json
{
  "type": "object",
  "properties": {
    "label": {
      "type": "string",
      "description": "Provider/account name shown on the connect form, e.g. 'OpenWeather'."
    },
    "env_var": {
      "type": "string",
      "description": "UPPER_SNAKE_CASE env var to deliver the key as, e.g. OPENWEATHER_API_KEY."
    }
  },
  "required": [
    "label",
    "env_var"
  ]
}
```

**Result** — {ok: true, url, expires_minutes: 30, label, env_var} — a secure single-use link (30-min expiry). Relay the url; the key the owner enters is delivered to the bot's environment as `env_var` and NEVER transits chat.

**Errors / edges** — {ok: false, reason} for: an empty label · env_var not UPPER_SNAKE_CASE · a reserved/managed env_var (pick a provider-specific name) · too many open links (ask the owner to complete one or let it expire, then retry). Plus the shared platform set.

**Example**

```json
{
  "label": "OpenWeather",
  "env_var": "OPENWEATHER_API_KEY"
}
```

→

```json
{
  "ok": true,
  "url": "https://oteny.com/connect/ab12cd",
  "expires_minutes": 30,
  "label": "OpenWeather",
  "env_var": "OPENWEATHER_API_KEY"
}
```

**Authoring notes** — NEVER ask for an API key in chat — mint the link instead. Free. A website LOGIN (username + password) goes through connect_login.

### `connect_login` — Remember a website login

*first-party tool · request via `tools.required` · status **live** · cost Included*

> Create a secure, single-use link the user opens to **save a website login** (username + password, and optionally a 2FA setup key) so you sign in automatically on future visits — use when the user wants you to *remember* a login for a site (e.g. 'stay logged in to my bank', 'remember my Marktplaats login'). Never ask for the password in chat; you never see it. Pass a human-readable `label` (the site/account name) and the site's `domain` (e.g. example.com). After they submit, future browser sessions sign in automatically. For a one-time login use `browser_request_human` instead.

**Parameters**

```json
{
  "type": "object",
  "properties": {
    "label": {
      "type": "string",
      "description": "Site/account name shown on the form, e.g. 'My bank'."
    },
    "domain": {
      "type": "string",
      "description": "The website to save the login for, e.g. example.com."
    }
  },
  "required": [
    "label",
    "domain"
  ]
}
```

**Result** — {ok: true, url, expires_minutes: 30, label, origin} — a secure single-use link where the owner saves username + password (and optionally a 2FA setup key). The bot NEVER sees the credentials; every future browser visit to that origin signs in automatically.

**Errors / edges** — {ok: false, reason} — a missing website address, or too many open links (30-min expiry). On a bot without saved-login support the name is unknown ({error:"unknown tool 'connect_login'"}) → use browser_request_human. Plus the shared platform set.

**Example**

```json
{
  "label": "Marktplaats",
  "domain": "marktplaats.nl"
}
```

→

```json
{
  "ok": true,
  "url": "https://oteny.com/connect/ef34gh",
  "expires_minutes": 30,
  "label": "Marktplaats",
  "origin": "https://www.marktplaats.nl"
}
```

**Authoring notes** — For RECURRING logins ('remember my X login'); a one-time login is browser_request_human. `label` may be omitted (derived from the domain). Free. Compose with the delivered oteny-remember-login skill on the box.

### `list_logins` — List saved logins

*first-party tool · request via `tools.required` · status **live** · cost Included*

> List the websites the user has saved a login for, so you can answer 'what logins have I saved?'. Returns the site origins only — never any passwords. Side-effect-free.

**Result** — {origins: ['https://example.com', …]} — the sites with a saved login, origins ONLY (never a password); [] when none. Side-effect-free, free.

**Errors / edges** — Only the shared platform set (a storage fault surfaces as {error:'tool call failed'}).

**Example**

```json
{}
```

→

```json
{
  "origins": [
    "https://www.marktplaats.nl"
  ]
}
```

### `disconnect_login` — Forget a login

*first-party tool · request via `tools.required` · status **live** · cost Included*

> Remove a saved website login. Pass `domain` to forget one site, or `all: true` to forget every saved login — **confirm with the user before forgetting all**. Use when the user says 'forget my X login' or 'forget all my logins'.

**Parameters**

```json
{
  "type": "object",
  "properties": {
    "domain": {
      "type": "string",
      "description": "Site to forget, e.g. example.com."
    },
    "all": {
      "type": "boolean",
      "description": "Forget every saved login (confirm first)."
    }
  },
  "required": []
}
```

**Result** — One site: {ok: true, removed: ['<origin>']}. all:true: {removed: [<every origin>]} — note this branch carries no `ok` key.

**Errors / edges** — Neither arg given → {ok: false, reason: 'name the site to forget, e.g. example.com.'}. Plus the shared platform set.

**Example**

```json
{
  "domain": "marktplaats.nl"
}
```

→

```json
{
  "ok": true,
  "removed": [
    "https://www.marktplaats.nl"
  ]
}
```

**Authoring notes** — CONFIRM with the user before all:true (it forgets every saved login). Free.

## Out of the box

### `switch_persona` — Smart model switching

*first-party tool · request via `tools.required` · status **live** · cost Included*

> Escalate to a stronger model for ONE error-prone task, then switch back. Call this FIRST when starting a task named in your 'Model routing' table (e.g. finding or verifying real bookable listings, rentals, tickets, or offers), with the table's task slug. The switch is announced to the user, uses credits faster, and stays on until you call this again with done=true — do that as soon as the task is finished so ordinary chat stays cheap. Never switch for plain conversation, and never call it repeatedly for the same task.

**Parameters**

```json
{
  "type": "object",
  "properties": {
    "task": {
      "type": "string",
      "description": "The task slug from your Model routing table, e.g. 'live-inventory'."
    },
    "done": {
      "type": "boolean",
      "description": "true when the task is finished — switches back to the default model."
    }
  },
  "required": [
    "task"
  ]
}
```

**Result** — {success, task, model, message} — the `message` is the user announcement the bot relays (mandatory: escalation is never silent). done=true returns the drop-back confirmation.

**Errors / edges** — {error: 'unknown_task'} → only the tasks in the bot's Model-routing table are valid. {error: 'not_available'} → this bot has no escalation tasks (a locked business bot never does). {error: 'rate_limited'} → stay on the current model; switching per message wastes credits.

**Example**

```json
{
  "task": "live-inventory"
}
```

→

```json
{
  "success": true,
  "task": "live-inventory",
  "model": "builder",
  "message": "Now using the builder model for this task\u2026"
}
```

**Authoring notes** — Platform-managed: the task map comes from the fleet policy plus each Talent's declared `task_escalations`; a Talent never calls this for plain chat. Sticky per task — switch once, finish, then done=true. The switch itself is free; the stronger model burns credits faster while it's on.

### `cron` — Schedule tasks

*built-in toolset · request via `toolset_contribution` · status **live** · cost Included*

**Result** — Scheduled jobs the bot creates run on its own machine (an in-process scheduler); each fire is a normal agent turn.

**Errors / edges** — A job on an archived/paused bot does not fire until it returns.

**Authoring notes** — Declare for bots that watch/remind/report on a schedule. Compose with the delivered oteny-cron-authoring skill on the box.

### `memory` — Long-term memory

*built-in toolset · request via `toolset_contribution` · status **live** · cost Included*

**Result** — Long-term memory across conversations (the bot remembers the owner, preferences, ongoing context).

**Errors / edges** — —

**Authoring notes** — On a locked (scoped) business bot the self-editing curator side is disabled by the platform; remembering still works.

### `terminal` — Run shell commands

*built-in toolset · request via `toolset_contribution` · status **live** · cost Included*

**Result** — Arbitrary shell on the bot's own isolated machine.

**Errors / edges** — —

**Authoring notes** — A scoped business bot should almost never declare this — the whole point of the scope-lock is that a prompt-injected bot finds NO shell mounted. List the minimum and stop (business-bot-pattern.md §2).

### `execute_code` — Run code

*built-in toolset · request via `toolset_contribution` · status **live** · cost Included*

**Result** — Run Python/code snippets on the bot's machine.

**Errors / edges** — —

**Authoring notes** — Same discipline as terminal: leave it OFF a scoped business bot unless the job itself is computation.

### `skills` — Build its own skills

*built-in toolset · request via `toolset_contribution` · status **live** · cost Included*

**Result** — The bot can view/load its skills; with self-modification enabled it can also author new ones.

**Errors / edges** — —

**Authoring notes** — On a locked business bot the platform keeps a read floor (skill_view works — the bot can load YOUR skills) and disables creation/self-editing. You rarely need to declare this explicitly; the lock floor provides it.

### `todo` — To-do list

*built-in toolset · request via `toolset_contribution` · status **live** · cost Included*

**Result** — A per-bot task list the agent maintains across turns.

**Errors / edges** — —

**Authoring notes** — Cheap and useful for any bot that chases multi-step work across days.

### `send_message` — Proactive messages

*built-in toolset · request via `toolset_contribution` · status **live** · cost Included*

**Result** — The bot can message the owner/channel proactively (outside a reply).

**Errors / edges** — —

**Authoring notes** — Needed by watchers/escalators: anything that must speak up on its own (a cron result, an alert, an escalation).
