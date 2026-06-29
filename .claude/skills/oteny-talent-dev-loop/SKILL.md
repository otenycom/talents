---
name: oteny-talent-dev-loop
description: "Run a Talent's test/clone/staging dev loop on Oteny — clone, reload, test, read traces, fix, green, tag. How to use the Oteny dev CLI."
---

# Oteny Talent dev loop

**The full playbook is [`skills/oteny-talent-dev-loop/SKILL.md`](../../../skills/oteny-talent-dev-loop/SKILL.md) — read it now.**
This stub only makes it discoverable as a slash command; `skills/` is the single source of
truth (don't duplicate its content here).

It is the **test/ship rung** + the **Oteny CLI reference**: prove a Talent *behaves* (not just
that it lints) by running it on a disposable, neutralized **clone**, reading the debug traces,
and gating `commit → staging → green/red` before you tag a release. Verbs: `lint-talent` ·
`clone` · `reload` · `test` · `traces` · `logs` · `selfcheck` · `migrate-talent` · `reinit` ·
`reap` (+ the CI `request-staging-run` / `staging-run-status` path).

Read first: [`talent-authoring-standard`](../../../skills/talent-authoring-standard/SKILL.md)
(the rubric) and [`oteny-talent-authoring`](../../../skills/oteny-talent-authoring/SKILL.md)
(create → edit → package → publish). Repo entrypoint: [`AGENTS.md`](../../../AGENTS.md).
