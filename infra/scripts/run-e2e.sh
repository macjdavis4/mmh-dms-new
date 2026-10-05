#!/usr/bin/env bash
# Start a production-like server (Gunicorn, built frontend, CSP on) against
# the local Postgres, then run a Playwright project: e2e or screenshots.
set -euo pipefail
PROJECT=${1:-e2e}
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT/backend"
export DJANGO_SETTINGS_MODULE=config.settings.e2e
export DATABASE_URL=${DATABASE_URL:-postgres://mmh:mmh@localhost:5432/mmh}
PY=${E2E_PYTHON:-$ROOT/backend/.venv/bin/python}
"$PY" manage.py migrate --noinput >/dev/null
"$(dirname "$PY")/gunicorn" -c gunicorn.conf.py config.wsgi >/tmp/mmh-e2e-server.log 2>&1 &
SERVER=$!
trap 'kill $SERVER 2>/dev/null || true' EXIT
for _ in $(seq 1 30); do curl -sf --noproxy '*' http://localhost:8000/readyz >/dev/null && break; sleep 1; done
cd "$ROOT/frontend"
npx playwright test --project="$PROJECT"
