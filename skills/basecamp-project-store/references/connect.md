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

You can offer to find 2–4 yourself once you are connected (step 3 below) and read the names
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

Expect `BASECAMP_CLI_INSTALLED <version>` and `BASECAMP_MANUAL <path>`. It downloads the
pinned official release for this machine, checks it against the published checksum, puts it
in `~/.local/bin`, and has the tool write its own version-matched manual to
`~/.agents/skills/basecamp/SKILL.md` — that is where you look up any verb this skill does not
spell out. It is idempotent — a re-run on an already-installed box just prints the version. If
it fails, report the error and stop; do not improvise another install.

### 2. Ask Oteny for a sign-in link — one link, nothing to paste

Call the tool:

```
oauth_connect(provider="basecamp")
```

Send the owner the `url` it returns, with these two lines:

> 1. Open this link and sign in to Basecamp.
> 2. That is all — I will tell you as soon as I am connected.

Then **end your turn.** The owner signs in, Basecamp redirects to Oteny, and Oteny completes
the exchange and hands you the access token. You are messaged when it lands. Do not poll, and
do not ask them for anything from their address bar — with this link there is nothing there
for you to want.

**Never post that link anywhere else** — not into the board, not into a group. It is
one-time and it is theirs.

**If `oauth_connect` refuses with an unknown provider**, Oteny has not registered a Basecamp
app on this deployment yet. Say so plainly — "I can't connect to Basecamp yet on this bot;
I've flagged it" — and stop. Then read the fallback below, and use it only if the owner asks
you to try anyway.

### 3. Learn the board

Reading the board's shape is the command-line tool's own job — ask it directly:

```
~/.local/bin/basecamp projects list --account <acc> --json --jq '.data[] | "\(.id)\t\(.name)"'
~/.local/bin/basecamp todolists list --account <acc> --in <proj> --json --jq '.data[] | "\(.id)\t\(.name)\t\(.completed_ratio)"'
~/.local/bin/basecamp messages list --account <acc> --in <proj> --json --jq '.data[] | "\(.id)\t\(.subject)"'
```

That gives every to-do list and message on the board with its id and name. Read the names back
to the owner and let them say which is the work queue, which are read-only, and which messages
are the brief.

### 4. Save the profile

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

### 5. Re-check, then start

```
python3 ~/.hermes/skills/talents/basecamp-project-store/scripts/preflight.py
```

When it prints `READY: yes`, tell the owner in one line which board you are on and which list
is yours, then read the brief (`project_store.py brief`) and begin.

If `READY: no` persists, or a call is refused although you appear signed in:

```
python3 ~/.hermes/skills/talents/basecamp-project-store/scripts/connect_auth.py status
```

That is the only verb that tells you the truth. `SIGNED_IN` says whether a credential is
configured, `SOURCE` says where it came from (`oteny` = leased by the platform), and `WORKS`
is a real call to Basecamp. `SIGNED_IN: yes` with `WORKS: no` means the token was revoked or
expired — go back to step 2 and connect again.

---

## Fallback — the tool's own sign-in, only when Oteny has no Basecamp app

Use this **only** after `oauth_connect` refused with an unknown provider, and only if the
owner asks you to try anyway. Tell them the cost first, in your own words:

> There's a rougher way in: you'd sign in, land on a page that can't connect, and copy the
> whole address back to me here in chat. That address is a one-time key, so it would sit in
> our conversation. I'd rather wait until Oteny finishes the proper connection — your call.

If they say go ahead:

```
python3 ~/.hermes/skills/talents/basecamp-project-store/scripts/connect_auth.py start
```

It prints `AUTH_URL <link>`. Send the link and tell them to open it, sign in, and copy the
whole address bar back. Then, **in the same sitting** — the tool holds the sign-in open for
about five minutes and no longer:

```
python3 ~/.hermes/skills/talents/basecamp-project-store/scripts/connect_auth.py finish --callback "<what they pasted>"
```

Expect `AUTH_OK`. On `AUTH_FAILED` the five minutes ran out or the paste was partial: run
`connect_auth.py cancel`, then start again from the top of this section. Do not retry more
than twice without telling the owner what went wrong.

Never post the link, or the address they paste back, anywhere else. Both are one-time, and
both are secrets for as long as they live.
