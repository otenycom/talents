# Review, export & import a Talent (Oteny Talent Drop)

Telegram can't show a whole multi-file Talent. So to let the owner **read one back in
full**, **export/share** it, or **import** one someone else made, I package the bundle
into an **Oteny Talent Drop**: a `bundle.zip` plus a self-contained `index.html` viewer
(every file rendered, Markdown + code, a Download button) — published with my built-in
`publish_file` ([oteny-drop](../../oteny-drop/SKILL.md)). The viewer link IS the
read-back surface, the export, and the thing others import from.

The helper scripts ship beside this skill:
`~/.hermes/skills/talents/oteny-talent-authoring/scripts/`. They are declared scripts —
run them by path (approval-clean); never paste their logic inline.

## A. Review or export a Talent — do these in order

> Use when the owner says *"show me my <X> Talent"*, *"let me review it"*, *"export
> it"*, *"give me a link to it"*, or *"send it to a friend"*.

1. **Find the slug.** It's the dir name under `~/.hermes/skills/talents/`. List them if
   unsure (`ls ~/.hermes/skills/talents/`). Only the owner's own Talents export this way.
2. **Package it** (sanitizes + zips + manifests in one call):
   ```
   python3 ~/.hermes/skills/talents/oteny-talent-authoring/scripts/package_talent.py --slug <slug> --json
   ```
   This writes an export dir with `bundle.zip`, `manifest.json`, and a sanitized copy.
   It **strips secrets/PII** automatically (a public link is effectively permanent) —
   any seeded `*.db`, `profile.yaml`, `memory.md`, or baked chat/owner id is removed
   *before* anything leaves the box. Note the printed `zip_path` and `out_dir`.
3. **Publish the zip:**
   ```
   publish_file(file_path="<out_dir>/bundle.zip", file_name="<slug>.zip")
   ```
   Keep the returned `url` — that's `ZIP_URL`.
4. **Render the viewer** with that URL so its Download button works:
   ```
   python3 ~/.hermes/skills/talents/oteny-talent-authoring/scripts/render_viewer.py \
     --package "<out_dir>" --zip-url "<ZIP_URL>"
   ```
   It writes `<out_dir>/index.html`.
5. **Publish the viewer:**
   ```
   publish_file(file_path="<out_dir>/index.html", file_name="<slug>.html")
   ```
6. **Reply with the viewer link** (visibly) — that's the one to open or share. Mention
   the zip link too if they asked for a download. For a *private* review, add
   `password="…"` to the viewer's `publish_file` and relay the password.

## B. Import a Talent someone shared

> Use when the owner gives me a Talent drop link or a `.zip` and says *"install this"*.

1. **Install it:**
   ```
   python3 ~/.hermes/skills/talents/oteny-talent-authoring/scripts/import_talent.py --url "<drop link>"
   # or a local file: --zip "/path/to/bundle.zip"
   ```
2. **Read the result.** On success it lands at `~/.hermes/skills/talents/<slug>/`,
   marked **imported / unverified** — it's third-party content I didn't write. It can't
   **shadow an Oteny Talent** (those are refused), and nothing runs at install time.
3. **If it refuses:** the reason says why — the slug already belongs to one of *your*
   Talents (re-run with `--overwrite` to replace it), or it isn't a valid bundle, or the
   slug is Oteny-managed. A traversal-unsafe archive is rejected hard.
4. **Tell the owner** it's installed and unverified, and that they can review it with
   Protocol A (export → open the viewer) before relying on it.

## C. Health-check a Talent (is it share-ready?)

> Use when the owner says *"health report my Talents"*, *"is my &lt;X&gt; Talent ready to
> publish?"*, or before submitting one.

```
python3 ~/.hermes/skills/talents/oteny-talent-authoring/scripts/self_check.py --all --json
# or one: --slug <slug>
```

It sanitizes a copy of each **owner-authored** Talent (never the managed/infra skills) and
grades it against the authoring standard:

- **green** — share-ready (would promote clean).
- **yellow** — clean but with soft warnings (a checklist-first nudge, a stripped baked id);
  publishable, worth polishing.
- **red** — lint violations (e.g. no `agent-profile.yaml`); not share-ready — the `reasons`
  say exactly what to fix.

The definitive grade always re-runs Oteny-side (the nightly sweep + `promote-talent`), so a
`provisional: true` result (the deep rules weren't on this box) is confirmed there.

## D. Publish a Talent (submit it to the Bot Market)

> Use when the owner says *"publish my &lt;X&gt; Talent"* / *"submit it to the store"*.

1. **Self-check first** (Protocol C). A **red** blocks the submit — fix and retry.
2. **Export it** (Protocol A) so the reviewer gets a viewer link — keep the viewer URL.
3. **Submit** (only fires on green/yellow):
   ```
   python3 ~/.hermes/skills/talents/oteny-talent-authoring/scripts/self_check.py \
     --slug <slug> --request-publish --viewer-url "<viewer link>"
   ```
   This writes a publish-request marker the Oteny sweep drains into the **Bot Market review
   queue** (`hh.owner_talent`, `publish_state=submitted`). An operator vets the rendered bundle
   and, on approval, `promote-talent` lifts it into the catalog. Nothing here touches the
   network or the control plane — the box holds no control-plane key; the sweep pulls the marker.
4. **Tell the owner** it's submitted for review (not yet live) and share the viewer link.

## Notes

- **Export only the bundle, never the data.** Packaging reads
  `~/.hermes/skills/talents/<slug>/` only — the owner's data in
  `~/.hermes/data/<slug>/` is never exported. The viewer shows the *method*, not the
  person.
- **The manifest stamps the authoring-standard version** the Talent targeted — that's
  what a future share-readiness lint grades against, so a versioned Talent isn't unfairly
  failed by newer rules.
- **Publishing to the Talent Store is separate** (the `promote-talent` path, Oteny side)
  — see this skill's "Publishing to the Oteny Talent Store" section.
