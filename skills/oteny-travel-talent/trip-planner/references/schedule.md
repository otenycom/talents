# trip-planner — Day-by-Day Schedule & Leave-By Math

The `itinerary` table is the day-by-day plan; `bookings` holds the fixed legs/stays. This
file is the build recipe + the **leave-by** computation. Schema in
[`datamodel.md`](datamodel.md).

## Build / edit the schedule (entry → verify → reply)

1. Resolve the trip + `day_date` (parse "day 1", "Friday", "10 Sep" → a date,
   `datamodel.md` date parsing). Parse each item's `time` (`HH:MM`, NULL = all-day).
2. Classify `category` ∈ transit/meal/activity/lodging/admin. Pull `title` + `place`.
3. Write **one INSERT per item**, the source/assumption in `notes`:

   ```bash
   sqlite3 ~/.hermes/data/oteny-travel-talent/trips.db "INSERT INTO itinerary (trip_id, day_date, time, title, place, category, notes) VALUES (<trip_id>,'2026-09-11','19:30','Dinner at Time Out Market','Time Out Market, Lisbon','meal','tenant pick');"
   ```
4. **Verify** with a separate SELECT for that day, ordered by time, and read it back.
5. Reply: lay the day out **in time order**, quoting the times; flag clashes or a too-tight
   gap to the next fixed leg.

## Leave-by — the number the tenant actually needs

For any timed item that requires travel (catch a flight/train, reach a venue), tell them
**when to leave their door**, not just when the thing starts:

```
leave_by = scheduled_start − live_door_to_door_duration − buffer
```

1. **Re-pull the live door-to-door duration this turn** via the `travel` tool
   (`transit.md`) from the current location (lodging / `home_city`) to the destination —
   **never** a remembered duration (hard rule ②).
2. Subtract a **buffer** sized to the leg type (quarantined defaults; the tenant can
   override → `memory.md`):
   - **flight, international:** be at the airport ~**180 min** before departure.
   - **flight, short-haul/EU:** ~**120 min**.
   - **train / intercity:** ~**20 min** on the platform.
   - **a venue / activity:** ~**10 min**.
3. Compute `leave_by` and state it with the basis: *"Leave by **07:05** — Schiphol is ~40
   min door-to-door right now + 2 h check-in for a 09:40 EU flight."* If the live duration
   can't be fetched, say so and give a conservative estimate flagged as unverified.
4. The **daily briefing** and the **monitor reroute** both reuse this: a delay that moves
   the departure moves the leave-by.

## Notes

- **One `sqlite3` statement per call**; verify with a separate SELECT.
- **Don't double-schedule.** `preflight.py` already lists today's rows — check before
  inserting a duplicate.
- A **fixed leg already in `bookings`** (a flight, a hotel check-in) doesn't need an
  `itinerary` copy unless the tenant wants it on the day view; if you add one, set
  `category='transit'`/`'lodging'` and reference the booking in `notes`.
