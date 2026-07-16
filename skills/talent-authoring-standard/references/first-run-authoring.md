# First-run authoring — the check-3 mechanics

Detail behind **check 3** in [`../SKILL.md`](../SKILL.md) ("First-run is mechanical,
idempotent, in `references/`, and approval-clean"). Pulled on demand; the body states
each graded rule, this file carries the failure chain it prevents and the worked
examples — read it when authoring a first-run drill or judging a borderline case.

## The drill lives in `references/first-run.md`, not the body (D57)

The first-run drill is pulled only when the guard says NOT-READY — in the `SKILL.md`
body it would sit in context on every load; the body's triage just routes to it. The
drill itself is **copy-paste-exact** (literal commands, no judgement calls), opens with
a **one-line guard** ("setup complete?" — READY ⇒ skip & act), covers **every**
manifest class (create db → intake → register routing/cron), and **loops to a
re-check** → READY.

## Declared scripts only — never improvised exec (D57)

Create the schema via the shipped `scripts/init.sql` (`sqlite3 db < scripts/init.sql`)
or a `scripts/*.py`; **never** an inline `CREATE TABLE`/`python3 -c`/heredoc — Hermes'
approval gate flags improvised exec and the bot stalls on "Command Approval Required".
Schema lives **once** in `scripts/*.sql`. Remediation is **idempotent**:
`CREATE TABLE IF NOT EXISTS`, cron list-first ("create if absent"),
`ON CONFLICT … DO UPDATE` for daily rows.

## Cron jobs pin `model` + `provider` (D40)

Un-pinned, a job resolves from `config.yaml` `model.default` and with none fires
**empty** → router 400 → silent-fail. The planner reads both from `config.yaml` and
passes them on **every** job (`oteny-flatbelly-talent/scripts/provision_cron.py`); the
pin is a **persona alias** (`assistant`/`builder`/`researcher`, D55, fallback
`assistant`), never the raw OpenRouter slug.

## The runtime hard rules (live `food-tracker`)

One `sqlite3` invocation per terminal call; never chain INSERT+SELECT; keep non-ASCII
out of SQL output.

## Readiness scripts: pure-stdlib, never hard-fail (D237)

`selfcheck`/`preflight` run under the tenant's **system `python3`**, which on a cold
tenant may lack `python3-yaml` (or any apt/pip lib). A readiness script must honor its
"always exit 0, never look like a failure" contract even then — degrade to a clean
NOT-READY, never raise a traceback (which makes the model grind on `pip install`). The
canonical `selfcheck.py` reads YAML via a **vendored stdlib fallback**; a container can
only get a baked dep via a disruptive rebase, so the first-run/critical path must not
depend on one. (Non-readiness feature scripts — e.g. a matplotlib dashboard cron — MAY
use a baked dep, declared per check 9.)

## Collapse the per-turn preamble (D38)

The triage's first action is a **single** `preflight`-style call (readiness + clock +
today's state + memory + targets) with hot intents inlined in `SKILL.md` — not 4–5
probe calls + a reference load (live: 67 → 5 calls).
