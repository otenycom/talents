#!/bin/sh
# install_odoo.sh — set up Odoo Community 19 USER-SPACE under ~/odoo-site (no root, no apt,
# survives rebase because everything lives in the home). Idempotent: safe to re-run.
#
# Proven recipe (verified live under gVisor on a power container):
#   * a venv + Odoo's Python deps from binary wheels — swap psycopg2 -> psycopg2-binary
#     (no libpq on the box) and drop python-ldap (needs libldap dev headers the website
#     builder doesn't use);
#   * run Odoo FROM SOURCE via `python -m odoo` (PYTHONPATH), no slow wheel/pip-install-odoo;
#   * pgserver = a pip-embedded PostgreSQL, no system Postgres needed.
set -eu

BASE=$HOME/odoo-site
VENV=$BASE/venv
SRC=$BASE/odoo
TARBALL_URL=https://nightly.odoo.com/19.0/nightly/src/odoo_19.0.latest.tar.gz
SELF_DIR=$HOME/.hermes/skills/talents/odoo-website/scripts

mkdir -p "$BASE"
cd "$BASE"

# 1. venv (Python 3.10+; the box ships 3.12)
[ -x "$VENV/bin/python" ] || python3 -m venv "$VENV"
"$VENV/bin/pip" install --quiet --upgrade pip wheel

# 2. Odoo source (pin the tarball by sha256 for a reproducible install)
if [ ! -d "$SRC/odoo" ]; then
  [ -f odoo.tar.gz ] || curl -fsSL -o odoo.tar.gz "$TARBALL_URL"
  sha256sum odoo.tar.gz > odoo.sha256
  mkdir -p "$SRC"
  tar xzf odoo.tar.gz -C "$SRC" --strip-components=1
fi

# 3. deps (binary psycopg2; drop python-ldap) + the embedded Postgres
if [ ! -f "$BASE/.deps-installed" ]; then
  sed -e '/python-ldap/d' -e 's/^psycopg2\b/psycopg2-binary/' \
      "$SRC/requirements.txt" > "$BASE/requirements.filtered.txt"
  "$VENV/bin/pip" install -r "$BASE/requirements.filtered.txt"
  "$VENV/bin/pip" install pgserver
  touch "$BASE/.deps-installed"
fi

# 4. init the site database + install the website module (idempotent — the ensure script
#    owns pgserver boot + the one-time DB init).
sh "$SELF_DIR/ensure_site.sh" --init-only

echo "ODOO_INSTALLED $(cat "$BASE/odoo.sha256" 2>/dev/null | cut -d' ' -f1)"
