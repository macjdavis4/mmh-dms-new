#!/usr/bin/env bash
# Shared helpers for deploy.sh and rollback.sh (run on the Droplet).
set -euo pipefail

MMH_HOME=${MMH_HOME:-/opt/mmh}
STATE_FILE="$MMH_HOME/state.env"
RELEASE_DIR=${RELEASE_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
COMPOSE_FILE="$RELEASE_DIR/docker-compose.prod.yml"
READY_TIMEOUT=${READY_TIMEOUT:-120}

log() { printf '%s [deploy] %s\n' "$(date -u +%FT%TZ)" "$*"; }

load_env() {
  # Runtime files that exist only on the server.
  set -a
  # shellcheck source=/dev/null
  . "$MMH_HOME/.env"
  set +a
  if [ -f "$MMH_HOME/admin.env" ]; then
    set -a
    # shellcheck source=/dev/null
    . "$MMH_HOME/admin.env"
    set +a
  fi
  export DATABASE_DIRECT_URL_FOR_WORKER="${DATABASE_DIRECT_URL:-$DATABASE_URL}"
  # Migrations run as the database owner (see require_owner_for_migrations).
  export DATABASE_MIGRATE_URL="${ADMIN_DATABASE_URL:-$DATABASE_DIRECT_URL_FOR_WORKER}"
  touch "$STATE_FILE"
  set -a
  # shellcheck source=/dev/null
  . "$STATE_FILE"
  set +a
  export CADDY_IMAGE="${CADDY_IMAGE:?CADDY_IMAGE missing from .env}"
}

# On staging and production, migrations must run as the database owner: run
# as the app's user, new tables would belong to it, and an owner can drop
# them and switch off the no-delete triggers, defeating its row-only access.
require_owner_for_migrations() {
  case "${APP_ENV:-}" in
    staging | production)
      if [ -z "${ADMIN_DATABASE_URL:-}" ]; then
        log "ADMIN_DATABASE_URL is missing from $MMH_HOME/admin.env; refusing to migrate as the app user"
        return 1
      fi
      ;;
  esac
}

