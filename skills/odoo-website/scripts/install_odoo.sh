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
# Odoo CE + embedded Postgres + your agent need a dedicated VM (the Max plan). A packed
# gVisor container can't fit them. A healthy cx23 (~4 GiB) IS a valid floor — refuse only
# clearly undersized envelopes (Lite-class ~1.5 GiB). The deployer injects OTENY_SUBSTRATE
# from the tenant's isolation_tier; else probe the kernel (gVisor names itself in
# /proc/version).
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
# Memory floor (~3.2 GiB = 3355443 KiB): cgroup v2 hard cap first, then /proc/meminfo; an
# OTENY_MEM_GB override wins (deployer injection / tests). An unknown reading does NOT
# block. cx23 MemTotal (~3.8 GiB usable) clears this; refuse only tiny boxes.
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
if [ -n "$mem_kb" ] && [ "$mem_kb" -lt 3355443 ]; then
  echo "ODOO_INSTALL_REFUSED mem=$((mem_kb / 1024))MB — Odoo + Postgres + your agent need" \
       "at least ~3.2 GB (a Max dedicated VM, e.g. cx23). This box is too small; ask the" \
       "owner to upgrade to Max." >&2
  exit 1
fi

mkdir -p "$BASE"
cd "$BASE"

# 1. venv (Python 3.10+; the box ships 3.12). Prefer /usr/bin/python3 so a PATH
#    shim cannot skip ensurepip. Refuse early with an actionable message when the
#    distro python3-venv package is missing (older Max goldens omitted it).
PY3="${OTENY_PYTHON3:-/usr/bin/python3}"
[ -x "$PY3" ] || PY3=python3
if [ ! -x "$VENV/bin/python" ]; then
  if ! "$PY3" -c "import ensurepip" 2>/dev/null; then
    echo "ODOO_INSTALL_REFUSED missing_ensurepip — need the distro python3-venv package" \
         "(apt install python3-venv / python3.12-venv). Max goldens bake this in;" \
         "ask support to heal this box, then re-run install." >&2
    exit 1
  fi
  "$PY3" -m venv "$VENV"
fi
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

# 5. Start Odoo briefly and lock the admin login to profile.yaml's owner_email (password
#    lands only in ~/.hermes/data/odoo-website/.odoo-admin — never stdout). Skip when the
#    profile isn't written yet; first-run.md re-runs setup_admin.py after intake.
PROFILE="$HOME/.hermes/data/odoo-website/profile.yaml"
if [ -f "$PROFILE" ]; then
  sh "$SELF_DIR/ensure_site.sh"
  python3 "$SELF_DIR/setup_admin.py" || {
    echo "ODOO_INSTALL_WARN admin_setup_failed — re-run: python3 $SELF_DIR/setup_admin.py" >&2
  }
fi

echo "ODOO_INSTALLED $(cat "$BASE/odoo.sha256" 2>/dev/null | cut -d' ' -f1)"
