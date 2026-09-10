#!/bin/sh
# ensure_odoo.sh — Postgres first, then Odoo on 0.0.0.0:8069.
# Always waits for 127.0.0.1:5432 (odoo-community sorts before postgres).
#   ensure_odoo.sh              -> serving / (primary). /web/login is fallback only.
#   ensure_odoo.sh --init-only  -> base DB inited, then exit
set -eu

BASE=$HOME/odoo-site
VENV=$BASE/venv
SRC=$BASE/odoo
ADDONS=$BASE/addons
PORT=8069
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PG_SCRIPTS=$HOME/.hermes/skills/talents/postgres/scripts
if [ ! -x "$PG_SCRIPTS/ensure_postgres.sh" ]; then
  PG_SCRIPTS=$(CDPATH= cd -- "$HERE/../../postgres/scripts" && pwd)
fi

export PYTHONPATH=$SRC
mkdir -p "$ADDONS"
ADDONS_PATH="$SRC/addons,$ADDONS"

# Fresh PG 18 talks TCP. Legacy pgserver talks the unix socket in pgdata.
if [ -d "$HOME/postgres/data" ]; then
  DB_ARGS="--db_host=127.0.0.1 --db_port=5432 --db_user=odoo --addons-path=$ADDONS_PATH"
else
  PGDATA=$BASE/pgdata
  DB_ARGS="--db_host=$PGDATA --db_port=5432 --db_user=odoo --addons-path=$ADDONS_PATH"
fi

sh "$PG_SCRIPTS/ensure_postgres.sh"

i=0
while [ $i -lt 30 ]; do
  python3 -c 'import socket; s=socket.socket(); s.settimeout(2); s.connect(("127.0.0.1",5432)); s.close()' \
    2>/dev/null && break
  i=$((i + 1))
  sleep 1
done
python3 -c 'import socket; s=socket.socket(); s.settimeout(2); s.connect(("127.0.0.1",5432)); s.close()' \
  || { echo "ODOO_DOWN: Postgres did not accept 127.0.0.1:5432" >&2; exit 1; }

# One-time base init. Keep DB name `website` so a carried cluster needs no rename.
if [ ! -f "$BASE/.db-inited" ]; then
  "$VENV/bin/python" -m odoo -d website -i base --stop-after-init --without-demo=True \
    $DB_ARGS --data-dir="$BASE/odoo-data" --http-port="$PORT" --http-interface=0.0.0.0 \
    --workers=0 >> "$BASE/odoo.log" 2>&1
  touch "$BASE/.db-inited"
fi

[ "${1:-}" = "--init-only" ] && { echo "DB_READY"; exit 0; }

# Canonical "Odoo is up" probe is /. A shop may disable
# /web/login on purpose (Pioneer). / HTTP 200 is enough.
# /web/login is fallback for a backend-only box with no
# website /. Do not start a second listener.
_odoo_answering() {
  curl -sf -o /dev/null -m "$1" "http://127.0.0.1:$PORT/" && return 0
  curl -sf -o /dev/null -m "$1" "http://127.0.0.1:$PORT/web/login" && return 0
  return 1
}

if ! _odoo_answering 3; then
  cd "$BASE"
  setsid "$VENV/bin/python" -m odoo -d website $DB_ARGS \
    --data-dir="$BASE/odoo-data" --http-port="$PORT" --http-interface=0.0.0.0 --workers=0 \
    >> "$BASE/odoo.log" 2>&1 </dev/null &
  i=0
  while [ $i -lt 30 ]; do
    _odoo_answering 2 && break
    i=$((i + 1))
    sleep 1
  done
fi

if _odoo_answering 5; then
  echo "ODOO_UP"
  exit 0
fi
echo "ODOO_DOWN: nothing is answering on 127.0.0.1:$PORT" >&2
tail -30 "$BASE/odoo.log" 2>/dev/null >&2 || true
exit 1
