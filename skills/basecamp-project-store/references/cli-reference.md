# The Basecamp command line — the parts you cannot guess

You can discover the verbs yourself with `basecamp commands --json` and
`basecamp <topic> <action> --help`. **Do that for anything not on this page.** What follows is
only the behaviour that is surprising, silent, or expensive to get wrong.

Every command below also takes `--json` (parse this, not the human output) and `--jq '<expr>'`
(filter without a second tool).

## Four rules that apply to every call

1. **`--account <id>` is required.** Without it the command fails with "account is required",
   even when the project id is unambiguous.
2. **Close standard input: append `< /dev/null`.** Some commands wait on input when they think
   they have a terminal, and then they hang for minutes instead of failing. With input closed
   they return in seconds. This costs nothing when it was not needed.
3. **Pass any body through a file, never inline.** Write the text to a file, then
   `body="$(cat <path>)"` and pass `"$body"`. Text pulled in this way is not re-expanded, so
   `$`, backticks and quotes stay literal. Typing a long body inline mangles it.
4. **Ids come from links for free:** `basecamp url parse "<link>"` splits an
   `app.basecamp.com` link into its account, project and record ids.

## The write verbs have three different shapes — do not assume symmetry

| What | Shape | Note |
| --- | --- | --- |
| Add a todo | `basecamp todos create "<content>" --list <list-id> --account <acc> --in <proj>` | content is **positional**; `--description` carries the long notes |
| Edit a todo | `basecamp todos update <todo-id> --title "<new>" --account <acc> --in <proj>` | `--title` (or a positional title). **`--content` is rejected** |
| Tick a todo | `basecamp todos complete <todo-id> --account <acc> --in <proj>` | `todos uncomplete` undoes it |
| Edit a message | `basecamp messages update <msg-id> --body "$body" --account <acc> --in <proj>` | **`--body`**, and `--title` for the title |
| Comment on anything | `basecamp comments create <record-id> "<content>" --account <acc> --in <proj>` | content is **positional**; `--content` is rejected |

A skill that assumes one shape fails on every edit. Read the row, do not infer it.

## `todos list` ignores a positional id — the silent wrong answer

`basecamp todos list` takes **no positional argument**. Passing a list id as one is accepted
and then ignored, so you get *the whole project's* open todos and believe you got one list's.
On a board with three lists that is the difference between 10 items and 25.

```
basecamp todos list --list <list-id> --account <acc> --in <proj> --json    # one list
basecamp todos list --account <acc> --in <proj> --json                     # whole project
```

Completed todos are **left out by default**, so a count that looks short is usually right; add
`--status completed` (or `--completed`) when you need them.

## Formatting: two things the editor eats

Basecamp's editor renders headings, bold, italics and bullet/numbered lists. It has **no
tables** and **no inline HTML**.

- **A pipe table collapses into a paragraph of literal `|` characters.** Convert every table
  to a bullet list first — one bullet per row, e.g. `- **Espresso** — €2,50`.
- **Raw HTML is silently swallowed** unless it sits inside a fenced code block — and this is
  true in **todo notes as well as message bodies**. Fenced, it survives as readable,
  copy-pasteable escaped text. Unfenced, the tag is simply gone and nothing warns you; you
  find out later when the thing it described was never built.

Both conversions are done for you:

```
python3 ~/.hermes/skills/talents/basecamp-project-store/scripts/project_store.py body --file <path>
```

It rewrites the file in place, prints what it changed, and is safe to run twice.

## Posting a message: draft, read back, publish

1. `basecamp messages create "<title>" "$body" --draft --account <acc> --in <proj> --json`
   — a draft notifies nobody. Note the id it returns.
2. Read it back (`basecamp messages show <msg-id> …`) and confirm no flattened table and no
   missing markup survived.
3. `basecamp messages publish <msg-id> --account <acc> --in <proj> --json`

Publishing only notifies people who are **already** subscribed — a message you created
subscribes only its author, so publishing is not a team-wide alert. Adding a subscriber to an
already-published item does notify them.

## Sharing with a client — company-wide, and irreversible in practice

`basecamp recordings visibility <id> --visible` shares the item with — and notifies —
**everybody at the client company**. There is no per-person client sharing. So:

- Never turn it on without saying that sentence to the owner and getting a clear yes.
- Anything candid (pricing notes, internal reasoning, half-formed plans) stays off a
  client-visible post.
- Turning visibility on **recomputes the subscriber list** and can drop team members you
  already added — so add team subscribers **after** the visibility change, then confirm with
  `basecamp subscriptions show <id> …`.

## Signing in

`basecamp auth login --remote` runs the headless flow: it prints a link and waits for the
callback address to be pasted back. `connect_auth.py` drives both halves — see
[`connect.md`](connect.md).

`--scope full` is accepted, but on accounts that sign in through the 37signals launchpad the
CLI reports that **scopes are ignored** and the token is account-wide regardless. Do not rely
on a read-only scope as a safety boundary; the boundary is the project id in the profile and
the rule that you only ever touch that one. Check the current state with
`basecamp auth status --json` — an expired-looking token often still works, so judge by
whether a call succeeds, not by the label.

## Other useful reads

```
basecamp projects list --account <acc> --json
basecamp todolists list --account <acc> --in <proj> --json
basecamp messages list --account <acc> --in <proj> --json
basecamp search "<keyword>" --account <acc> --json
basecamp upload <path> --account <acc> --in <proj>        # files, e.g. photos, next to the brief
basecamp doctor --verbose                                  # when something is off
```
