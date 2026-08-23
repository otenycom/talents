# `connections:` — how a Talent names the systems it needs

A Talent declares every outside system it touches as a **named connection** in
`agent-profile.yaml`. The name is the whole contract. A tool call passes it, the
platform binds environment variables from it, the readiness gate judges it, and the
owner sees it under that name on their own Connections page.

```yaml
connections:
  crewradar:                   # kind: odoo    — the business's own Odoo
    kind: odoo
    uplink_user: hr.otenybot
    odoo_grants:
      read:  [res.partner]
      write: [res.partner]
  permits:                     # kind: portal  — a website the browser plane drives
    kind: portal
    real_url: https://permits.example.org
    fence_hosts: [permits.example.org]
  basecamp:                    # kind: saas    — a third-party account the owner grants
    kind: saas
    provider: basecamp
    scopes: [projects, todos]
    env:
      BASECAMP_TOKEN: access_token
    required: true
```

There are four kinds, and `odoo_json2` is accepted as a synonym for `odoo`. **Anything
else is skipped in silence.** A typo in `kind:` does not raise: the Talent ships, loads,
and answers as though it had a data plane it never got. The authoring lint refuses an
unknown kind for exactly that reason, so a typo is a red pull request rather than a
customer's broken bot.

## `kind: saas` — an account the owner has to grant

The other three kinds say *bind this*. `kind: saas` says *this Talent cannot work until
the owner has granted us an account*. Nothing on the box can create that account. The
owner grants it once, in a browser, and the platform then leases the credential to the
box on every gateway start.

| Field | Meaning |
|---|---|
| `provider` | The provider code the platform has registered, lower case (`basecamp`). |
| `scopes` | The scopes to ask for, where the provider has them. Display only. |
| `env` | `ENV_VAR: payload_field` — the variables your scripts read. |
| `required` | `true` gates readiness on the grant. Defaults to `false`. |

### The rules the platform enforces, so check them here first

The registry refuses a binding that breaks any of these, and it refuses it at grant
time — long after your pull request merged. The lint mirrors each one:

- An environment variable is `UPPER_SNAKE_CASE`, 3 to 64 characters, and starts with a
  letter.
- It may not be a name the platform manages (anything starting `OTENY_` or `TELEGRAM_`,
  plus a short list of others). The one carve-out is the `OTENY_CONN_` namespace.
- A payload field is lower snake case (`access_token`).
- **A box receives the access token and nothing else.** `refresh_token`,
  `authorization_code` and `pkce_verifier` never leave the control plane, so binding one
  is refused.
- One variable belongs to one connection. Two connections on the same bot may not both
  bind `BASECAMP_TOKEN` — give one of them its own variable.

Use the name the ecosystem already uses for the provider (`GITHUB_TOKEN`,
`NOTION_API_KEY`). Stock SDKs and command-line tools then work unmodified.

### A script that reads a credential must declare it

If a delivered script reads a credential-shaped variable — anything ending `_TOKEN`,
`_API_KEY`, `_APIKEY`, `_SECRET`, `_PASSWORD`, `_PAT` or `_CREDENTIAL` — some connection
in this bundle has to bind it. A bare `_KEY` is not on that list, because `SORT_KEY` and
`CACHE_KEY` are ordinary names and a false failure is worse than a missed one. The lint fails an undeclared read. The reason is what the
tenant would otherwise meet: the variable is simply unset, the script raises a
`KeyError`, and nothing anywhere says which account is missing. Test files are exempt,
because a test invents its own variables.

## The readiness gate

`required: true` on its own gates nothing. It has to be paired with a `connection`
artifact in `required_artifacts.yaml`, and the lint fails a `required: true` that is
not. The lint also fails `required: true` on a `delivery: baked` bundle: a baked bundle
ships to every box, so it would put the whole fleet NOT-READY on an account nobody asked
for. A Talent that genuinely needs an account is `delivery: purchased`.

```yaml
artifacts:
  - kind: connection
    name: basecamp                # the same name as under connections:
    env_vars: [BASECAMP_TOKEN]    # every variable the gate must find
    blocking: true                # the default
    remediation: "connect drill §board: send the owner the connect link"
```

`selfcheck` then answers one of three things, and each one asks for a different
response from the bot:

- **READY** — the account is granted and its value has reached this box.
- **NOT-READY** — the owner has not granted the account, or the grant ended. Run the
  connect drill. This is ordinary first-run work.
- **UNKNOWN** — the grant exists and no value reached this box, or `config.yaml` cannot
  be read. Report it and stop. Do **not** coach the owner, because they already did
  their part and nothing they type will fix it.

The judge reads two files, and needs both to agree. `~/.hermes/config.yaml` carries the
map the last converge rendered, and `~/.hermes/state/delivered/<VAR>.ready` is the
receipt written when a value actually arrives. Either one alone leaves a window where a
grant that has ended still reads as present. Requiring both closes each window with the
other.

The two files also decide WHICH failure you are looking at. Nothing rendered means the
owner has not granted the account — first-run work. Rendered with no receipt means the
grant exists and this box has not received it — an environment fault the owner cannot
fix.

**A Talent whose connection is missing still loads, and still ships.** That is
deliberate. Your bundle carries the connect drill — the prose that tells the owner how
to grant the account. Holding the Talent back until the grant exists would deadlock the
owner it was meant to help. So write the drill on the assumption that a NOT-READY box
is the normal first thing a new owner sees.

## An outbound connection needs `neutralize.yaml`

Any `connections:` entry makes the Talent an outbound-action Talent, so it must ship a
`neutralize.yaml` (check 13). A disposable clone of real tenant state would otherwise
inherit the connection and fire a live action at the real system.
