# trip-planner — In-box migrations (version-to-version state fixes)

You are here because triage saw `MIGRATIONS: pending` in `preflight.py`. These are
**forward-only, idempotent** fixes that bring this tenant's live state (registered cron
jobs, db rows) from an older version of the Talent to the current shape. A converge can't
do this — cron jobs aren't files, and only you hold the live chat origin the `cronjob`
tool needs. Run each pending migration **in the order `migrate.py --status` printed**,
**before** the normal turn, then mark it done. Every checklist is **detect-then-act**: if
nothing matches, it's a clean no-op — still mark it and move on. Never fabricate; never
touch another Talent's jobs.

After finishing a migration's steps, record it:

```bash
python3 ~/.hermes/skills/talents/oteny-travel-talent/scripts/migrate.py --mark <id>
```

## 0001_windowed_trip_crons

**Why.** Older versions registered the trip MONITOR as an open `every 6h` interval and the
BRIEFING as an unbounded daily `30 7 * * *` cron. A Hermes interval/daily fires from the
moment it is created, so for a trip booked weeks out they burned a turn every few hours far
from the trip. The current planner emits **day-of-month-bounded** cron expressions over
`start − 2 days … end + 1 day`. This migration swaps the old-shape jobs for the windowed
ones, per active/future trip.

**Steps.**

1. **List** this bot's cron jobs with the `cronjob` tool — `cronjob(action="list")`.
   Find the OLD-shape trip jobs: name starts `OtenyTravelTalent monitor —` or
   `OtenyTravelTalent briefing —` **and** the schedule is an **interval** (`every …`) or an
   **unbounded daily** (`M H * * *`, i.e. `*` for both day-of-month and month). Leave the
   `review`/`EU261` one-shots and any already-windowed job (a day range like `18-31 7`)
   untouched.
2. If there are **none**, this box is already current → skip to step 5 (a clean no-op).
3. **Per active/future trip** (`SELECT id FROM trips WHERE status!='cancelled' AND
   (end_date IS NULL OR end_date >= date('now'))`), re-plan list-first:
   ```bash
   python3 ~/.hermes/skills/talents/oteny-travel-talent/scripts/provision_cron.py --trip <id> --json
   ```
   For each spec in `to_create`, register it with the `cronjob` tool
   (`action="create"`, passing its `schedule`, `repeat`, `name`, `skills`,
   `enabled_toolsets`, `model`, `provider`). The job inherits **this chat** as its delivery
   target (the live origin) — exactly where the old ones delivered. Skip any name already
   present.
4. **Remove** the old-shape monitor/briefing jobs you found in step 1 —
   `cronjob(action="remove", job_id=<id>)` — now that their windowed replacements exist.
   (Create-then-remove, so monitoring is never dropped mid-migration.)
5. **Verify** with `cronjob(action="list")`: every remaining `monitor`/`briefing` job is a
   day-bounded cron expression, and no `every …` / unbounded-daily trip job remains.
6. **Mark** it done:
   ```bash
   python3 ~/.hermes/skills/talents/oteny-travel-talent/scripts/migrate.py --mark 0001_windowed_trip_crons
   ```
