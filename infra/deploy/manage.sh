#!/usr/bin/env bash
# Run a Django management command in the live app container.
# For the owner's admin SSH account (not the deploy key), e.g.:
#   sudo -u deploy /opt/mmh/current/manage.sh createsuperuser
#   sudo -u deploy /opt/mmh/current/manage.sh reset_2fa pat@maine-material.com
set -euo pipefail
# shellcheck source=SCRIPTDIR/lib.sh
. "$(cd "$(dirname "$0")" && pwd)/lib.sh"
load_env
[ -n "${ACTIVE_COLOR:-}" ] || { echo "nothing deployed yet" >&2; exit 1; }
exec docker compose -p mmh -f "$COMPOSE_FILE" exec "app-$ACTIVE_COLOR" python manage.py "$@"
