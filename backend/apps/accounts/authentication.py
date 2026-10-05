from __future__ import annotations

from typing import Any

from django.http import HttpRequest
from rest_framework.authentication import SessionAuthentication
from rest_framework.request import Request


class CsrfSessionAuthentication(SessionAuthentication):
    """Session cookie auth with CSRF enforced. Returns 401 (not 403) when
    the visitor is not signed in, so the app can send them to the sign-in page."""

    def authenticate_header(self, request: Request) -> str:
        return 'Session realm="mmh"'


def axes_username(request: HttpRequest, credentials: dict[str, Any] | None) -> str:
    """Lock accounts by normalized email address."""
    creds = credentials or {}
    raw = creds.get("username") or creds.get("email") or ""
    return str(raw).strip().lower()
