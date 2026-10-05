#!/usr/bin/env bash
# Blue/green deploy of one image tag. Called by the deploy entry point on the
# Droplet (see infra/cloud-init/droplet.yaml) with the tag as $1.
#
#  1. pull the new image          4. switch Caddy to it
#  2. run migrations (expand-only, safe for the running version)
#  3. start the idle color, wait for /readyz
#  5. smoke test through Caddy    6. roll the worker, stop the old color
# Any failure before step 6 puts traffic back on the old color automatically.
set -euo pipefail
# shellcheck source=SCRIPTDIR/lib.sh
. "$(cd "$(dirname "$0")" && pwd)/lib.sh"

TAG=${1:?usage: deploy.sh <image-tag>}
load_env
IMAGE="${APP_IMAGE_REPO:?APP_IMAGE_REPO missing}:${TAG}"

ACTIVE=${ACTIVE_COLOR:-}
if [ -z "$ACTIVE" ]; then NEW=blue; else NEW=$(other_color "$ACTIVE"); fi
log "deploying $IMAGE as $NEW (active: ${ACTIVE:-none})"

pull "$IMAGE"
pull "$CADDY_IMAGE"

if [ "$NEW" = blue ]; then export BLUE_IMAGE=$IMAGE; else export GREEN_IMAGE=$IMAGE; fi
export WORKER_IMAGE=${WORKER_IMAGE:-$IMAGE}

log "running migrations"
MIGRATE_IMAGE=$IMAGE compose --profile tools run --rm migrate

log "starting app-$NEW"
compose up -d --no-deps --force-recreate "app-$NEW"
if ! wait_ready "app-$NEW"; then
  compose stop "app-$NEW" || true
  log "FAILED: new version never became ready; old version untouched"
  exit 1
fi

switch_traffic "$NEW"
if ! smoke_test; then
  log "FAILED smoke tests; rolling back"
  if [ -n "$ACTIVE" ]; then switch_traffic "$ACTIVE"; fi
  compose stop "app-$NEW" || true
  exit 1
fi

log "rolling the worker to the new image"
export WORKER_IMAGE=$IMAGE
compose up -d --no-deps --force-recreate worker

if [ -n "$ACTIVE" ]; then
  log "stopping app-$ACTIVE (kept for fast rollback)"
  compose stop "app-$ACTIVE"
  # Read by save_state (lib.sh) for rollback.
  export PREVIOUS_COLOR=$ACTIVE
  if [ "$ACTIVE" = blue ]; then export PREVIOUS_IMAGE=$BLUE_IMAGE; else export PREVIOUS_IMAGE=$GREEN_IMAGE; fi
fi
export ACTIVE_COLOR=$NEW
save_state
ln -sfn "$RELEASE_DIR" "$MMH_HOME/current"
docker image prune -af --filter "until=720h" >/dev/null 2>&1 || true
log "deploy of $TAG complete"
