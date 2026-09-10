#!/bin/sh
# install_modules.sh — add modules on the existing `website` database.
# Usage: install_modules.sh website    |    install_modules.sh crm
# Consumer Talents call this. This Talent itself inits base only.
set -eu

BASE=$HOME/odoo-site
VENV=$BASE/venv
SRC=$BASE/odoo
ADDONS=$BASE/addons
PORT=8069
export PYTHONPATH=$SRC
mkdir -p "$ADDONS"
ADDONS_PATH="$SRC/addons,$ADDONS"

if [ "$#" -lt 1 ]; then
  echo "usage: install_modules.sh <module> [<module>…]" >&2
  exit 2
fi

mods=$(printf '%s,' "$@" | sed 's/,$//')

if [ -d "$HOME/postgres/data" ]; then
  DB_ARGS="--db_host=127.0.0.1 --db_port=5432 --db_user=odoo --addons-path=$ADDONS_PATH"
else
  DB_ARGS="--db_host=$BASE/pgdata --db_port=5432 --db_user=odoo --addons-path=$ADDONS_PATH"
fi
if [ -f "$BASE/odoo.conf" ]; then
  DB_ARGS="$DB_ARGS --config=$BASE/odoo.conf"
fi

HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
sh "$HERE/ensure_odoo.sh" --init-only

"$VENV/bin/python" -m odoo -d website -i "$mods" --stop-after-init --without-demo=True \
  $DB_ARGS --data-dir="$BASE/odoo-data" --http-port="$PORT" --http-interface=0.0.0.0 \
  --workers=0 >> "$BASE/odoo.log" 2>&1
echo "ODOO_MODULES $mods"
