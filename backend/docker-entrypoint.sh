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
    exec python manage.py procrastinate worker --queues=default,maintenance,imports
    ;;
  migrate)
    # In production this runs as the database owner (ADMIN_DATABASE_URL),
    # then gives the app's limited user access to any new tables.
    python manage.py wait_for_db --timeout 120
    python manage.py migrate --noinput
    if [ -n "${APP_DB_ROLE:-}" ]; then
      python manage.py grant_app_privileges "$APP_DB_ROLE"
    fi
    ;;
  manage)
    shift
    exec python manage.py "$@"
    ;;
  *)
    exec "$@"
    ;;
esac
