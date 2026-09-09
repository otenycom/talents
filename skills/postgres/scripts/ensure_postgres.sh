#!/bin/sh
# ensure_postgres.sh — start the one cluster. No-op when already up.
# Fresh: ~/postgres/data (PostgreSQL 18). Legacy: ~/odoo-site/pgdata.
set -eu

PREFIX=$HOME/postgres
FRESH=$PREFIX/data
LEGACY=$HOME/odoo-site/pgdata
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
export LD_LIBRARY_PATH="$PREFIX/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

if [ -d "$FRESH" ]; then
  DATADIR=$FRESH
  START=pg_ctl
elif [ -d "$LEGACY" ]; then
  DATADIR=$LEGACY
  # PG 18 binaries must not start a PG 16 cluster. Use pgserver when majors differ.
  major=""
  if [ -f "$DATADIR/PG_VERSION" ]; then
    major=$(cat "$DATADIR/PG_VERSION" | tr -d '[:space:]')
  fi
  case "$major" in
    18) START=pg_ctl ;;
    *) START=pgserver ;;
  esac
else
  echo "POSTGRES_DOWN: no cluster at $FRESH or $LEGACY" >&2
  exit 1
fi

if [ -f "$DATADIR/postgresql.conf" ]; then
  if [ -x "$PREFIX/bin/python3" ]; then
    "$PREFIX/bin/python3" "$HERE/normalize_pg_locales.py" "$DATADIR" || true
  fi
  python3 "$HERE/normalize_pg_locales.py" "$DATADIR"
fi

# Stale postmaster.pid after a sandbox kill (same class as WebsiteBot ensure).
if [ -f "$DATADIR/postmaster.pid" ]; then
  PGPID=$(head -1 "$DATADIR/postmaster.pid" 2>/dev/null || true)
  STALE=1
  case "$PGPID" in
    ''|*[!0-9]*) ;;
    *)
      if kill -0 "$PGPID" 2>/dev/null \
         && tr -d '\000' < "/proc/$PGPID/cmdline" 2>/dev/null | grep -q "postgres" \
         && tr -d '\000' < "/proc/$PGPID/cmdline" 2>/dev/null | grep -q -- "$DATADIR"; then
        STALE=0
      fi ;;
  esac
  if [ "$STALE" = 1 ]; then
    echo "ensure_postgres: stale postmaster.pid pid='$PGPID' for $DATADIR" >&2
    rm -f "$DATADIR/postmaster.pid" "$DATADIR/.s.PGSQL.5432" "$DATADIR/.s.PGSQL.5432.lock"
  fi
fi

_up() {
  python3 - <<'PY'
import socket, sys
s = socket.socket()
s.settimeout(2)
try:
    s.connect(("127.0.0.1", 5432))
except OSError:
    sys.exit(1)
finally:
    s.close()
PY
}

if _up; then
  echo "POSTGRES_UP"
  exit 0
fi

if [ "$START" = "pg_ctl" ]; then
  if [ ! -x "$PREFIX/bin/pg_ctl" ]; then
    echo "POSTGRES_DOWN: pg_ctl missing at $PREFIX/bin — run install_postgres.sh" >&2
    exit 1
  fi
  "$PREFIX/bin/pg_ctl" -D "$DATADIR" -l "$DATADIR/pg.log" -o "-p 5432 -h 127.0.0.1" start
else
  VENV=$HOME/odoo-site/venv
  if [ ! -x "$VENV/bin/python" ]; then
    echo "POSTGRES_DOWN: legacy cluster $DATADIR needs the site venv pgserver" >&2
    exit 1
  fi
  LC_ALL=C.UTF-8 LANG=C.UTF-8 "$VENV/bin/python" - <<'PY'
import os, pgserver
srv = pgserver.get_server(os.path.expanduser("~/odoo-site/pgdata"), cleanup_mode=None)
srv.psql("DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='odoo') "
         "THEN CREATE ROLE odoo WITH LOGIN CREATEDB; END IF; END $$;")
PY
fi

i=0
while [ $i -lt 30 ]; do
  _up && { echo "POSTGRES_UP"; exit 0; }
  i=$((i + 1))
  sleep 1
done
echo "POSTGRES_DOWN: 127.0.0.1:5432 did not accept a connection" >&2
tail -30 "$DATADIR/pg.log" 2>/dev/null >&2 || true
exit 1
