---
name: talent-authoring-standard
description: "Author or grade an Oteny Talent bundle — the rubric + the lint rules that gate every PR and delivery."
---

# Talent authoring standard

**The full rubric is [`skills/talent-authoring-standard/SKILL.md`](../../../skills/talent-authoring-standard/SKILL.md) — read it now.**
This stub only makes it discoverable as a slash command; `skills/` is the single source of
truth (don't duplicate its content here).

It is the **standard a Talent must meet** — numbered, verifiable do-lists (the airline-pilot
checklist rule), upgrade-safety, lean authoring — plus the `scripts/lint_upgrade_safe.py` /
`lint_tools.py` checks that enforce it. The **same** lint gates your PR, Oteny's delivery, and
the on-device self-check, so a clean local run means no surprise rejection. Pair it with the
how-to [`oteny-talent-authoring`](../../../skills/oteny-talent-authoring/SKILL.md) and the
[`oteny-talent-dev-loop`](../../../skills/oteny-talent-dev-loop/SKILL.md). Repo entrypoint:
[`AGENTS.md`](../../../AGENTS.md).
