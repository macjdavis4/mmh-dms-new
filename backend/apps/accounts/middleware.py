from __future__ import annotations

import re
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse, JsonResponse

from .permissions import is_verified

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
