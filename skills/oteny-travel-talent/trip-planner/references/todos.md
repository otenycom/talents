# trip-planner — Per-Member Prep Todos

The `todos` table holds prep tasks: packing, documents, health, bookings, admin. A todo
can be **per-member** (`member_id`) or whole-party (`member_id` NULL). In a group, anyone
can add a task and **claim their own**. Schema in [`datamodel.md`](datamodel.md); the
ready-made template lists are in
[`../../resources/packing-templates.md`](../../resources/packing-templates.md) and
[`../../resources/document-checklists.md`](../../resources/document-checklists.md).

## Add a todo (entry → verify → reply)

1. Classify `category` ∈ packing/document/booking/health/admin. Resolve `member_id`
   (whose task — map the speaker in a group; NULL = whole party) and `due` (a date or
   NULL).
2. Insert — one statement; read the id back.

   ```bash
   sqlite3 ~/.hermes/data/oteny-travel-talent/trips.db "INSERT INTO todos (trip_id, member_id, title, category, due) VALUES (<trip_id>,<member_id>,'Renew passport (expires within 6 months)','document','2026-08-01');"
   ```
3. Reply: confirm the task + who owns it + the due date.

## Seed a starter list (don't hand a blank page)

When a trip is created (or the tenant asks "what do I need to do?"), seed a **starter
prep list** from the template that fits `trips.type` + the destination:
1. Pick the packing template (beach / city / ski / road-trip / with-kids / business) from
   `resources/packing-templates.md`; pick the document checklist from
   `resources/document-checklists.md`.
2. Insert the items as `todos` (category `packing` / `document`), assigned per member where
   it makes sense (each adult owns their own passport task; shared gear is whole-party).
3. **Documents are advisory** — passport validity, visa/ESTA, vaccinations depend on
   nationality + destination and **change**: always say "verify with the official source"
   and, when asked specifics, check live via `travel`/`web_search` (hard rule ④,
   `../../references/safety-boundaries.md`). Never assert an entry rule as settled.

## Claim / complete / list

- **Claim** (group): a member takes an unassigned task → `UPDATE todos SET member_id=<id>
  WHERE id=<todo_id>;`.
- **Complete**: `UPDATE todos SET done=1 WHERE id=<todo_id>;` (guarded by id).
- **List open**, per member or whole party:

  ```bash
  sqlite3 ~/.hermes/data/oteny-travel-talent/trips.db "SELECT t.id, COALESCE(m.display_name,'(party)') AS who, t.category, t.title, t.due FROM todos t LEFT JOIN members m ON m.id=t.member_id WHERE t.trip_id=<trip_id> AND t.done=0 ORDER BY t.due IS NULL, t.due, t.id;"
  ```

Reply with the open list grouped by person, the soonest-due first, and **one** nudge if a
dated task is close. The daily briefing surfaces each member's still-open todos.
