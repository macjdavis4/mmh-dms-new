from __future__ import annotations

import re
import time
from collections.abc import Callable

from django.conf import settings
from django.contrib.auth import logout
from django.http import HttpRequest, HttpResponse, JsonResponse

from .permissions import is_verified
from .roles import has_any_role

SIGNED_IN_AT = "signed_in_at"

# While an admin has not completed two-factor sign-in they may only reach
# these: their own account info, 2FA setup, sign-out, and the app shell.
_ALLOWED = re.compile(r"^/(healthz|readyz|static/.*|api/v1/auth/.*|api/v1/system/status)$")


class RequireAdminTwoFactorMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        user = getattr(request, "user", None)
        if (
            user is not None
            and user.is_authenticated
            and getattr(user, "requires_two_factor", False)
            and not is_verified(user)
            and not _ALLOWED.match(request.path)
            and request.path.startswith(("/api/", "/django-admin/"))
        ):
            return JsonResponse(
                {
                    "code": "two_factor_setup_required",
                    "detail": "Set up two-factor authentication to continue.",
                },
                status=403,
            )
        return self.get_response(request)


class SessionLifetimeMiddleware:
    """A hard limit on how long one sign-in lasts, however busy it is.

    Sessions already end after 12 hours without use (SESSION_COOKIE_AGE), but a
    session in daily use, or a copied session cookie, would otherwise last for
    ever, and a stolen cookie gets past 2FA. So: admins sign in again after
    SESSION_MAX_AGE_ADMIN, everyone else after SESSION_MAX_AGE."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            now = int(time.time())
            started = request.session.get(SIGNED_IN_AT)
            if not isinstance(started, int):
                # Signed in before this limit existed: start the clock now.
                request.session[SIGNED_IN_AT] = now
            else:
                limit = (
                    settings.SESSION_MAX_AGE_ADMIN
                    if has_any_role(user, ("admin",))
                    else settings.SESSION_MAX_AGE
                )
                if now - started > limit:
                    logout(request)  # flushes the session; the request goes on signed out
        return self.get_response(request)
