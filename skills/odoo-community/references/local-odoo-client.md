# Local Odoo client — the on-demand fallback

Load this page with `skill_view name='odoo-community'
file_path='references/local-odoo-client.md'` when the owner's ask is a model,
a record, a view, or local SQL that the active Talent's own table does not
name. CrmBot captures leads. WebsiteBot builds the site. This page talks to
the Odoo already on the box for everything else. Do not load it on a booth
capture or a site build — those stay on the consumer's own script.

This page does not install Odoo. Setup lives in
[`references/setup.md`](setup.md) and [`references/first-run.md`](first-run.md).
Load one of those only when the owner asked to set up, or when `ENGINE` is
missing.

## What the owner types

| They send | You do |
| --- | --- |
| "Which models match partner?" / "Show fields on crm.lead" | Inspect |
| "What views does res.partner have?" | Inspect views |
| "Find partners named …" / "Read record …" | Read |
| "Create a record …" / "Set the phone on …" | Write (confirm first) |
| "Delete record …" | Unlink (confirm first) |
| "Run this SQL …" / "What's in ir_ui_view for …" | SQL (confirm if not SELECT) |
| "Is Odoo up?" | Preflight only |

## Triage first

If the active Talent already ran its own `preflight.py` this turn, use that
turn's `ENGINE` / `JSON2` reading — do not run a second preflight. Only when
no preflight ran this turn:

```text
python3 ~/.hermes/skills/talents/odoo-community/scripts/preflight.py
```

`ENGINE: missing` or `JSON2: down` sends you to setup, not to the scripts
below.

## Bot notes — Inspect

Models:

```text
python3 ~/.hermes/skills/talents/odoo-community/scripts/list_models.py --match partner
```

Fields on one model:

```text
python3 ~/.hermes/skills/talents/odoo-community/scripts/list_fields.py --model res.partner
```

Views on one model:

```text
python3 ~/.hermes/skills/talents/odoo-community/scripts/list_views.py --model res.partner
```

Add `--type form` or `--full` when they asked for the arch.

Quote the printed rows. Do not invent a model name. If the script prints
`ok: false`, say the error and stop.

## Bot notes — Read

No id yet — search. Domain is JSON on stdin or `--domain`:

```text
echo '{"domain":[["name","ilike","<name>"]],"fields":["name","email","phone"]}' | python3 ~/.hermes/skills/talents/odoo-community/scripts/crud.py search --model res.partner
```

Known ids — read:

```text
python3 ~/.hermes/skills/talents/odoo-community/scripts/crud.py read --model res.partner --ids <id> --fields name,email,phone
```

Count only:

```text
echo '{"domain":[]}' | python3 ~/.hermes/skills/talents/odoo-community/scripts/crud.py count --model res.partner
```

Quote `ids` and rows the script printed this turn. Do not invent them.
Prefer JSON-2 over SQL for record reads.

## Bot notes — Write

1. Resolve the model and the ids with Read first when they are missing.
2. Show the vals in chat. Ask for the owner's yes once, unless this
   message already is one.
3. Then run one of:

```text
echo '{"vals":{"name":"<name>"}}' | python3 ~/.hermes/skills/talents/odoo-community/scripts/crud.py create --model res.partner --confirm
echo '{"vals":{"phone":"<phone>"}}' | python3 ~/.hermes/skills/talents/odoo-community/scripts/crud.py write --model res.partner --ids <id> --confirm
python3 ~/.hermes/skills/talents/odoo-community/scripts/crud.py unlink --model res.partner --ids <id> --confirm
```

4. Confirm only an id the script printed this turn. If `ok` is false, say
   the error — do not invent a success.

A method `crud.py` does not wrap:

```text
echo '{"model":"res.partner","method":"name_search","name":"<query>","limit":8}' | python3 ~/.hermes/skills/talents/odoo-community/scripts/rpc.py
```

`create` / `write` / `unlink` through `rpc.py` still need the owner's yes
first — pass `"confirm": true` in that JSON.

## Bot notes — SQL

Prefer JSON-2. SQL is only for the local Community database (preflight `DB`
not `-`).

```text
echo '{"sql":"SELECT id, model, name FROM ir_model WHERE model ILIKE '\''%partner%'\'' LIMIT 20"}' | python3 ~/.hermes/skills/talents/odoo-community/scripts/sql.py
```

Mutating SQL needs the owner's yes, then `"confirm": true`. The script
refuses password / `api_key` columns and `DROP DATABASE`.

## Safety boundary

- Never post a password, API key, or connection string. Offer the secure
  intake link instead.
- Confirm before create, write, unlink, and mutating SQL.
- Quote only a record id, a count, or rows a script printed this turn.
- JSON-2 `create` returns a list. The scripts unwrap it — do not send a
  list as a Many2one id.
- Keep `--match` on `list_models.py`; a script named `search_*` or a
  `--query` flag reads as a web lookup to the gateway.
