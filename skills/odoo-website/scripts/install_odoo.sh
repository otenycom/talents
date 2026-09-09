#!/bin/sh
# Thin wrapper — the recipe lives on odoo-community. Then install the website module.
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
OC=$(CDPATH= cd -- "$HERE/../../odoo-community/scripts" && pwd)
sh "$OC/install_odoo.sh"
[ "${OTENY_SKIP_STACK:-}" = "1" ] && exit 0
sh "$OC/install_modules.sh" website
