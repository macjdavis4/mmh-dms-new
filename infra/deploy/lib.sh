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
  # Migrations run as the database owner when its URL is available.
  export DATABASE_MIGRATE_URL="${ADMIN_DATABASE_URL:-$DATABASE_DIRECT_URL_FOR_WORKER}"
  touch "$STATE_FILE"
  set -a
  # shellcheck source=/dev/null
  . "$STATE_FILE"
  set +a
  export CADDY_IMAGE="${CADDY_IMAGE:?CADDY_IMAGE missing from .env}"
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
  mv "$MMH_HOME/upstream/active.caddy.new" "$MMH_HOME/upstream/active.caddy"
  if [ -n "$(compose ps -q caddy 2>/dev/null)" ]; then
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