# vector.yaml -> vector.rendered.yaml with the bucket, endpoint, region and
# environment filled in. Each value is checked first, so nothing unexpected
# can end up in the config. (The key pair is passed as environment variables.)
render_logship_config() {
  local region
  region=$(sed -nE 's|^https://s3\.([a-z0-9-]+)\..*|\1|p' <<<"${OFFSITE_ENDPOINT_URL:-}")
  [[ "${OFFSITE_BUCKET:-}" =~ ^[A-Za-z0-9-]{6,63}$ ]] || { log "OFFSITE_BUCKET looks wrong"; return 1; }
  [[ "${OFFSITE_ENDPOINT_URL:-}" =~ ^https://[a-z0-9.-]+$ ]] || { log "OFFSITE_ENDPOINT_URL looks wrong"; return 1; }
  [[ "$region" =~ ^[a-z0-9-]+$ ]] || { log "can't read the region from OFFSITE_ENDPOINT_URL"; return 1; }
  [[ "${APP_ENV:-}" =~ ^[a-z0-9-]+$ ]] || { log "APP_ENV looks wrong"; return 1; }
  sed -e "s|@OFFSITE_BUCKET@|$OFFSITE_BUCKET|" \
    -e "s|@OFFSITE_ENDPOINT_URL@|$OFFSITE_ENDPOINT_URL|" \
    -e "s|@OFFSITE_REGION@|$region|" \
    -e "s|@APP_ENV@|$APP_ENV|" \
    "$RELEASE_DIR/vector.yaml" >"$RELEASE_DIR/vector.rendered.yaml"
}

compose() {
  local files=(-f "$COMPOSE_FILE")
  # Local deploy test only: join the throwaway database's network.
  if [ -n "${EXTRA_NETWORK:-}" ]; then files+=(-f "$RELEASE_DIR/docker-compose.test-network.yml"); fi
  docker compose -p mmh "${files[@]}" "$@"
}

pull() {
  if [ "${SKIP_PULL:-0}" = 1 ]; then return 0; fi
  docker pull --quiet "$1"
}

save_state() {
  local tmp
  tmp=$(mktemp "$MMH_HOME/state.XXXXXX")
  {
    echo "ACTIVE_COLOR=${ACTIVE_COLOR:-}"
    echo "BLUE_IMAGE=${BLUE_IMAGE:-}"
    echo "GREEN_IMAGE=${GREEN_IMAGE:-}"
    echo "WORKER_IMAGE=${WORKER_IMAGE:-}"
    echo "PREVIOUS_COLOR=${PREVIOUS_COLOR:-}"
    echo "PREVIOUS_IMAGE=${PREVIOUS_IMAGE:-}"
    echo "DEPLOYED_AT=$(date -u +%FT%TZ)"
  } >"$tmp"
  mv "$tmp" "$STATE_FILE"
}

other_color() { [ "$1" = "blue" ] && echo green || echo blue; }

# Wait until a container answers /readyz (database reachable, migrations current).
wait_ready() {
  local service=$1 deadline=$((SECONDS + READY_TIMEOUT))
  while [ $SECONDS -lt $deadline ]; do
    if compose exec -T "$service" python -c \
      "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/readyz', timeout=3).status == 200 else 1)" \
      >/dev/null 2>&1; then
      log "$service is ready"
      return 0
    fi
    sleep 2
  done
  log "$service did not become ready within ${READY_TIMEOUT}s"
  compose logs --tail 80 "$service" || true
  return 1
}

switch_traffic() {
  local color=$1
  mkdir -p "$MMH_HOME/upstream"
  sed "s/__COLOR__/$color/" "$RELEASE_DIR/upstream.caddy.tmpl" >"$MMH_HOME/upstream/active.caddy.new"
  # The deploy entry point runs with umask 077, which would make this 0600 and
  # unreadable by Caddy (its container drops all capabilities). No secrets in it.
  chmod 0644 "$MMH_HOME/upstream/active.caddy.new"
  mv "$MMH_HOME/upstream/active.caddy.new" "$MMH_HOME/upstream/active.caddy"
  # Reload only a running Caddy; a stopped or crash-looping one is (re)started.
  if [ -n "$(compose ps --status running -q caddy 2>/dev/null)" ]; then
    compose exec -T caddy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile
  else
    compose up -d caddy
  fi
  log "traffic now goes to app-$color"
}

# End-to-end checks through Caddy with the real certificate.
smoke_test() {
  local url="https://${SITE_DOMAIN}"
  local curl_opts=(--silent --show-error --fail --max-time 10 --noproxy "*" --resolve "${SITE_DOMAIN}:443:127.0.0.1")
  # Local deploy test only: Caddy uses its own internal CA there.
  if [ "${SMOKE_INSECURE:-0}" = 1 ]; then curl_opts+=(--insecure); fi
  for _ in $(seq 1 15); do
    if curl "${curl_opts[@]}" "$url/readyz" >/dev/null 2>&1; then break; fi
    sleep 2
  done
  curl "${curl_opts[@]}" "$url/readyz" | grep -q '"status": "ok"' || { log "smoke: /readyz failed"; return 1; }
  curl "${curl_opts[@]}" "$url/api/v1/system/status" | grep -q '"read_only_mode"' || { log "smoke: status API failed"; return 1; }
  curl "${curl_opts[@]}" "$url/login" | grep -q '<div id="root">' || { log "smoke: app shell failed"; return 1; }
  local asset
  asset=$(curl "${curl_opts[@]}" "$url/login" | grep -o '/static/assets/index-[^"]*\.js' | head -1)
  if [ -z "$asset" ] || ! curl "${curl_opts[@]}" -o /dev/null "$url$asset"; then
    log "smoke: static assets failed"
    return 1
  fi
  log "smoke tests passed"
}
