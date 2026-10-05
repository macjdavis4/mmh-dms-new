#!/usr/bin/env bash
# The ONLY command the `deploy` SSH key may run (forced in authorized_keys).
# GitHub Actions calls:  ssh deploy@host "deploy <tag>" < env-file
#                        ssh deploy@host "rollback"
#                        ssh deploy@host "status"
set -euo pipefail
umask 077
MMH_HOME=/opt/mmh
read -r CMD TAG _ <<<"${SSH_ORIGINAL_COMMAND:-}"

case "${CMD:-}" in
  deploy)
    [[ "${TAG:-}" =~ ^[A-Za-z0-9._-]{1,128}$ ]] || { echo "invalid tag" >&2; exit 2; }
    # New environment (secrets) arrives on stdin; keep the old one for rollback.
    cat >"$MMH_HOME/.env.incoming"
    grep -q '^APP_IMAGE_REPO=' "$MMH_HOME/.env.incoming" || { echo "env missing APP_IMAGE_REPO" >&2; exit 2; }
    REPO=$(grep '^APP_IMAGE_REPO=' "$MMH_HOME/.env.incoming" | cut -d= -f2-)
    GHCR_USER=$(grep '^GHCR_USER=' "$MMH_HOME/.env.incoming" | cut -d= -f2-)
    grep '^GHCR_TOKEN=' "$MMH_HOME/.env.incoming" | cut -d= -f2- \
      | docker login ghcr.io --username "$GHCR_USER" --password-stdin >/dev/null
    docker pull --quiet "$REPO:$TAG" >/dev/null
    # Unpack this version's deploy scripts from the image itself.
    RELEASE="$MMH_HOME/releases/$TAG"
    rm -rf "$RELEASE.tmp" && mkdir -p "$RELEASE.tmp"
    CID=$(docker create "$REPO:$TAG")
    docker cp "$CID:/app/deploy/." "$RELEASE.tmp/" && docker rm "$CID" >/dev/null
    rm -rf "$RELEASE" && mv "$RELEASE.tmp" "$RELEASE"
    chmod 0755 "$RELEASE"/*.sh
    [ -f "$MMH_HOME/.env" ] && cp -p "$MMH_HOME/.env" "$MMH_HOME/.env.previous"
    mv "$MMH_HOME/.env.incoming" "$MMH_HOME/.env"
    exec env RELEASE_DIR="$RELEASE" "$RELEASE/deploy.sh" "$TAG"
    ;;
  rollback)
    [ -f "$MMH_HOME/.env.previous" ] && cp -p "$MMH_HOME/.env.previous" "$MMH_HOME/.env"
    exec env RELEASE_DIR="$(readlink -f "$MMH_HOME/current")" "$MMH_HOME/current/rollback.sh"
    ;;
  status)
    cat "$MMH_HOME/state.env" 2>/dev/null || echo "never deployed"
    docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'
    ;;
  *)
    echo "allowed commands: deploy <tag> | rollback | status" >&2
    exit 2
    ;;
esac
