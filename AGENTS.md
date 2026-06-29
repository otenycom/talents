# Oteny Talents — agent guide

> The agent-facing twin of [`README.md`](README.md). If you are an **AI coding agent**
> (Claude Code, Cursor, Codex, …) working in this repo on behalf of a Talent author, read
> this first. The README is the human on-ramp; this is yours. Both point at the same skills —
> the skills are the single source of truth.

You are working in the **open catalog of Talents** for [OtenyBot](https://oteny.com). A
**Talent** is a self-contained bundle under `skills/<name>-talent/` — a persona
(`agent-profile.yaml`), the markdown skills the bot reads, optional `references/`, a
`scripts/selfcheck.py` first-run judge, and (if it does anything outbound) a `neutralize.yaml`.
Your job is usually one of three: **author** a Talent, **test/ship** one, or **publish** it.

Everything here is **Apache-2.0** and cross-platform. The Oteny platform that hosts and runs
these Talents is proprietary and is **not** in this repo — treat it as a black box you reach
through the Oteny CLI / `/json/2/`, scoped by the author's own account key.

## Read these skills first (don't reinvent them)

Three author skills live under `skills/`. They are the playbooks — invokable here as slash
commands (`.claude/skills/` stubs point into them) and linked below. **Read the one that
matches your task before you touch a bundle.**

| Task | Skill | Read |
| --- | --- | --- |
| Know the **rules** a Talent must satisfy (the rubric + the lint that enforces it) | `talent-authoring-standard` | [`skills/talent-authoring-standard/SKILL.md`](skills/talent-authoring-standard/SKILL.md) |
| **Create / edit / package / publish** a Talent, step by step | `oteny-talent-authoring` | [`skills/oteny-talent-authoring/SKILL.md`](skills/oteny-talent-authoring/SKILL.md) |
| **Test / clone / debug / ship** — prove it *behaves*, not just that it lints; **how to use the Oteny dev CLI** | `oteny-talent-dev-loop` | [`skills/oteny-talent-dev-loop/SKILL.md`](skills/oteny-talent-dev-loop/SKILL.md) |

Newcomer's narrative walk-through: [`docs/writing-a-talent.md`](docs/writing-a-talent.md). The
full tool catalog a Talent may request: [`TOOLS.md`](TOOLS.md).

## The dev loop — how to use the Oteny CLI

Linting proves a bundle is well-formed; it **never sends the bot a message**. To prove
behavior you stand the Talent up on a real, disposable, **neutralized clone** of a bot and run
its `tests/scenarios/*.yaml` against it, then read the bot's debug traces:

```
lint-talent → clone → reload (your branch) → test → traces → fix → green → tag a release
```

The CLI verbs (every one returns a JSON DTO; non-zero exit on failure) — full table + rules in
[`oteny-talent-dev-loop`](skills/oteny-talent-dev-loop/SKILL.md):

| Step | Verb |
| --- | --- |
| offline gate (run before you ever clone) | `lint-talent --dir <bundle>` |
| stand up a disposable, neutralized, budgeted clone of a **permitted** source | `clone --from <source> --bundle <slug> --branch <dev> --byob <token-file>` |
| deliver your pushed branch to the clone | `reload --ref <clone>` |
| run the bundle scenarios LIVE → green/red | `test --ref <clone> --bundle <slug>` |
| the structured per-turn debug trace (your debugging eye) | `traces --ref <clone>` |
| `logs` · `selfcheck` · `migrate-talent` · `reinit` · `reap` | see the skill |

CI path: `request-staging-run --source-id <id> --commit <sha>` → poll `staging-run-status`.

**Availability (be honest with the author):** the lint, the offline behavioral scenarios, and
the pre-commit gate below are runnable by **anyone, today**. The live `clone → test → traces`
CLI loop is currently driven by **Oteny + trusted partners**; one-push self-serve
`commit → staging → green/red` is rolling out. Don't tell an author to run a verb they can't
yet reach — gate behavior with the offline scenarios + lint in the meantime.

## Before you open a PR — run the gate

Same checks CI runs, so there are no surprise rejections (see [`CONTRIBUTING.md`](CONTRIBUTING.md)):

```bash
# one-time: install the local pre-commit gate (same checks as CI)
pip install pre-commit && pre-commit install
# the authoritative lint Oteny also runs at delivery:
python skills/talent-authoring-standard/scripts/lint_upgrade_safe.py skills/<your>-talent
# exit 0 = pass, 1 = fail; add --json for machine output
```

`python scripts/precommit_checks.py` runs the full gate on demand (bundle unit tests, offline
scenarios, both lints). CI: [`.github/workflows/talent-lint.yml`](.github/workflows/talent-lint.yml)
+ [`bundle-tests.yml`](.github/workflows/bundle-tests.yml).

## Hard rules — don't break these

- **`skills/` is the single source of truth.** The `.claude/skills/` and `.cursor/rules/`
  entries are thin **pointers** into it — never duplicate skill content into them, and never
  let them drift. Edit the canonical file under `skills/`.
- **Upgrade-safety.** No seeded databases, no hardcoded per-tenant identifiers, no state a
  re-delivery would clobber. The lint enforces this statically — a Talent is **content bounded
  by the platform**, not a place to smuggle infrastructure.
- **Neutralize is mandatory for anything outbound.** If a Talent sends email, hits an external
  API, or runs an outbound cron, it **must** ship a `neutralize.yaml` (the lint enforces it) so
  a test clone is safe before it serves a turn.
- **`TOOLS.md` / `tools-catalog.md` is generated by Oteny — never hand-edit it.** Request tools
  in `agent-profile.yaml` (`tools.required` / `toolset_contribution`); the lint fails a Talent
  that stubs a tool which is actually live.
- **Scope.** Through the CLI / `/json/2/` you may touch only the author's **own** bots, Oteny
  demo/template bots, and bots explicitly **granted** — never an arbitrary customer's tenant. A
  clone lands with third-party secrets redacted; you can't extract another tenant's credentials.
- **Tests are author-only.** A bundle's `tests/` is never delivered to a bot.

## Map

```
skills/
├── talent-authoring-standard/   the RUBRIC + the lint rules that enforce it
├── oteny-talent-authoring/      the HOW-TO: create → edit → package → publish
├── oteny-talent-dev-loop/       the TEST/SHIP loop + the Oteny CLI verbs
├── *-talent/                    the reference Talents — read as worked examples
└── _shared/                     scripts every bundle reuses byte-identical
tests/                           the catalog's own unit + scenario tests (CI runs per PR)
docs/writing-a-talent.md         newcomer's guide
TOOLS.md                         the (generated) catalog of tools a Talent may request
```
