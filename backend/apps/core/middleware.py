from __future__ import annotations

import logging
import re
import time
import uuid
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse, JsonResponse

from .context import RequestContext, get_context, reset_context, set_context

logger = logging.getLogger("mmh.request")

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
_UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}

Handler = Callable[[HttpRequest], HttpResponse]


def client_ip(request: HttpRequest) -> str:
    # Caddy overwrites X-Real-IP with the real client address (it trusts
    # Cloudflare's CF-Connecting-IP only from Cloudflare's IP ranges). The app
    # containers are not reachable except through Caddy.
    return request.META.get("HTTP_X_REAL_IP") or request.META.get("REMOTE_ADDR", "")


class RequestContextMiddleware:
    """Request ID, client IP, JSON access log line."""

    def __init__(self, get_response: Handler) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        incoming = request.META.get("HTTP_X_REQUEST_ID", "")
        request_id = incoming if _REQUEST_ID_RE.match(incoming) else uuid.uuid4().hex
        request.request_id = request_id  # type: ignore[attr-defined]
        token = set_context(
            RequestContext(
                request_id=request_id,
                ip=client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:300],
                source="web",
            )
        )
        start = time.monotonic()
        try:
            response = self.get_response(request)
            response["X-Request-ID"] = request_id
            if request.path not in ("/healthz", "/readyz"):
                logger.info(
                    "request",
                    extra={
                        "method": request.method,
                        "path": request.path,
                        "status": response.status_code,
                        "duration_ms": round((time.monotonic() - start) * 1000, 1),
                        "ip": get_context().ip,
                    },
                )
            return response
        finally:
            reset_context(token)


class AuditActorMiddleware:
    """Once the user is known, attribute every write in this request to them."""

    def __init__(self, get_response: Handler) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            ctx = get_context()
            ctx.user_id = user.pk
            ctx.user_role = getattr(user, "role", "")
        return self.get_response(request)


class SecurityHeadersMiddleware:
    def __init__(self, get_response: Handler) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        response.setdefault(
            "Permissions-Policy", "camera=(self), microphone=(), geolocation=(), payment=()"
        )
        if request.path.startswith("/api/"):
            response.setdefault("Cache-Control", "no-store")
        return response


# Requests allowed while read-only mode is on: signing in and out, and the
# admin switch that turns read-only mode back off.
_READ_ONLY_ALLOWED = (
    re.compile(r"^/api/v1/auth/"),
    re.compile(r"^/api/v1/admin/site-settings$"),
)


class ReadOnlyModeMiddleware:
    def __init__(self, get_response: Handler) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.method in _UNSAFE and not any(p.match(request.path) for p in _READ_ONLY_ALLOWED):
            from .models import SiteSettings

            if SiteSettings.is_read_only():
                return JsonResponse(
                    {
                        "code": "read_only",
                        "detail": "The system is in read-only mode. Changes are paused.",
                    },
                    status=503,
                )
        return self.get_response(request)
