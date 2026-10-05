#!/usr/bin/env bash
# Exercise the real blue/green deploy and rollback scripts on this machine,
# with a local "Droplet" directory, a throwaway Postgres and a Caddy that uses
# its own internal certificate instead of Let's Encrypt.
#
#   infra/scripts/test-deploy-local.sh <app-image>
#
# Checks: first deploy (blue), second deploy (green, zero downtime),
# rollback (back to blue), and a broken image that must leave the live
# version untouched.
set -euo pipefail

APP_IMAGE=${1:?usage: test-deploy-local.sh <app-image>}
CADDY_BASE=${CADDY_BASE:-caddy:2}
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
WORK=$(mktemp -d /tmp/mmh-deploy-test.XXXXXX)
export MMH_HOME="$WORK/opt-mmh"
NET=mmh-deploy-test
PG=mmh-deploy-test-pg
DOMAIN=dms.localtest

cleanup() {
  CADDY_IMAGE=mmh-caddy-test EXTRA_NETWORK=$NET docker compose -p mmh \
    -f "$ROOT/infra/deploy/docker-compose.prod.yml" -f "$ROOT/infra/deploy/docker-compose.test-network.yml" \
    down -v --remove-orphans >/dev/null 2>&1 || true
  rm -rf "$WORK"
  docker rm -f "$PG" >/dev/null 2>&1 || true
  docker network rm "$NET" >/dev/null 2>&1 || true
}
[ "${KEEP:-0}" = 1 ] || trap cleanup EXIT
cleanup

log() { printf '\n=== %s\n' "$*"; }

mkdir -p "$MMH_HOME/certs" "$MMH_HOME/upstream"

log "test database"
docker network create "$NET" >/dev/null
docker run -d --name "$PG" --network "$NET" -e POSTGRES_USER=mmh -e POSTGRES_PASSWORD=mmh -e POSTGRES_DB=mmh postgres:16-alpine >/dev/null
for _ in $(seq 1 30); do docker exec "$PG" pg_isready -U mmh >/dev/null 2>&1 && break; sleep 1; done

log "test Caddy image (internal TLS instead of Let's Encrypt)"
cat >"$WORK/Caddyfile" <<CADDY
{
	auto_https disable_redirects
}
{\$SITE_DOMAIN} {
	tls internal
	import /etc/caddy/upstream/active.caddy
}
CADDY
printf 'FROM %s\nCOPY Caddyfile /etc/caddy/Caddyfile\n' "$CADDY_BASE" >"$WORK/Dockerfile"
docker build -q -t mmh-caddy-test "$WORK" >/dev/null

docker tag "$APP_IMAGE" mmh-local/app:v1
docker tag "$APP_IMAGE" mmh-local/app:v2
printf 'FROM %s\nENTRYPOINT ["sh", "-c", "echo broken build; exit 1"]\n' "$APP_IMAGE" | docker build -q -t mmh-local/app:broken - >/dev/null

cat >"$MMH_HOME/.env" <<ENV
APP_IMAGE_REPO=mmh-local/app
CADDY_IMAGE=mmh-caddy-test
SITE_DOMAIN=$DOMAIN
DJANGO_SETTINGS_MODULE=config.settings.prod
DJANGO_SECRET_KEY=local-deploy-test-secret-key-0123456789abcdefghijklmnop
DJANGO_ALLOWED_HOSTS=$DOMAIN
DJANGO_CSRF_TRUSTED_ORIGINS=https://$DOMAIN
DATABASE_URL=postgres://mmh:mmh@$PG:5432/mmh
DATABASE_DIRECT_URL=postgres://mmh:mmh@$PG:5432/mmh
APP_ENV=deploy-test
ENV

# Images exist only locally: skip registry pulls, trust Caddy's internal CA,
# and put the containers on the test database's network.
export SKIP_PULL=1 SMOKE_INSECURE=1 EXTRA_NETWORK=$NET
export no_proxy="$DOMAIN,localhost,127.0.0.1" NO_PROXY="$DOMAIN,localhost,127.0.0.1"

run() { RELEASE_DIR="$ROOT/infra/deploy" "$ROOT/infra/deploy/$1" "${@:2}"; }
active() { grep '^ACTIVE_COLOR=' "$MMH_HOME/state.env" | cut -d= -f2; }
live_version() {
  curl -sk --resolve "$DOMAIN:443:127.0.0.1" "https://$DOMAIN/healthz"
}

log "deploy v1 (first deploy -> blue)"
run deploy.sh v1
[ "$(active)" = blue ] || { echo "expected blue"; exit 1; }
live_version

log "deploy v2 (-> green) while polling for downtime"
( fails=0; for _ in $(seq 1 200); do
    curl -skf --max-time 2 --resolve "$DOMAIN:443:127.0.0.1" "https://$DOMAIN/healthz" >/dev/null || fails=$((fails+1))
    sleep 0.2
  done; echo "$fails" >"$WORK/fails" ) &
POLLER=$!
run deploy.sh v2
wait "$POLLER"
[ "$(active)" = green ] || { echo "expected green"; exit 1; }
echo "failed requests during deploy: $(cat "$WORK/fails")"
[ "$(cat "$WORK/fails")" -eq 0 ] || { echo "downtime detected"; exit 1; }

log "rollback (-> blue)"
run rollback.sh
[ "$(active)" = blue ] || { echo "expected blue after rollback"; exit 1; }
live_version

log "broken image must not replace the live version"
if run deploy.sh broken; then echo "broken deploy should have failed"; exit 1; fi
[ "$(active)" = blue ] || { echo "live color changed after failed deploy"; exit 1; }
curl -skf --resolve "$DOMAIN:443:127.0.0.1" "https://$DOMAIN/readyz"

log "ALL DEPLOY CHECKS PASSED"
