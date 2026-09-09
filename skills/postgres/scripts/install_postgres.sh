#!/bin/sh
# install_postgres.sh — user-space PostgreSQL 18 under ~/postgres. No apt.
# Idempotent. Adopts ~/odoo-site/pgdata when ~/postgres/data is missing.
set -eu

PREFIX=$HOME/postgres
FRESH=$PREFIX/data
LEGACY=$HOME/odoo-site/pgdata
PG_VER=18.6.0
PG_SHA256=bb3d09f876b2383e25a8c9ce09e32d185a03656a23d074f5195542b1b1b3ca61
ARCH=$(uname -m)
case "$ARCH" in
  x86_64) PG_TRIPLE=x86_64-unknown-linux-gnu ;;
  *)
    echo "POSTGRES_INSTALL_REFUSED arch=$ARCH — pin is x86_64-unknown-linux-gnu." >&2
    exit 1
    ;;
esac
TARBALL_URL="https://github.com/theseus-rs/postgresql-binaries/releases/download/${PG_VER}/postgresql-${PG_VER}-${PG_TRIPLE}.tar.gz"
ARCHIVE="postgresql-${PG_VER}-${PG_TRIPLE}.tar.gz"

mkdir -p "$PREFIX"
cd "$PREFIX"

if [ ! -x "$PREFIX/bin/pg_ctl" ]; then
  [ -f "$ARCHIVE" ] || curl -fsSL -o "$ARCHIVE" "$TARBALL_URL"
  got=$(sha256sum "$ARCHIVE" | awk '{print $1}')
  if [ "$got" != "$PG_SHA256" ]; then
    echo "POSTGRES_INSTALL_REFUSED sha256 mismatch — got $got want $PG_SHA256" >&2
    rm -f "$ARCHIVE"
    exit 1
  fi
  tar xzf "$ARCHIVE"
  # theseus layout: postgresql-<ver>-<triple>/{bin,lib,share}
  inner="postgresql-${PG_VER}-${PG_TRIPLE}"
  if [ -d "$inner/bin" ]; then
    cp -a "$inner"/. "$PREFIX"/
    rm -rf "$inner"
  fi
  rm -f "$ARCHIVE"
fi

export LD_LIBRARY_PATH="$PREFIX/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PATH="$PREFIX/bin:$PATH"

# One cluster. Fresh 18 at ~/postgres/data. A carried WebsiteBot cluster
# stays at ~/odoo-site/pgdata — do not initdb a second copy.
if [ ! -d "$FRESH" ] && [ -d "$LEGACY" ]; then
  echo "POSTGRES_ADOPTED $LEGACY"
  echo "POSTGRES_INSTALLED adopted-legacy"
  exit 0
fi

if [ ! -d "$FRESH" ]; then
  mkdir -p "$PREFIX/run"
  LC_ALL=C.UTF-8 LANG=C.UTF-8 "$PREFIX/bin/initdb" \
    -D "$FRESH" --auth=trust --encoding=utf8 --locale=C.UTF-8
  # Listen on loopback only. Socket dir is the data dir (pg_isready / Odoo).
  {
    echo "listen_addresses = '127.0.0.1'"
    echo "port = 5432"
    echo "unix_socket_directories = '$FRESH'"
  } >> "$FRESH/postgresql.conf"
fi

# Non-superuser role for Odoo (Odoo refuses SUPERUSER).
if ! "$PREFIX/bin/pg_ctl" -D "$FRESH" status >/dev/null 2>&1; then
  "$PREFIX/bin/pg_ctl" -D "$FRESH" -l "$FRESH/pg.log" -o "-p 5432 -h 127.0.0.1" start
fi
"$PREFIX/bin/psql" -h 127.0.0.1 -p 5432 -d postgres -v ON_ERROR_STOP=1 \
  -c "DO \$\$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='odoo') THEN CREATE ROLE odoo WITH LOGIN CREATEDB; END IF; END \$\$;"

echo "POSTGRES_INSTALLED $PG_VER"
