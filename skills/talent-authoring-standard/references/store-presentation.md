# Store presentation + per-Talent tools (the storefront face)

Pulled out of the `SKILL.md` body to keep it lean (the native >20k split rule). These two
optional bundle-root files give a Talent its face in the Oteny Bot Market, and the
`agent-profile.yaml` tools declaration doubles as the storefront's "what it can do" copy.

## `icon.png` + `teaser.yaml`

Two optional bundle-root files give a Talent its face in the Oteny Bot Market — read by
the seeder, never required at runtime, so a bundle without them still works (graceful
fallback). Author both for any Talent you want to ship to the storefront.

- **`icon.png`** — a square card/landing mark, ≥512×512 (the seeder down-scales),
  transparent or stage-dark background, in the art-deco gold palette. Distinct per Talent
  (a grid of identical glyphs reads as unfinished). The mark must stay legible at ~56 px
  and hold contrast on a light card; pre-rasterise an `.svg` to PNG (the seeder stores the
  raster as-is). An `icon:` key in `agent-profile.yaml` overrides the default filename. The
  icon is **ops-curatable**: a backend upload wins and is never clobbered by a re-seed.

- **`teaser.yaml`** — a believable **sample chat** rendered on the landing page (and the
  homepage, for the flagship). One authored artifact, two consumers (and the future in-chat
  previewer). Shape:

  ```yaml
  teaser:
    title: "Weekly groceries"          # group-chat title (required)
    icon: fa-shopping-basket            # FontAwesome class for the group avatar
    members:                            # required; role me|bot, else a "them" colour by index
      - {key: me,  name: You,      role: me}
      - {key: sam, name: Sam}           # optional color: maya|priya|sky|rose|sage|plum
      - {key: bot, name: OtenyBot, role: bot}
    turns:                              # required; each `from` is a member key + content
      - {from: me,  at: "18:02", text: "add oat milk x2"}
      - {from: bot, at: "18:02", text: "Added — Dairy aisle.",
         card: {title: "Weekly list", lines: ["oat milk x2", "spinach"], status: "12 items"}}
      - {from: bot, image: "teaser/aisle.png", alt: "list grouped by aisle"}   # alt REQUIRED
  ```

  A turn carries any of `text` / `card` / `image` / `video`. **Every image/video turn MUST
  carry `alt`** (the accessibility floor — same as a screenshot); the seeder rejects one
  that doesn't. A card line may be `{text, highlight: true}` to spotlight a changed line.
  Bundle-relative media (`teaser/…`) is inlined as a data URI at seed time; an `http(s)`
  URL is kept as-is. Keep it short (a dozen turns) and lead with the outcome.

## Per-Talent tools-used (check 9 extension)

State, in `agent-profile.yaml`, the capabilities the Talent leans on — its
`toolset_contribution` (the Hermes built-ins it unions in: `terminal`, `cron`,
`send_message`, …) and any first-party tool under `tools.required` / `tools.stubbed`. This
is both the runtime contract (check 9: absent charged tools ship as graceful stubs) and the
storefront's "what it can do" copy. Don't claim a tool you don't use; don't stub a tool the
catalog says is live (`lint_tools.py` fails a stale claim).
