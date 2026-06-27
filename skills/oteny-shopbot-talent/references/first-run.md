# ShopBot — first-run setup &amp; self-check

**You are here only because the guard printed `NOT-READY`.** Mechanical and idempotent
(declared scripts only — never improvise `python3 -c` or a heredoc; the approval gate
flags those and the bot stalls). The setup GOAL is `../required_artifacts.yaml`;
`selfcheck.py` is the judge.

## Guard (always run first)

```bash
python3 ~/.hermes/skills/talents/oteny-shopbot-talent/scripts/selfcheck.py
```

- `READY` → skip the rest and manage the list.
- `NOT-READY: missing=[…]` → run the remediation for each listed artifact, then re-check.

## Remediation: `sqlite_db` (the shopping list)

The shipped, idempotent `init.sql` owns the schema AND seeds the canonical aisle walk order
(`categories`) + the common store aliases (`store_aliases`) — no manual per-store setup. Run
it once (creates the dir first):

```bash
mkdir -p ~/.hermes/data/oteny-shopbot-talent
sqlite3 ~/.hermes/data/oteny-shopbot-talent/shopping.db < ~/.hermes/skills/talents/oteny-shopbot-talent/scripts/init.sql
```

## Remediation: `profile` (light intake)

Ask (in the tenant's language) and write `~/.hermes/data/oteny-shopbot-talent/profile.yaml`
(template: `../profile/profile.yaml.template`):
1. Your **main supermarket** (the default store new items file under) — e.g. Albert Heijn.
2. (group bots) who is in the **household** sharing the list?
3. Reply **language** (default English) and **timezone**.
4. (optional) a **weekly nudge** time, e.g. `Sat 09:00` — leave blank to skip.

That's all the store setup needed — `shop.py` files each item under its aisle automatically
and learns specialty stores ("... bij slager") as they're mentioned.

Finally render this bot's DOMAIN memory: fill `../profile/memory.md.template`'s
`{{placeholders}}` from `profile.yaml` and write it to
`~/.hermes/data/oteny-shopbot-talent/memory.md`. If `~/.hermes/memories/USER.md` does not
exist yet, also render a small shared identity file there (name / timezone / language).

## Remediation: `routing` (register the channel prompt)

```bash
python3 ~/.hermes/skills/talents/index-reconciler/scripts/index_reconciler.py --apply
```

## `cron` (weekly nudge) — opt-in

Registered only when the owner set `reminders.weekly_shop`. Plan it (list-first) and
register each printed spec via the `cronjob` tool, pinning the printed model + provider:

```bash
python3 ~/.hermes/skills/talents/oteny-shopbot-talent/scripts/provision_cron.py
```

## Re-check

Run the guard again; when `READY`, start managing the shared list.
