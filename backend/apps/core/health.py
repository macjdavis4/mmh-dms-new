"""Health endpoints.

/healthz  the process is alive (no dependencies checked).
/readyz   the database answers and every migration this code expects is applied.
          The deploy pipeline and uptime monitors use this one.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from django.conf import settings
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

logger = logging.getLogger("mmh.health")

# Once migrations are current for this code version they stay current, so the
# (relatively expensive) migration graph check is skipped after first success.
_migrations_current = False


def _check_database() -> tuple[bool, str]:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return True, "ok"
    except Exception as exc:  # noqa: BLE001 - any failure means not ready
        logger.warning("readyz database check failed", extra={"error": str(exc)})
        # Drop the broken connection so the next request reconnects cleanly.
        connection.close()
        return False, "unreachable"


def _check_migrations() -> tuple[bool, str]:
    global _migrations_current
    if _migrations_current:
        return True, "ok"
    try:
        executor = MigrationExecutor(connection)
        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
    except Exception as exc:  # noqa: BLE001
        logger.warning("readyz migration check failed", extra={"error": str(exc)})
        connection.close()
        return False, "unknown"
    if plan:
        return False, f"{len(plan)} pending"
    _migrations_current = True
    return True, "ok"


class HealthCheckMiddleware:
    """Answer /healthz and /readyz before host validation and HTTPS redirects.

    Docker, Caddy and the deploy script probe containers directly
    (Host: 127.0.0.1 or app-blue:8000), which ALLOWED_HOSTS would reject.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.method == "GET":
            if request.path == "/healthz":
                return healthz(request)
            if request.path == "/readyz":
                return readyz(request)
        return self.get_response(request)


@never_cache
@require_GET
def healthz(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok", "version": settings.APP_VERSION})


@never_cache
@require_GET
def readyz(request: HttpRequest) -> JsonResponse:
    db_ok, db_detail = _check_database()
    mig_ok, mig_detail = _check_migrations() if db_ok else (False, "skipped")
    ok = db_ok and mig_ok
    return JsonResponse(
        {
            "status": "ok" if ok else "unavailable",
            "version": settings.APP_VERSION,
            "checks": {"database": db_detail, "migrations": mig_detail},
        },
        status=200 if ok else 503,
    )
