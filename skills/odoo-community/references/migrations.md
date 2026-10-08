# In-box migrations — odoo-community

`ODOO_COMMUNITY_MIGRATIONS: pending — <id>` in a module Talent's preflight
sends you here. Run each pending migration below, in order. Then continue the
owner's message. Each migration is safe to run again: a second run finds
nothing and changes nothing.

Mark a migration done only after its script printed the "done" line this turn:

```
python3 ~/.hermes/skills/talents/odoo-community/scripts/migrate.py --mark <id>
```

## lowercase-logins

Odoo matches a login case-sensitively. A login that holds a capital, for
example `Sam@example.com`, fails when the person types
`sam@example.com` on the login page. New logins are lowercase already. This
migration fixes the logins that are older.

1. Run
   `python3 ~/.hermes/skills/talents/odoo-community/scripts/team_login.py lowercase-all`
2. Read the output:
   - `LOWERCASED <old> -> <new>` — that login changed.
   - `TWIN <old> <twin>` — a lowercase twin already exists. The script
     changed neither user, because two people or two accounts may hide
     behind the pair. Only a person can tell.
   - `ADMIN_FILE_UPDATED <path>` — the stored owner login now matches.
   - `LOWERCASE_DONE changed=<n> twins=<m>` — the run is done.
   - `LOWERCASE_NOTHING_TO_DO <reason>` — this box has no Odoo or no key.
     The run is done.
   - `LOWERCASE_LATER odoo_down` — Odoo is on this box but does not answer.
     Do not mark. Stop here; the next turn runs it again.
   - `TEAM_LOGIN_FAILED …` — say the error. Do not mark.
3. If any login changed, tell the owner in one sentence which logins
   changed, and that those people now type their login in lowercase. If a
   `TWIN` line printed, name the pair and ask the owner which account is
   right. Do not merge or delete either user yourself.
4. On `LOWERCASE_DONE` or `LOWERCASE_NOTHING_TO_DO`, mark it:
   `python3 ~/.hermes/skills/talents/odoo-community/scripts/migrate.py --mark lowercase-logins`

Passwords are not touched. The default `admin` login is lowercase already.
