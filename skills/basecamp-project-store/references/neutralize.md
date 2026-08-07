# Neutralize checklist — before a copy of a box serves a turn

A disposable copy of a real owner's box inherits two things this skill cares about: the
**signed-in command-line tool** under `~/.config/basecamp/`, and the **board ids** in
`~/.hermes/data/basecamp-project-store/profile.yaml`. Together those are enough to write into
a live customer's project — visible to their team and, if the project has clients, to the
client company.

The automated step disables the recurring digest job. This checklist covers the rest.

## Checks

1. **The digest job is gone.** `~/.hermes/cron/jobs.json` contains no enabled job named
   `Basecamp project digest`.
2. **The board is not a live one.** Either
   - `~/.hermes/data/basecamp-project-store/profile.yaml` is absent or its `account_id` /
     `project_id` are empty (the copy starts unconnected — preferred), **or**
   - both point at a board created for testing.
3. **The sign-in is not the real owner's.** Either `~/.config/basecamp/` is absent, or it has
   been replaced with credentials for a test user. If in doubt, remove the directory: the copy
   then behaves like a fresh box and asks to connect.
4. **No pending sign-in is mid-flight.** `~/.hermes/data/basecamp-project-store/auth/` is
   absent or empty, so a half-finished sign-in from the source box cannot complete here.

## If any check fails

Do not start the gateway. Clear the offending item, then re-run the check. A copy that can
reach a live board is not a test box.
