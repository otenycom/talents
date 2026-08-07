# Connecting a board

Pulled only when `preflight.py` prints `READY: no` **and** the owner is asking about a
project board. Owners answer in chat; they never run commands.

---

## What you ask the owner

Ask short, one or two messages, until you have:

1. **Which board** — the account and project. If they paste a link like
   `https://app.basecamp.com/<account>/projects/<project>`, you already have both; read the
   ids out of the link and confirm them rather than asking again.
2. **Which list is yours** — the name of the to-do list that is your work queue. Say plainly
   that you will only tick and comment on that one, and read everything else as background.
3. **Which lists you must read before finishing** — the open-questions list, if there is one.
4. **Which messages are the brief** — the post(s) that hold the rules and the literal copy.

You can offer to find 2–4 yourself once you are signed in (step 4 below) and read the names
back for a yes; that is usually faster than making them look them up.

**Say this before you ask them to sign in, in your own words:**

> Signing in gives me your whole Basecamp account, not just this project — Basecamp grants
> access per person, not per project. I will only touch the project you name. If you would
> rather keep it tight, make a separate Basecamp user, invite it to just this project, and
> sign me in as that user instead.

That is a real limitation of Basecamp, not a setting you can fix. Say it, then let them
choose.

---

## Bot notes — the connect drill

### 1. Install the command-line tool

```
bash ~/.hermes/skills/talents/basecamp-project-store/scripts/install_cli.sh
```

Expect `BASECAMP_CLI_INSTALLED <version>`. It downloads the official release for this
machine, checks it against the published checksum, and puts it in `~/.local/bin`. It is
idempotent — a re-run on an already-installed box just prints the version. If it fails,
report the error and stop; do not improvise another install.

### 2. Start the sign-in and relay the link

The sign-in is a browser flow, and the box has no browser — so it runs in two turns.

```
python3 ~/.hermes/skills/talents/basecamp-project-store/scripts/connect_auth.py start
```

It prints `AUTH_URL <link>`. Send that link to the owner with these three lines:

> 1. Open this link and sign in to Basecamp.
> 2. Your browser will land on a page that says it cannot connect — that is expected.
> 3. Copy the whole address from the address bar and paste it back to me.

**Never** post that link, or the address they paste back, anywhere else — not into the board,
not into a group. Both are one-time.

### 3. Finish the sign-in with what they pasted

```
python3 ~/.hermes/skills/talents/basecamp-project-store/scripts/connect_auth.py finish --callback "<what they pasted>"
```

Expect `AUTH_OK`. If it prints `AUTH_FAILED`, the link expired or the paste was partial —
run `connect_auth.py cancel`, then start again from step 2. Do not retry more than twice
without telling the owner what went wrong.

### 4. Learn the board

```
python3 ~/.hermes/skills/talents/basecamp-project-store/scripts/project_store.py boards --account <account-id>
python3 ~/.hermes/skills/talents/basecamp-project-store/scripts/project_store.py lists --account <account-id> --project <project-id>
```

`lists` prints every to-do list and message on the board with its id and name. Read the names
back to the owner and let them say which is the work queue, which are read-only, and which
messages are the brief.

### 5. Save the profile

Write `~/.hermes/data/basecamp-project-store/profile.yaml` from
`profile/profile.yaml.template`, filling:

- `account_id`, `project_id`
- `work_todolist_id` — the one list you own
- `read_todolist_ids` — comma-separated, may be empty
- `brief_message_ids` — comma-separated, may be empty
- `digest_chat`, `digest_time` — leave empty until they ask for a digest

`mkdir -p ~/.hermes/data/basecamp-project-store` first if needed. Render
`~/.hermes/data/basecamp-project-store/memory.md` from `profile/memory.md.template`.

**Do not write anything into `~/.hermes/memories/USER.md`.** That file is the bot's shared
identity and belongs to whatever else the owner runs on this bot; this skill never touches it.

### 6. Re-check, then start

```
python3 ~/.hermes/skills/talents/basecamp-project-store/scripts/preflight.py
```

When it prints `READY: yes`, tell the owner in one line which board you are on and which list
is yours, then read the brief (`project_store.py brief`) and begin.

If `READY: no` persists:

```
python3 ~/.hermes/skills/talents/basecamp-project-store/scripts/selfcheck.py
```
