# trip-planner — Per-Intent Checklists (the operator manual)

Step-by-step for **one message**, after the master triage in [`SKILL.md`](../SKILL.md)
("Every message — triage first") has classified the intent. Follow the matching section
top to bottom — **don't skip steps, don't improvise**. The big intents have their own
reference (TRANSIT/ITINERARY are inlined in `SKILL.md`; BOOKING → `bookings.md`,
schedule → `schedule.md`, TODO → `todos.md`, EXPENSE → `expenses.md`, DISRUPTION →
`disruption.md`); this file carries TRIP, MEMBER, BRIEFING, ADJUST, DASHBOARD and the
final-check.

**Every checklist obeys the hard rules** (full text in `SKILL.md`): ① no vibe-served
facts — read the DB or call `travel` this turn and quote it; ② verify flight/train status
live before any leave-by; ③ link out, never book/pay; ④ advisory-only on entry/health.
Every write follows **one-`sqlite3`-call-per-INSERT, verify-with-a-separate-SELECT**. A
failed tool/script is an **error to surface**, never a faked empty result.

---

## §TRIP — start or edit a trip

**A. Data entry**
1. Resolve what they gave: `name` (e.g. "Our Trip to Lisbon"), `destination`, `start_date`,
   `end_date`, `type` (beach/city/ski/road-trip/family/business/other). Missing dates are
   fine — a trip can start as just a name + destination. Default `home_city` from
   `profile.home_city`.
2. Insert the trip (`status='planning'`). One statement; then read the new `id` back.

   ```bash
   sqlite3 ~/.hermes/data/oteny-travel-talent/trips.db "INSERT INTO trips (name, destination, start_date, end_date, type, home_city, status) VALUES ('Our Trip to Lisbon','Lisbon','2026-09-10','2026-09-14','city','<home_city>','planning');"
   ```
3. **Group?** If the human says they'll add the bot to a trip group, tell them to create
   the group and add the bot (a bot **cannot** create a group or add people). Once bound,
   set `trips.group_chat_id` and add the owner as the `lead` member (§MEMBER). DM/solo →
   leave `group_chat_id` NULL; no members needed.

**B. Analysis**
4. If dates are set, that defines the trip window → the new-trip checklist **schedules the
   trip's crons** now (monitor/briefing/review), list-first:

   ```bash
   python3 ~/.hermes/skills/talents/oteny-travel-talent/scripts/provision_cron.py --trip <id> --json
   ```
   Register **each** `to_create` job with the `cronjob` tool, passing **every** field —
   **including `model` + `provider`** (mandatory: an un-pinned cron fires with an empty
   model and the router 400s). Skip if dates are still unknown; re-run when they're set.

**C. Reply**
5. Confirm the trip back (name, destination, dates, days-to-go), and name the next lever
   ("add your flights so I can watch them", "tell me who's coming", "want a day plan?").

## §MEMBER — map a speaker / add a traveller (group trips)

1. From the sender's `telegram_user`, look up their `members` row for the active trip.
2. **New speaker** → greet them by **name** and insert them (idempotent on the unique
   `(trip_id, telegram_user)` index, so a re-greet never double-inserts):

   ```bash
   sqlite3 ~/.hermes/data/oteny-travel-talent/trips.db "INSERT INTO members (trip_id, telegram_user, display_name, role) VALUES (<trip_id>,'<telegram_user>','<name>','member') ON CONFLICT(trip_id, telegram_user) DO UPDATE SET display_name=excluded.display_name;"
   ```
3. Adding someone **by name only** (no Telegram handle) → insert with `telegram_user` NULL.
   The owner is the `lead`.
4. Reply: welcome them, say what they can do here (ask, claim todos, log expenses).

## §BRIEFING — the daily trip briefing (cron)

Runs only inside the trip window (the cron prompt + this checklist gate it).
1. Run `preflight.py`. If **today is outside** the trip window → reply `[SILENT]`. Stop.
2. Read **today's itinerary** (preflight gives it) and the **first departure** of the day.
3. For the first departure leg, **re-pull live status** via `travel` and compute the
   **leave-by** (`schedule.md`). Get a one-line **weather** for the destination via
   `travel`/`web_search`.
4. Read each member's **still-open todos** (`todos.md`).
5. Reply: a tight briefing — today's plan in order, the leave-by for the first move, the
   weather, and each person's open prep. Ground every fact (hard rule ①). If nothing is
   scheduled and nothing is open → a short "clear day" note, not a fabricated agenda.

## §ADJUST — durable customization (the teach loop) — NEVER touch the bundle

The tenant is changing how the Talent behaves. The change must land in this Talent's **own
data-plane files** (converge never touches them) — **never** the shipped bundle under
`~/.hermes/skills/talents/oteny-travel-talent/`, and **never** the global SOUL
(`~/.hermes/data/_overrides/soul-override.md`).

1. **Classify the kind:**
   | The tenant said… | kind | target file |
   |---|---|---|
   | a durable **fact/preference** ("home airport is Schiphol", "default currency EUR", "I prefer aisle seats") | FACT | `memory.md` |
   | a **rule / behavior / voice** change ("never auto-book", "always split evenly", "stop the morning briefing", "be terse", "greet us in Dutch") | RULE | `overrides.md` |
2. **FACT → append one line** to `~/.hermes/data/oteny-travel-talent/memory.md` (read it
   first; only add if not already there — never duplicate). `preflight.py` reads it every
   turn, so it's in hand next message.
3. **RULE → merge a delta** into `~/.hermes/data/oteny-travel-talent/overrides.md` — one
   consolidated doc, sectioned (Preferences / Rules / Voice), **corrections + additions
   only, never a copy of the base**. Read the existing file, merge the new rule (replace a
   conflicting line, don't append a duplicate), write the whole file back with the file
   tool. The global SOUL rule makes the agent read + obey it with precedence next turn.
4. **Confirm** in plain words what you changed and that it'll apply from now on. **Do not**
   edit any file under the skills bundle.

> Fact vs rule is the same split Wilma uses: a "Preferences" line vs a "User Overrides"
> child article — delta-only, "takes precedence", never a rewrite of the base.

## §DASHBOARD — the visual trip card

1. Resolve the trip id. Run the visual ([`trip-dashboard`](../../trip-dashboard/SKILL.md)):

   ```bash
   python3 ~/.hermes/skills/talents/oteny-travel-talent/trip-dashboard/scripts/trip_card.py --trip <id>
   ```
2. Deliver the PNG by putting `MEDIA:<printed path>` in the reply.
3. Caption per that skill's rules (countdown, today/next, settle-up headline, packing
   status), grounded in the DB read. If the trip has no content yet, say so instead.

---

### After any branch — final check (every reply)
- Did I **read the DB or call `travel` this turn** and quote real values? (hard rule ①)
- For anything time-of-travel, did I **re-verify live** before a leave-by? (hard rule ②)
- Did I **link out** and never imply a booking/payment? (hard rule ③)
- For entry/visa/health, did I stay **advisory + verify-live**? (hard rule ④)
- For an adjustment, did it go to `memory.md` / `overrides.md` and **not** the bundle/SOUL?
- Is the reply compact, in the tenant's language, with **one** clear next step?
