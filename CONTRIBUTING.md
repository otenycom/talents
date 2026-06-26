# Contributing a Talent

Thanks for building on Oteny. A **Talent** is a self-contained bundle under
`skills/<name>-talent/`: an `agent-profile.yaml` (the persona + which skills load),
the skills themselves, optional `references/`, and a `scripts/selfcheck.py` first-run
judge. Write it against the **[talent-authoring-standard](skills/talent-authoring-standard)**
and follow the **[oteny-talent-authoring](skills/oteny-talent-authoring)** how-to.

## Before you open a PR

Run the same gate Oteny runs at delivery — there are no surprise rejections:

```bash
python skills/talent-authoring-standard/scripts/lint_upgrade_safe.py skills/<your>-talent
# exit 0 = pass, 1 = fail. Add --json for machine-readable output.
```

The CI workflow ([`.github/workflows/talent-lint.yml`](.github/workflows/talent-lint.yml))
runs this on every PR.

## What we check

- **The standard** — numbered, verifiable do-lists; lean authoring; the
  checklist-first structure the rubric grades.
- **Upgrade-safety** — no seeded databases, no hardcoded per-tenant identifiers, no
  state that a re-delivery would clobber (the lint enforces this statically).
- **Provenance & trust** — a reviewer verifies a Talent before it is marked
  **Verified** in the store. GitHub is the transport; the review is the trust
  authority. A merged-but-unverified Talent lists as **Community**.

## Licensing

By contributing you agree your Talent is licensed under **Apache-2.0** (this repo's
licence). If you want to ship a **paid** Talent under a commercial licence instead,
open an issue first — that path is handled separately from this open catalog.
