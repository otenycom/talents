# The checklist-first bar — the shape and the worked examples

Detail behind the foregrounded principle in [`../SKILL.md`](../SKILL.md) ("The
checklist-first bar — the airline-pilot rule") and its Talent expansion in **check 11**.
Pulled on demand; the body states the bar, this file carries the shape.

## The shape, scaled to the skill

- A **master triage** on every message (setup-check → is-this-for-me → classify →
  dispatch) for a multi-intent Talent; for a single-purpose skill, the **one ordered
  protocol it runs every time** (the cron skill's *"do these in order, every time"*).
- **Per-task sub-checklists** — numbered, literal, shaped **input → check → reply/act**.
  "Decision = checklist, not prose; don't improvise."
- **Completeness loops** for multi-input flows (onboarding) — track each required input,
  ask only for the **still-missing** ones, validate ranges, and **never restart** from a
  partial state. On an interruption, **re-ground from the store before continuing** a
  mutating sequence — re-read where the flow actually is rather than assuming the step;
  never blind-restart and never double-write.
- **Grounded, never confabulated** — read the tenant value from the store **this turn**
  and quote it (cite any evidence figure, or say "let me check"); *"no data"* is a valid
  answer, never a fabricated one.

## Disciplines for a weak reader

Five habits that keep a checklist runnable by the slavish Flash tier — each is the
cockpit/maintenance practice behind the bar, not a new idea to bolt on:

- **Do-list, not flow.** The model reads each step and does it; it never "acts from
  memory, then verifies." (Aviation's *Challenge-Verification-Response* flow assumes a
  reliable memory the weak tier lacks — use *Call-Do-Response*, the read-and-do list.)
  The decision is the step, not the model's recall.
- **Exact-status responses.** Each step names the precise, verifiable end-state —
  "write the row, then read it back and quote the saved kcal" — never a passive "log
  it" / "handle it" / "check the data" the model can rubber-stamp without acting.
  (Aviation bans the vague "set"/"checked"; name the status.)
- **A failure branch per step.** Every step that can fail carries its recovery line
  inline — *retry / ask the user / escalate*. This is the **one** half of "outcome-
  oriented, let the model reason around errors" we keep: the weak tier cannot improvise
  recovery, so author it. A happy-path-only checklist is the bug, not the skill.
- **Semantic errors, never fake-empty data.** A failing tool or script must surface an
  **actionable** error the model branches on; it must **never** swallow the error into
  an empty list or a mock result — an empty result reads as "all clear" and silently
  mis-routes the agent. Stocks' rule *"Surface errors, don't silently work around them"*
  (and *"No fake data, ever"*) is the shape; it extends the grounded rule to the error path.
- **Negative constraints last.** Put the hard *never-do-X* prohibitions at the **end** of
  the skill/task — a weak model weights its most-recent tokens highest (recency), so the
  bans land where they are read last and obeyed.

## Reference implementations (copy the shape)

The shipped worked example for check 11 is **Flatbelly-talent**: the master triage in
[`food-tracker/SKILL.md`](../../oteny-flatbelly-talent/food-tracker/SKILL.md) ("Every
message — triage first"), the per-intent entry→analysis→reply
[`checklists.md`](../../oteny-flatbelly-talent/food-tracker/references/checklists.md),
the plain-language + fade-ladder
[`glossary.md`](../../oteny-flatbelly-talent/food-tracker/references/glossary.md), and the
input-by-input "Completeness checklist" in
[`flatbelly-onboarding/SKILL.md`](../../oteny-flatbelly-talent/flatbelly-onboarding/SKILL.md).

The non-Talent ordered-protocol shape to copy is the platform **oteny-cron-authoring**
skill delivered on every bot (*"do these in order, every time"*) — the same bar at
single-skill scale. It is not in this catalog; open it on a live box under
`~/.hermes/skills/talents/oteny-cron-authoring/`.

## Talent nuances (check 11)

Two output disciplines a full Talent layers on top of the shape:

- **Speak to the user, not the expert — then fade jargon in.** Explain domain jargon
  (leucine / mTOR for food; P/E / RSI for stocks) in plain words **with why it matters**
  while the tenant is new, **gradually shifting to the bare term as they settle** — a
  three-rung fade gauged by tenure/usage: **new** (plain + why, every time) → **settling**
  (term + a short tag) → **settled** (bare term), always dropping back to plain words the
  moment they ask. **Never hand a newcomer a bare metric** they can't read. Ship a
  **plain-language glossary** keyed to the terms the bundle surfaces, **with that fade
  ladder**, and point the output rules at it.
- **Keep the hot path in the body, the rest in `references/`.** State the few hard rules
  once in the lean `SKILL.md` (they're held every turn); push per-intent detail to
  `references/` for on-demand load. A weak model benefits from the hard rules being
  *present*, but a fat body it re-reads every turn is the failure mode this rubric exists
  to prevent (D57) — restate sparingly, don't duplicate whole sections.

**Keep checklists lean** — tune them against real test-VM logs as live cases surface,
don't over-specify up front.

## Verify before you gate — don't mistake REAL info for hallucination (live-proven, the hard way)

A trap worth more than any rule it produced. The travel talent's `assistant` (Gemini-Flash) tier
surfaced transit-disruption info from `web_search` (a Surinameplein tram closure / works), and the
author **presumed it was hallucination, called it "fabrication," and built a mechanical gate that
blocked `web_search` for that intent.** Truth-checked against the real world, the premise was wrong:

- The works were **real and useful** — the GVB Oranje Loper reconstruction + the 4-July
  zomerdienstregeling (shuttle trams 27/28, the Surinameplein split) are genuine.
- A forwarded **photo of a stop's closure sign** was correctly **overridden** by a web check that
  said the stop was open — the sign was just stale (workers hadn't removed it). Web beat reality.

So the gate destroyed real value and made the bot **refuse true info**. The actual failure was
narrower and different: **over-assertion** (presenting a web *report* as a "⚠️ CRITICAL live
disruption" / guaranteed live feed) and the **occasional garbled specific** (a self-contradicting
train number, an invented exact "40 m") — not "the tool hallucinates."

The lessons:

- **Truth-check before you block. Data is king** — verify a claim against the real source before
  declaring it a hallucination and gating the tool. A tool returning something you can't *instantly*
  confirm is not proof it's wrong; blocking a tool is a big hammer — earn it with evidence.
- **Fix over-assertion with attribution, not suppression:** make the model **cite the source** and
  **frame it as a report** ("Per GVB, works from 4 July…"), **never invent a specific the source
  didn't give**, and **if two results conflict, say so** — keep the tool, fix the framing.
- **Treat a user's photo / on-the-ground sign as possibly stale** — cross-check it against a live
  source rather than trusting it blindly.
- **A reference file that says the old thing wins over a SKILL.md rule** (the model followed
  `disruption.md` over a newer SKILL.md line) — when you do change a rule, reconcile it at **every**
  reference, not just the body (enumeration sweep).
