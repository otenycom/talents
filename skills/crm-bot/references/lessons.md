# Lessons and pitfalls (PeekMSX harvest, `hh00033`)

Kept from the live lead-bot skill. The shipped Talent changes the
install path and the wire. The lessons stay.

## Lessons

1. Verify the target version before cloning. An unpinned clone took
   18 when 19 was current. Pin `git clone --branch 19.0 --single-branch
   --depth 1`. Check `odoo/release.py` after the clone.
2. No root on the box. `sudo` is blocked. Plan every dependency as
   user-space.
3. `python-ldap` needs `lber.h`. Drop it from `requirements.txt`.
4. Source `psycopg2` needs `pg_config`. Use `psycopg2-binary`.
5. No system Postgres. Use the PostgreSQL Installer Talent (18), not
   a portable 16.15 tarball and not pip `pgserver` as the product.
6. `host_website` slugs can stay reserved after unhost. Pick another
   slug. Never hardcode one.
7. `uv`/`pip` from a filtered `requirements.txt` is the venv path.
8. Do not say CRM is ready when `profile.yaml` did not land.
   `write_file` cannot create `~/.hermes/data/crm-bot` when that
   parent is not writable. Run `write_profile.py`. Stop on
   `PROFILE_WRITE_FAILED`.

## Pitfalls

1. Re-running the full install when the site is already up.
2. Hardcoding a slug or `*.oteny.bot` host.
3. Binding Odoo on `127.0.0.1` → public 502.
4. `sudo apt`.
5. Secrets in the skill file.
6. `publish_file` for a running app.
7. In-place Community upgrade across majors — there is no path.
8. Minting a fresh credential when one is already delivered.
9. Trusting a late background-process notification. Re-check live
   state.
11. Assuming an Odoo Python API is stable across majors
    (`odoo.registry()` died in 19).
12. Cloning the default branch and calling it "latest".
13. `res.users.apikeys._generate()` attaches to `self.env.user`.
14. Odoo 19 renamed `groups_id` → `group_ids`.
15. `crm.lead` defaults to `type = 'opportunity'`. Do not search
    `type = 'lead'`.
16. `message_post(body=...)` wraps its own `<p>`.
17. `ir.attachment` with only `res_model`/`res_id` is invisible on
    the Odoo 19 CRM form. Post `attachment_ids` on the chatter, and
    keep the real filename extension.
18. Waiting for `web_search` before the first upsert.
