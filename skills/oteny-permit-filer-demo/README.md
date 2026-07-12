# Permit Filer (demo) — the runnable business-bot reference

A complete, copyable example of a **scoped, portal-filing business bot**: the kind
of Talent that reads a job from a system of record, drives a government-style web
portal, and writes provable results back — without ever fabricating an outcome.
Everything a real one has, at toy scale, against a portal you run yourself.

**What it demonstrates, and where each pattern is explained:**

| In this bundle | The pattern | Explained in |
| --- | --- | --- |
| `agent-profile.yaml` — the minimal locked toolbox, `portal:` tier binding | scope-lock; the stub-double | `business-bot-pattern.md` §2, §5 |
| `permit-filing/SKILL.md` — one `browser_fill_form` call per wizard page, verified next-click | batch-fill | `business-bot-pattern.md` §6; `browser-authoring.md` |
| `permit-filing/references/form-selectors.md` — the shipped selector map (+ how it was derived) | skills ship selectors; snapshots show refs, not CSS | `browser-authoring.md` |
| write-ahead `PENDING-…` → explicit submit → number read off the page | fail-closed + the crash fence | `business-bot-pattern.md` §4 |
| `tests/scenarios/` — a mock-green happy path + a live-only fail-closed probe | scenario grammar; mutually-exclusive classes | `oteny-talent-dev-loop` |
| `scripts/demo_portal.py` — the local portal with an `/_audit` ground-truth endpoint | test against a double you own | `business-bot-pattern.md` §5 |

**Try it in five minutes (no bot needed):**

```
python3 scripts/demo_portal.py --port 8099
```

Open http://127.0.0.1:8099/portal in your browser, click through the wizard, and
read `permit-filing/references/form-selectors.md` against the pages you see —
that's the selector-map discipline in miniature. `GET /_audit` shows the portal's
own record of what was submitted (the ground truth the scenarios assert against).

**Run it as a real bot:** commission a dev bot from this bundle (the
`oteny-talent-dev-loop` recipe), expose the portal over any HTTPS tunnel, and pass
it as the bot's portal double at commission (`spinup_config:
{stub_endpoints: {portal: <your tunnel url>}}` — the platform binds it to
`$OTENY_PORTAL_BASE_URL` on the box). Then seed a row
(`permit-filing/references/first-run.md`) and hand the bot the job.

**What a real business bot changes:** the local sqlite becomes your client's own
system reached over its API seam (declared by your Talent — see
`business-bot-pattern.md` §3), `terminal` drops off the toolbox, the portal's
`real_url`/`fence_hosts` become the real host, and the wizard grows the things
real portals have (login walls → `connect_login`/`browser_request_human`;
search-then-pick interludes → never batched).

**Exact tool parameters and result shapes** for every tool used here:
`talent-authoring-standard/references/tools-reference.md`.
