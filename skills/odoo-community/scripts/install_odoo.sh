#!/bin/sh
# install_odoo.sh — Odoo Community 19.0 user-space under ~/odoo-site.
# Shallow git clone of branch 19.0. No nightly zip. No pip embedded server.
# Reuses postgres. Idempotent.
set -eu

BASE=$HOME/odoo-site
VENV=$BASE/venv
SRC=$BASE/odoo
PG_SCRIPTS=$HOME/.hermes/skills/talents/postgres/scripts
# Repo / overlay sibling fallback (unit tests + first delivery).
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ ! -x "$PG_SCRIPTS/install_postgres.sh" ]; then
  PG_SCRIPTS=$(CDPATH= cd -- "$HERE/../../postgres/scripts" && pwd)
fi

mem_kb=""
if [ -r /sys/fs/cgroup/memory.max ]; then
  mm=$(cat /sys/fs/cgroup/memory.max 2>/dev/null)
  case "$mm" in ''|*[!0-9]*) : ;; *) mem_kb=$((mm / 1024)) ;; esac
fi
if [ -z "$mem_kb" ] && [ -r /proc/meminfo ]; then
  mem_kb=$(awk '/^MemTotal:/{print $2}' /proc/meminfo 2>/dev/null)
fi
if [ -n "${OTENY_MEM_GB:-}" ]; then
  mem_kb=$(awk "BEGIN{printf \"%d\", ${OTENY_MEM_GB} * 1024 * 1024}")
fi
if [ -n "$mem_kb" ] && [ "$mem_kb" -lt 2097152 ]; then
  echo "ODOO_INSTALL_REFUSED mem=$((mem_kb / 1024))MB — a website engine needs about 2 GB." \
       "This box is too small; ask the owner to upgrade to Power or Max." >&2
  exit 1
fi
avail_kb=$(df -Pk "$HOME" 2>/dev/null | awk 'NR==2{print $4}')
case "$avail_kb" in ''|*[!0-9]*) avail_kb="" ;; esac
if [ -n "$avail_kb" ] && [ "$avail_kb" -lt 4194304 ]; then
  echo "ODOO_INSTALL_REFUSED disk=$((avail_kb / 1024))MB free — Odoo Community needs" \
       "about 4 GB free to install. Ask the owner for a bigger plan." >&2
  exit 1
fi

mkdir -p "$BASE"
cd "$BASE"

PY3="${OTENY_PYTHON3:-/usr/bin/python3}"
[ -x "$PY3" ] || PY3=python3
if ! "$PY3" -c "import ensurepip" 2>/dev/null; then
  echo "ODOO_INSTALL_REFUSED missing_ensurepip — need the distro python3-venv package" \
       "(apt install python3-venv / python3.12-venv)." >&2
  exit 1
fi

# Unit tests set this after the envelope / ensurepip gates so they never fetch.
if [ "${OTENY_SKIP_STACK:-}" = "1" ]; then
  echo "ODOO_INSTALL_GATES_OK"
  exit 0
fi

# Postgres first. Both missing → install. Else ensure.
if [ ! -d "$HOME/postgres/data" ] && [ ! -d "$HOME/odoo-site/pgdata" ]; then
  sh "$PG_SCRIPTS/install_postgres.sh"
fi
sh "$PG_SCRIPTS/ensure_postgres.sh"

if [ ! -x "$VENV/bin/python" ]; then
  "$PY3" -m venv "$VENV"
fi
"$VENV/bin/pip" install --quiet --upgrade pip wheel

# Shallow 19.0. Never the nightly zip. Never default branch.
if [ ! -d "$SRC/odoo" ]; then
  git clone --branch 19.0 --single-branch --depth 1 --no-tags \
    https://github.com/odoo/odoo.git "$SRC"
  # Pin check — PeekMSX cloned unpinned and landed on 18.
  ver=$("$VENV/bin/python" -c "import ast,pathlib; p=pathlib.Path('$SRC')/'odoo'/'release.py'; t=p.read_text(); print('ok' if '19' in t else 'bad')")
  if [ "$ver" != "ok" ]; then
    echo "ODOO_INSTALL_REFUSED release.py is not 19.0 — refuse to build on the wrong major." >&2
    exit 1
  fi
  git -C "$SRC" rev-parse HEAD > "$BASE/odoo.sha256"
fi

if [ ! -f "$BASE/.deps-installed" ]; then
  sed -e '/python-ldap/d' -e 's/^psycopg2\b/psycopg2-binary/' \
      "$SRC/requirements.txt" > "$BASE/requirements.filtered.txt"
  "$VENV/bin/pip" install -r "$BASE/requirements.filtered.txt"
  touch "$BASE/.deps-installed"
fi

sh "$HERE/ensure_odoo.sh" --init-only

echo "ODOO_INSTALLED $(cat "$BASE/odoo.sha256" 2>/dev/null | tr -d '\n')"
