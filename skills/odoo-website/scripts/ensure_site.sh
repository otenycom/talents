#!/bin/sh
# Thin wrapper so hosted-site rows that still name ensure_site.sh keep healing.
# The keep-alive is register_service → services.d/. This file only starts the stack.
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
OC=$(CDPATH= cd -- "$HERE/../../odoo-community/scripts" && pwd)
exec sh "$OC/ensure_odoo.sh" "$@"
