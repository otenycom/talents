# Team logins — one Odoo login per person

Load this page with `skill_view name='odoo-community'
file_path='references/team-logins.md'` when the owner asks for a login for
a person on their team: "Add Sam as a salesperson like Alex", "Give Kim
a website login", "Sam cannot sign in". CrmBot and WebsiteBot send you
here. They do not keep a second copy.

The owner's own login is not this page. That is
[`setup.md`](setup.md).

## What the owner types

| They send | You do |
| --- | --- |
| "Add a login for Sam, like Alex" | Create, with `--like` |
| "Give Kim a website login" | Create, with `--groups` |
| "Sam's password does not work" | Check |
| "Can you make logins?" | Can |

## Bot notes — the script

Every command talks to the Odoo in this box over JSON-2. Never use
`odoo shell` for a login. Never pass a password as an argument: the password
is in an environment variable, and you name that variable with
`--password-env`.

```text
python3 ~/.hermes/skills/talents/odoo-community/scripts/team_login.py can
python3 ~/.hermes/skills/talents/odoo-community/scripts/team_login.py create --login <email> --name "<full name>" --like <login> [--password-env <VAR>]
python3 ~/.hermes/skills/talents/odoo-community/scripts/team_login.py create --login <email> --name "<full name>" --groups <xmlid,...> [--without <xmlid,...>]
python3 ~/.hermes/skills/talents/odoo-community/scripts/team_login.py set-password --login <email> --password-env <VAR>
python3 ~/.hermes/skills/talents/odoo-community/scripts/team_login.py check --login <exactly as typed> --password-env <VAR>
```

The script lowercases the login on `create` and `set-password`. Odoo
matches a login case-sensitively, and a chat client capitalises the first
letter of a message. So `Sam@example.com` in chat becomes the login
`sam@example.com`.

| The script prints | It means |
| --- | --- |
| `CAN_CREATE_USERS yes` / `no` | The key's user may (or may not) make logins |
| `CREATED <login> id=<n>` then `GROUPS <xmlid,...>` | Made. Quote the login and the groups |
| `EXISTS <login>` | That login is there. Use `set-password` |
| `EXISTS_CASE_VARIANT <login>` | The same login with other capitals is there. Do not make a second one |
| `NO_PASSWORD_YET` | Made without a password. Run `set-password` after the link |
| `PASSWORD_SET <login>` then `CHECK_OK` | The password works on this box |
| `CHECK_OK <login>` | That exact login and password sign in |
| `CHECK_FAILED <login>` then a cause line | The sign-in failed. Quote the cause line |
| `LOGIN_CASE_MISMATCH stored=<login>` | The stored login has other capitals than the typed one |
| `PASSWORD_REJECTED` / `LOGIN_NOT_FOUND` / `USER_ARCHIVED` | The measured cause |

## Bot notes — create a login

1. **Who may ask.** Anyone you answer may ask, the same as for every other
   Odoo action. A Talent that needs a narrower rule writes it itself.
2. Run `can`. On `CAN_CREATE_USERS no`, tell the owner the key cannot make
   logins, and stop. Do not ask anyone for a password first.
3. **Order: the email first, then the password link.** Ask for the person's
   email. Do not send a password link before you have the email.
4. Pick the groups. Which groups a person gets is your decision, from what
   the owner asked. "Like Alex" → `--like <Alex's login>`; the script
   copies Alex's groups exactly. Add a group with `--groups`, leave one out
   with `--without`.
5. Send the secure password link: `connect_account` with a label such as
   `Odoo password for Sam` and an env var such as `SAM_ODOO_PASSWORD`.
   Never ask anyone to type a password in chat.
6. When `credential_status` for that env var is `delivered` or
   `process_ready`, run `create … --password-env SAM_ODOO_PASSWORD`. If the
   user already exists (`NO_PASSWORD_YET` earlier), run `set-password`.
7. Expect `CHECK_OK`. Then tell the owner the login, the groups the script
   printed, and that the person signs in with the login in lowercase.
8. **Release the secret.** After `CHECK_OK`, call `disconnect_account` with
   the variable name (for example `SAM_ODOO_PASSWORD`). The box must not
   keep a person's Odoo password. Do not write the variable name into
   memory.

## Bot notes — "it still fails"

1. Ask which email the person typed on the login page. Never ask for the
   password.
2. Run `check --login <that exact string>` with the password variable, if
   it is still on the box. Do not change the capitals of the typed string.
3. Quote the cause line the script printed. On `LOGIN_CASE_MISMATCH`, tell
   the person to type the stored login. On `PASSWORD_REJECTED`, send a new
   password link (step 5 above), then `set-password`.
4. Never rotate a password that just passed `check`. Never state a cause
   that no check printed this turn.

## Bot notes — the public site

1. Never sign in on the public site with a script. A script that calls the
   public URL meets the edge's bot check, which answers a plain script with
   `403`. That `403` is not a wrong password.
2. For "is the site up", use `list_hosted_websites` and read
   `edge_reachable`.
