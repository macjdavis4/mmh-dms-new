#!/bin/sh
# Container entrypoint: web | worker | migrate | manage <args>
set -eu

case "${1:-web}" in
  web)
    exec gunicorn -c /app/backend/gunicorn.conf.py config.wsgi
    ;;
  worker)
    # Background jobs and the nightly schedule. Uses the direct (non-pooled)
    # database connection, set as DATABASE_URL for this container.
    exec python manage.py procrastinate worker --queues=default,maintenance
    ;;
  migrate)
    python manage.py wait_for_db --timeout 120
    exec python manage.py migrate --noinput
    ;;
  manage)
    shift
    exec python manage.py "$@"
    ;;
  *)
    exec "$@"
    ;;
esac
