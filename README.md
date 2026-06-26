# Oteny Talents

The open catalog of **Talents** for [Oteny](https://oteny.com) — your own private
AI assistant on Telegram. A **Talent** is open content: a persona plus a set of
skills (a tool *request* + instructions) that gives your OtenyBot a focused role —
a flat-belly coach, a stock-research analyst, a travel concierge.

A Talent is **content, never capability**. The Oteny platform runs every Talent
inside a scope-locked harness, so a Talent is safe by construction no matter what
it says. That is why this catalog is **open** ([Apache-2.0](LICENSE)) — browse it,
learn from it, and contribute your own.

> Browse the live store at **[oteny.com/talents](https://oteny.com/talents)**.
> Want to write one? Start at **[oteny.com/talents/build](https://oteny.com/talents/build)**.

## What's here

```
skills/
├── talent-authoring-standard/   the rubric a Talent must meet (+ the lint rules)
├── oteny-talent-authoring/      the how-to: create → edit → package → publish
├── oteny-flatbelly-talent/      a private flat-belly coach
├── oteny-stock-talent/          terse, numbers-first stock research
└── oteny-travel-talent/         a private travel concierge
```

Each marketable Talent is a self-contained bundle: an `agent-profile.yaml`
(persona + which skills load), the skills themselves, `references/`, and a
`scripts/selfcheck.py` first-run judge. Some bundle docs link to **Oteny platform
skills** (e.g. `index-reconciler`, `skill-translator`) that run on your OtenyBot's
machine and apply the Talent's routing — those live on the platform, not in this
catalog, so a few in-bundle links resolve only once the Talent is delivered.

## Build a Talent

1. **Read the standard** — [`skills/talent-authoring-standard/`](skills/talent-authoring-standard)
   is both the rubric a bundle must meet *and* the checks a capable model applies to
   grade one (numbered, verifiable do-lists — the "airline-pilot checklist" rule).
2. **Follow the how-to** — [`skills/oteny-talent-authoring/`](skills/oteny-talent-authoring)
   walks create → edit → package → publish, with helper scripts.
3. **Self-check before you submit** — run the same gate Oteny runs at delivery:

   ```bash
   python skills/talent-authoring-standard/scripts/lint_upgrade_safe.py skills/<your>-talent
   ```

   Exit `0` = pass, `1` = fail. CI ([`.github/workflows/talent-lint.yml`](.github/workflows/talent-lint.yml))
   runs this on every PR, so the same rules gate your PR, Oteny's delivery, and the
   on-device self-check — no surprise rejections.
4. **Open a PR.** See [CONTRIBUTING.md](CONTRIBUTING.md).

## Licensing

This catalog is **Apache-2.0** (see [LICENSE](LICENSE) + [NOTICE](NOTICE)) — open
content, contribute freely. The Oteny platform that hosts and runs these Talents is
proprietary and is not part of this repo. Paid third-party Talents may ship under a
separate commercial licence, and a business's private Talents are not published here.
