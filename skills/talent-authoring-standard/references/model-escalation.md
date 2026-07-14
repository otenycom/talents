# Per-task model escalation — `task_escalations`

Your bot runs on the cheap, fast model by default (good for chat, good for cost). But a
few kinds of task are **error-prone on the cheap model** — most of all, presenting a
specific listing/rental/ticket/offer as real and bookable, where a weak model tends to
*invent* links or misreport why a page failed. For those tasks — and **only** those tasks
— the bot can steer itself to a **stronger model while the task runs, then drop back**.
This is per-**task**, never a whole-bot model floor, so it is safe on a shared bot that
loads several Talents and safe on an always-shipped (`delivery: baked`) bundle: ordinary
chat, onboarding, and everything else stay cheap.

Declared in your `agent-profile.yaml`; enforced by **lint check 16**
(`lint_upgrade_safe.py`); rendered into the bot's HERMES.md at converge; carried out at
runtime by the `switch_persona` tool (which announces the switch to the user and labels
the charge, then switches back when the task is done).

## The declaration

```yaml
model_tier: assistant                 # your normal default — unchanged
task_escalations:                     # OPTIONAL — omit it entirely if you don't need it
  - task: live-inventory              # a slug you name (announcements + charge label key)
    model_tier: builder               # v1: builder ONLY (see rules)
    skills: [trip-planner]            # which of THIS bundle's skills carry the task
    triggers: >                       # short steer copy shown in the bot's routing table
      finding or verifying real bookable listings, rentals, tickets, or offers —
      anything with a live URL and price the user may act on
    model_tier_reason: fabrication-prone   # WHY this task needs the stronger model (required)
```

Each field:

- **`task`** — a short slug. It names the task in the user-facing announcement and in the
  billing `route_reason`, so make it readable (`live-inventory`, not `t1`).
- **`model_tier`** — the stronger model to use *for this task*. **v1 allows only
  `builder`.** `researcher` is never an automatic target; a whole-bot need is `model_tier`,
  not a task escalation.
- **`skills`** — a non-empty list naming skills **this bundle ships** (the marker the task
  rides). An unknown skill FAILs the lint.
- **`triggers`** — one line of steer copy: what the bot should recognise as "this task
  starting". It goes verbatim into the HERMES.md routing table.
- **`model_tier_reason`** — a required one-liner: *why* the cheap model isn't good enough
  here (`fabrication-prone`, `needs-verification`, …). Reviewed at the catalog gate.

## The rules (what the lint enforces — check 16)

- `model_tier` must be **`builder`** (v1 narrowing).
- Every entry needs a **`model_tier_reason`**.
- Every `skills` entry must be a skill **this bundle ships**.
- **No floor-smuggling:** a declaration set covering **every** skill in the bundle FAILs —
  that escalates the whole Talent by another name. For a bundle-wide need, declare a
  `model_tier:` floor instead; use `task_escalations` only for the specific, fabrication-
  prone tasks.
- **Allowed on `delivery: baked` bundles** — deliberately unlike the `model_tier` floor
  ban, because a task escalation never raises the fleet's base model. (A baked declaration
  still gets platform review at the catalog gate.)

## You usually don't need to declare anything

The platform ships **one built-in category, `live-inventory`**, that already covers the
common case — a user pasting a marketplace/booking link and asking the bot to check it —
on **every** bot, with no Talent loaded. Declare your own `task_escalations` only when your
Talent has a *distinct* fabrication-prone task the built-in category wouldn't catch, and
you can name the skill that carries it.

## What you get at runtime (you don't wire this — the platform does)

- The bot sees an "escalate for this task, then drop back" line in its HERMES.md and calls
  `switch_persona(task="<slug>")` when the task starts. The switch takes effect from the
  bot's **next message** (the model is resolved once per turn), so the bot announces the
  switch, ends that reply, does the task on the following message, and switches back with
  `switch_persona(task="<slug>", done=true)` once the task is delivered.
- The switch is **announced** to the user and the credit charge is stamped
  `route_reason: task:<slug>` (shown in `/costs` + the spend dashboard). Today it is
  **box-global for the duration** — while the task runs, the whole bot uses the stronger
  model, including any other group chats on it — so the announcement says so; the bot
  drops back to the cheap model when the task is done. (Per-chat scoping is the target,
  and arrives with a Hermes pin ≥ v2026.7.7 that carries `channel_overrides`; nothing you
  declare changes.)
- The escalation is **sticky per task, never per message** (so it doesn't thrash), has a
  soft per-task rate limit and a safety time-out that drops it back if the bot forgets,
  and **cron / background work never follows it**.
- A **locked business bot** (a scoped, single-Talent bot) is exempt: it renders no task
  table and refuses a `task=` switch, so nothing can knock it off its pinned model.

## Why it exists

Measured on the real 2026-07-12 fabrication incident (a travel bot inventing Turo rental
links, then blaming a security block for its own 404): *rules alone did not stop the cheap
model* from making things up, but the **stronger model with those same rules nearly
eliminated it** (it correctly named the dead link ~90% of the time and stopped inventing
links entirely). So the fix is to escalate the fabrication-prone task — surgically, for
that task only — not to make every bot expensive.
