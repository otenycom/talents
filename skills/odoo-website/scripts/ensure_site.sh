#!/bin/sh
# ensure_site.sh — idempotently ensure the embedded Postgres + Odoo are running and serving
# the site on 0.0.0.0:8069. THIS is the hosted-site row's `ensure_cmd`: the platform runs it
# (as the bot, uid 1001) to (re)start the site whenever it's detected down. Safe to re-run.
#
#   ensure_site.sh              -> ensure Postgres up, DB inited, Odoo serving 0.0.0.0:8069
#   ensure_site.sh --init-only  -> ensure Postgres up + DB inited, then exit (used by install)
set -eu

BASE=$HOME/odoo-site
VENV=$BASE/venv
SRC=$BASE/odoo
PGDATA=$BASE/pgdata
PORT=8069
export PYTHONPATH=$SRC
# Odoo refuses to run as a Postgres SUPERUSER ("security risk, aborting"), so the site runs
# as a dedicated non-superuser `odoo` role (CREATEDB, to create the `website` DB on init).
DB_ARGS="--db_host=$PGDATA --db_port=5432 --db_user=odoo"

# 1. embedded Postgres — start persistent (cleanup_mode=None keeps it running after this
#    Python process exits, so the separate Odoo process can connect over the unix socket),
#    and ensure the non-superuser `odoo` role exists.
"$VENV/bin/python" - <<'PY'
import pgserver, os
srv = pgserver.get_server(os.path.expanduser("~/odoo-site/pgdata"), cleanup_mode=None)
srv.psql("DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='odoo') "
         "THEN CREATE ROLE odoo WITH LOGIN CREATEDB; END IF; END $$;")
PY

# 2. one-time DB init (create `website` + install the website module). A marker file (under
#    the home, so it survives rebase) records success so a restart never re-inits.
if [ ! -f "$BASE/.db-inited" ]; then
  "$VENV/bin/python" -m odoo -d website -i website --stop-after-init --without-demo=True \
    $DB_ARGS --data-dir="$BASE/odoo-data" --http-port="$PORT" --http-interface=0.0.0.0 \
    --workers=0 >> "$BASE/odoo.log" 2>&1
  touch "$BASE/.db-inited"
fi

[ "${1:-}" = "--init-only" ] && { echo "DB_READY"; exit 0; }

# 3. serve — start Odoo in the background if it isn't already answering on 8069.
if ! curl -sf -o /dev/null -m 3 "http://127.0.0.1:$PORT/web/login" 2>/dev/null; then
  cd "$BASE"
  setsid "$VENV/bin/python" -m odoo -d website $DB_ARGS \
    --data-dir="$BASE/odoo-data" --http-port="$PORT" --http-interface=0.0.0.0 --workers=0 \
    >> "$BASE/odoo.log" 2>&1 </dev/null &
  # give it a moment to bind the port
  i=0; while [ $i -lt 30 ]; do
    curl -sf -o /dev/null -m 2 "http://127.0.0.1:$PORT/web/login" 2>/dev/null && break
    i=$((i+1)); sleep 1
  done
fi
echo "SITE_UP"
