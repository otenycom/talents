#!/bin/sh
# ensure_site.sh — idempotently ensure the embedded Postgres + Odoo are running and serving
# the site on 0.0.0.0:8069. THIS is the hosted-site row's `ensure_cmd`: the platform runs it
# (as the bot, uid 1001) to (re)start the site whenever it's detected down. Safe to re-run.
#
#   ensure_site.sh              -> ensure Postgres up, DB inited, Odoo serving 0.0.0.0:8069
#   ensure_site.sh --init-only  -> ensure Postgres up + DB inited, then exit (used by install)
#
# Always passes --addons-path so site modules under ~/odoo-site/addons load.
set -eu

BASE=$HOME/odoo-site
VENV=$BASE/venv
SRC=$BASE/odoo
ADDONS=$BASE/addons
PGDATA=$BASE/pgdata
PORT=8069
export PYTHONPATH=$SRC
mkdir -p "$ADDONS"
# Community addons + per-site custom modules (oteny_site_<slug>).
ADDONS_PATH="$SRC/addons,$ADDONS"
# Odoo refuses to run as a Postgres SUPERUSER ("security risk, aborting"), so the site runs
# as a dedicated non-superuser `odoo` role (CREATEDB, to create the `website` DB on init).
DB_ARGS="--db_host=$PGDATA --db_port=5432 --db_user=odoo --addons-path=$ADDONS_PATH"

# 0. carried clusters pin lc_* to en_US.UTF-8 (Ubuntu VM); the container image often
#    lacks that locale and Postgres refuses to start. Rewrite missing lc_* → C.UTF-8
#    BEFORE pgserver boots. Single owner of this rewrite (not site_carry). Fail loud —
#    swallowing the rewrite used to hide the real error behind a later Postgres FATAL.
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ -f "$PGDATA/postgresql.conf" ]; then
  # Prefer the site venv's python once it exists; fall back to PATH for a half-install.
  if [ -x "$VENV/bin/python" ]; then
    "$VENV/bin/python" "$HERE/normalize_pg_locales.py" "$PGDATA"
  else
    python3 "$HERE/normalize_pg_locales.py" "$PGDATA"
  fi
fi

# 0b. A postmaster.pid that outlived its cluster. THIS is what broke Power→Max.
#
#     A tier move kills the sandbox outright (runsc delete --force), so Postgres never gets
#     to remove its lock file, and the whole pgdata — lock file included — is carried to the
#     other substrate. Postgres and pgserver both decide "is a server already running?" by
#     reading the PID out of that file and asking whether it is alive.
#
#     Going DOWN that is harmless: a VM postmaster's PID (measured: 3168) does not exist in
#     a fresh gVisor PID namespace, so the lock is recognised as stale and cleaned up.
#     Going UP it is fatal: a CONTAINER postmaster's PID is a small number (measured: 79),
#     and on the destination VM PID 79 was a live kernel thread (kworker/R-scsi_). The
#     lock therefore read as a running server, pgserver returned a handle for a server that
#     does not exist, and the very next query died on a missing socket — under `set -eu`
#     that ends this script, so Odoo never started and the site stayed behind its own
#     maintenance page through every subsequent belt tick. (hh00415, 2026-08-08.)
#
#     A live postmaster for THIS cluster always has both "postgres" and this data directory
#     in its /proc cmdline. Anything else holding that PID — a kernel thread with no cmdline
#     at all, a recycled PID, nothing — means the lock is stale. Requiring both is what makes
#     removing the file safe: two postmasters on one data directory would corrupt it.
if [ -f "$PGDATA/postmaster.pid" ]; then
  PGPID=$(head -1 "$PGDATA/postmaster.pid" 2>/dev/null || true)
  STALE=1
  case "$PGPID" in
    ''|*[!0-9]*) ;;                                    # unreadable ⇒ stale
    *)
      if kill -0 "$PGPID" 2>/dev/null \
         && tr -d '\000' < "/proc/$PGPID/cmdline" 2>/dev/null | grep -q "postgres" \
         && tr -d '\000' < "/proc/$PGPID/cmdline" 2>/dev/null | grep -q -- "$PGDATA"; then
        STALE=0                                        # a real postmaster for this cluster
      fi ;;
  esac
  if [ "$STALE" = 1 ]; then
    echo "ensure_site: postmaster.pid names pid '$PGPID', which is not a postgres for" \
         "$PGDATA — removing the stale lock left by a substrate move." >&2
    rm -f "$PGDATA/postmaster.pid" "$PGDATA/.s.PGSQL.5432" "$PGDATA/.s.PGSQL.5432.lock"
  fi
fi

# 1. embedded Postgres — start persistent (cleanup_mode=None keeps it running after this
#    Python process exits, so the separate Odoo process can connect over the unix socket),
#    and ensure the non-superuser `odoo` role exists.
#
#    LC_ALL/LANG=C.UTF-8 makes a FIRST-TIME initdb bake a PORTABLE collation into the
#    cluster. pgserver runs `initdb --auth=trust --encoding=utf8` with NO --locale, so it
#    inherits this environment; on an Ubuntu VM that used to mean LC_COLLATE=en_US.UTF-8,
#    which is stored in pg_database and CANNOT be edited afterwards. Carried onto a
#    container that lacks the locale, every database then fails with "database locale is
#    incompatible with operating system" — a failure the postgresql.conf rewrite below
#    cannot reach, because that setting does not live in the file. C.UTF-8 exists on the
#    VM and in the container image alike, so the cluster survives a plan change in either
#    direction by construction. (Trade-off: code-point sort order rather than en_US
#    linguistic ordering — the default of most container Postgres images.)
#    Only affects clusters created from here on; one initialized earlier keeps its own.
LC_ALL=C.UTF-8 LANG=C.UTF-8 "$VENV/bin/python" - <<'PY'
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

# 4. SAY WHETHER IT WORKED. `SITE_UP` used to be echoed unconditionally, right after a wait
#    loop that is allowed to time out — so the platform's self-heal log, and the round-trip
#    installer's `"SITE_UP" not in out` check, both read green while Odoo had never bound
#    the port. The whole reason ~/oteny-ensure.log exists is to say why the last ensure did
#    or did not work; a marker that prints either way cannot do that. Report the real state,
#    and put the two logs that hold the answer in front of whoever is reading.
if curl -sf -o /dev/null -m 5 "http://127.0.0.1:$PORT/web/login" 2>/dev/null; then
  echo "SITE_UP"
  exit 0
fi
echo "SITE_DOWN: nothing is answering on 127.0.0.1:$PORT after the start attempt." >&2
echo "--- last 30 lines of $BASE/odoo.log ---" >&2
tail -30 "$BASE/odoo.log" 2>/dev/null >&2 || echo "(no odoo.log)" >&2
echo "--- last 30 lines of the Postgres log ---" >&2
tail -30 "$PGDATA"/log/*.log 2>/dev/null >&2 || echo "(no postgres log)" >&2
exit 1
