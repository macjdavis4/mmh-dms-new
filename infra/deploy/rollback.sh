#!/usr/bin/env bash
# Put traffic back on the previous version (the stopped color).
# Database changes are not undone: migrations are expand-only, so the
# previous code works with the current schema.
set -euo pipefail
# shellcheck source=SCRIPTDIR/lib.sh
. "$(cd "$(dirname "$0")" && pwd)/lib.sh"
load_env

PREV=${PREVIOUS_COLOR:?no previous version recorded}
CUR=${ACTIVE_COLOR:?no active version recorded}
log "rolling back from app-$CUR to app-$PREV (${PREVIOUS_IMAGE:-})"

compose up -d --no-deps "app-$PREV"
wait_ready "app-$PREV"
switch_traffic "$PREV"
smoke_test
export WORKER_IMAGE=$PREVIOUS_IMAGE
compose up -d --no-deps --force-recreate worker
compose stop "app-$CUR"

if [ "$CUR" = blue ]; then export PREVIOUS_IMAGE=$BLUE_IMAGE; else export PREVIOUS_IMAGE=$GREEN_IMAGE; fi
export PREVIOUS_COLOR=$CUR
export ACTIVE_COLOR=$PREV
save_state
log "rollback complete"
