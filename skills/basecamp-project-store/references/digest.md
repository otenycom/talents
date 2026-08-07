# The daily digest — and why a quiet day posts nothing

The digest is **opt-in**. Nothing is scheduled when the board is connected; you create the job
only when the owner asks for a recurring summary, and you remove it the moment they ask you to
stop.

## The one rule that makes a daily job tolerable

**A run that finds no change sends nothing.** Not "no changes today" — *nothing*. A recurring
job that speaks every day is noise within a week, and noise gets the whole thing switched off.
`project_store.py digest` enforces this for you: it prints `NO-CHANGES` and exits, and you then
send no message at all.

## What "changed" means

`digest` compares the board against what it saw on the previous run (kept in
`~/.hermes/data/basecamp-project-store/digest_state.json`) and reports only:

- todos **completed** since last time, on your own list
- todos **added** to your own list, and any that were **reopened**
- todos whose **notes or comments changed** (the board reports one "last touched" time per
  todo, so say "changed" — do not claim a comment you have not read)
- **new or edited messages** on the board

It never reports on a list you do not own — the same rule as everywhere else in this skill.

The first run has nothing to compare against, so it records the current state and prints
`NO-CHANGES`. That is deliberate: the first digest should not be a dump of the whole board.

## Creating the job

Ask for a time and confirm the timezone you will use, then create one job named **exactly**:

```
Basecamp project digest
```

The name is fixed on purpose — it is what a safety sweep looks for when a copy of this box is
made for testing, so a copy never posts into the real owner's project. Do not rename it, do
not create a second one.

Create it with the **cheap model** and a **bounded turn count** — a digest is summarising, not
reasoning, and an unbounded recurring turn is the fastest way to burn an owner's credit:

- model: `lite`
- maximum turns: `4`

Load `oteny-cron-authoring` for the exact way to register a scheduled job on this box, then
save `digest_chat` and `digest_time` into the profile so you can find and remove the job later.

## The digest message

Keep it to what changed, newest first, and end with what is still open. One short message:

```
Board: <project name>
Done since yesterday: <n>
  • <todo title>
New on the list: <n>
  • <todo title>
Changed: <n>
  • <todo title>
Still open: <n>
```

Link to the board once, at the end. Never paste a whole todo's notes into chat — link to it.

## Stopping it

Remove the job by its exact name, clear `digest_chat` and `digest_time` from the profile, and
confirm in one line. Do not leave a disabled job behind.
