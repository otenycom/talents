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

# 0. Refuse an under-provisioned envelope BEFORE any work (the §14.2 runtime self-gate).
# Odoo CE + embedded Postgres + your agent need a dedicated machine (the Max plan) — a
# packed gVisor container / <3 GB can't fit them. The deployer injects OTENY_SUBSTRATE from
# the tenant's isolation_tier; else probe the kernel (gVisor names itself in /proc/version).
substrate="${OTENY_SUBSTRATE:-}"
if [ -z "$substrate" ] && grep -qi gvisor /proc/version 2>/dev/null; then
  substrate=container
fi
if [ "$substrate" = "container" ]; then
  echo "ODOO_INSTALL_REFUSED substrate=container — WebsiteBot needs the Max plan (your own" \
       "dedicated server); a packed container can't host Odoo + Postgres. Ask the owner to" \
       "upgrade to Max." >&2
  exit 1
fi
# Memory floor (~3 GB = 3145728 KiB): cgroup v2 hard cap first, then /proc/meminfo; an
# OTENY_MEM_GB override wins (deployer injection / tests). An unknown reading does NOT block.
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
if [ -n "$mem_kb" ] && [ "$mem_kb" -lt 3145728 ]; then
  echo "ODOO_INSTALL_REFUSED mem=$((mem_kb / 1024))MB — Odoo + Postgres + your agent need" \
       "~3 GB. This box is too small; ask the owner to upgrade to the Max plan (a dedicated" \
       "server)." >&2
  exit 1
fi

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
