# Helper Runner (demo)

A worked example of a restricted Talent that ships its own scripts and runs them
through `talent_run`. Read it, copy it, then replace the two helpers with the
scripts your job needs.

What it shows:

- `restrictions.tool_use: true` makes `toolset_contribution` the whole allowlist.
- `talent_run.helpers` names the scripts the model may start. The platform
  mounts one tool, `talent_run`, whose `helper` argument is exactly that list.
- The helpers are stdlib Python, so the bundle ships no `uv.lock`. A helper with
  third-party imports ships `pyproject.toml` + `uv.lock` (lint check 18) and
  runs in the Talent's own runtime.
- The demo also lists `terminal`, on purpose, to show that no toolset name is
  refused: a Talent that lists a shell gets one. A real restricted Talent lists
  the minimum its job needs.

The authoring rule is in
`talent-authoring-standard/references/restricted-talent-pattern.md` §2c, and the
tool contract in `talent-authoring-standard/references/tools-reference.md`
under `talent_run`.
