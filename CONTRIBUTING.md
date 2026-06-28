# Contributing a Talent

Thanks for building on Oteny. A **Talent** is a self-contained bundle under
`skills/<name>-talent/`: an `agent-profile.yaml` (the persona + which skills load),
the skills themselves, optional `references/`, and a `scripts/selfcheck.py` first-run
judge. Write it against the **[talent-authoring-standard](skills/talent-authoring-standard)**
and follow the **[oteny-talent-authoring](skills/oteny-talent-authoring)** how-to.

## Enable the local gate (once)

The repo ships a **pre-commit hook** that runs the *same* checks CI runs — the bundle unit
tests (PII-clean, teaser schema, selfcheck parity, …), the offline behavioral scenarios, and
the two Talent lints — so a red change is caught before it leaves your machine instead of on
CI after the fact. Turn it on once:

```bash
pip install pre-commit && pre-commit install
```

After that every `git commit` runs the gate and blocks on a failure. To run it on demand
(no install required) use `python scripts/precommit_checks.py`, or
`pre-commit run --all-files`. In a genuine emergency `git commit --no-verify` bypasses it —
CI still gates the push.

## Before you open a PR

1. **Lint** — run the same gate Oteny runs at delivery, so there are no surprise rejections:

   ```bash
   python skills/talent-authoring-standard/scripts/lint_upgrade_safe.py skills/<your>-talent
   # exit 0 = pass, 1 = fail. Add --json for machine-readable output.
   ```

   The CI workflow ([`.github/workflows/talent-lint.yml`](.github/workflows/talent-lint.yml))
   runs this on every PR.

2. **Prove it behaves** — linting never sends the bot a message, so back it with
   behavioral tests in `tests/scenarios/*.yaml` and run them through the
   **[oteny-talent-dev-loop](skills/oteny-talent-dev-loop)** (clone → test → traces). A green
   run is what pre-clears the human review below.

## What we check

- **The standard** — numbered, verifiable do-lists; lean authoring; the
  checklist-first structure the rubric grades.
- **Upgrade-safety** — no seeded databases, no hardcoded per-tenant identifiers, no
  state that a re-delivery would clobber (the lint enforces this statically).
- **Provenance & trust** — a reviewer verifies a Talent before it is marked
  **Verified** in the store. GitHub is the transport; the review is the trust
  authority. A merged-but-unverified Talent lists as **Community**; a clean automated test
  run (the dev loop above) auto-grades it and can pre-clear the human review. Community
  flags can quarantine a listing, and the store sorts by reputation — so honest, well-tested
  Talents rise.

## Licensing

By contributing you agree your Talent is licensed under **Apache-2.0** (this repo's
licence). If you want to ship a **paid** Talent under a commercial licence instead,
open an issue first — that path is handled separately from this open catalog.
