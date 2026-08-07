# The Basecamp command line — only what its own manual gets wrong or leaves out

The tool ships **its own agent manual**, installed beside it and matched to its exact version:

```
~/.agents/skills/basecamp/SKILL.md          # the verbs, the flags, the JSON contract
~/.agents/skills/basecamp/.installed-version
```

That file is the reference for **anything not on this page** — every verb, every flag, mentions,
attachments, pagination, error codes. It is long (about 70 KB), so read it when you need a verb
you do not know, not as a matter of course. Faster still for one command:

```
~/.local/bin/basecamp <topic> <action> --help
~/.local/bin/basecamp <topic> --agent --help      # the same thing as JSON
```

**This page is the delta**: the handful of behaviours where the tool's own manual is silent or
wrong, each one checked against the pinned version on a live board. Everything here costs real
work when guessed.

**Call the tool by its full path, `~/.local/bin/basecamp`.** That directory is on a login
shell's PATH but not on the plain shell a tool call usually gets, so a bare `basecamp …` fails
with "command not found" on exactly the box where it is installed. If `preflight.py` reports a
different `CLI:` path, use the one it printed.

## 1. `--account <id>` is required — and its own manual never says so

Every command needs it, even when the project id is unambiguous; without it you get
`--account is required (or set account_id in config)`. The tool's manual assumes the account
sits in a config file and so never mentions the flag. Pass it every time.

## 2. `todos list` takes no positional id — passing one silently widens the answer

A list id given as a bare argument is accepted and then **ignored**, so you get the whole
project's todos believing you got one list's. On a three-list board that was 27 items instead
of 7.

```
~/.local/bin/basecamp todos list --list <list-id> --account <acc> --in <proj> --json   # one list
~/.local/bin/basecamp todos list --account <acc> --in <proj> --json                    # everything
```

Completed todos are left out by default; `--status completed` (or `--completed`) returns them
and really does filter on the pinned version.

## 3. `messages create` has no `-` stdin argument — piping posts an EMPTY message

`comments create` reads content from stdin and documents `-` as the "read stdin" argument.
**`messages create` does neither.** Its body is a plain optional positional, so `-` is taken
as the literal body: the piped text is dropped without a word and the board gets a message
whose whole body is one empty bullet. Nothing in the output says so.

```
printf '%s' "$body" | basecamp messages create "T" -     # WRONG — posts an empty message
~/.local/bin/basecamp messages create "T" "$body" …      # right — body as an argument
```

So pass a message body as an argument, read from a file: `body="$(cat <path>)"`, then
`"$body"`. Text pulled in that way is not re-expanded, so `$`, backticks and quotes stay
literal.

## 4. Markdown renders — until one raw HTML tag turns the whole body literal

A markdown body is converted to rich text on `messages create`, `messages update --body` and
`todos create/update --description` alike. Headings, bullets **and pipe tables** all render
(a table becomes a real table — do not pre-flatten it into bullets).

That holds only while the body is markdown. **One raw HTML tag anywhere flips the entire body
into pass-through HTML**, and then nothing else in it renders: the table posts as a paragraph
of literal bars, the bullets as hyphens, the heading as a hash. The tag itself renders as
markup, so it is invisible to whoever reads the board — you find out later, when the thing it
described was never built.

Fence it and both halves are fixed — the rest of the body renders, and the tag survives inside
a code block as readable, copy-pasteable escaped text. That is all `body` does now:

```
python3 ~/.hermes/skills/talents/basecamp-project-store/scripts/project_store.py body --file <path>
```

It rewrites the file in place, prints what it fenced, and is safe to run twice.

## 5. Signing in is a two-turn relay — `--device-code` is not a way out

`auth login --remote` prints a link and then **blocks**, waiting for the address the browser
lands on to be pasted back. `--device-code` looks like an escape from that and is not: it is
the same headless paste-back flow under another name (0.7.x said so outright — "alias for
`--remote`"; 0.9.0 dropped the phrase without changing the behaviour). There is no poll-based
device flow, so no version of this completes in one command call.

That is why `connect_auth.py` parks the waiting half in a detached supervisor — it is the only
way the flow can span two chat turns. See [`connect.md`](connect.md).

`--scope full` is accepted, but on accounts that sign in through the 37signals launchpad the
scope is ignored and the token is account-wide regardless. Do not treat a read-only scope as a
safety boundary — the boundary is the project id in the profile and the rule that you only ever
touch that one.

## 6. Client visibility is company-wide, and it rewrites the subscriber list

`~/.local/bin/basecamp recordings visibility <id> --visible` shares the item with — and
notifies — **everybody at the client company**. There is no per-person client sharing.

- Never turn it on without saying that sentence to the owner and getting a clear yes.
- Anything candid (pricing notes, internal reasoning, half-formed plans) stays off a
  client-visible post.
- Turning it on **recomputes the subscriber list** and can drop team members you already added
  — so add team subscribers **after** the visibility change, then confirm with
  `~/.local/bin/basecamp subscriptions show <id> …`.

## Checking this page is still true

The tool moves, and every claim above was true of one version. `check_upstream.py` re-runs each
one against a scratch board and prints HOLDS or BROKEN per item — run it whenever the pinned
version is bumped, and fix this page from what it prints rather than from the release notes:

```
python3 ~/.hermes/skills/talents/basecamp-project-store/scripts/check_upstream.py \
    --account <acc> --project <scratch-proj> --list <scratch-list>
```
