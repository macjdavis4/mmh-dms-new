"""API-key authentication and rate limiting for the import API."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.utils import timezone
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.throttling import SimpleRateThrottle

from .models import ApiKey, hash_key
from .permissions import IMPORT_ROLES


class ApiKeyAuthentication(BaseAuthentication):
    """`Authorization: Api-Key mmh_…`. The request acts as the admin who made the key."""

    keyword = "api-key"

    def authenticate(self, request: Request) -> tuple[Any, ApiKey] | None:
        header = get_authorization_header(request).decode(errors="ignore").split()
        if not header or header[0].lower() != self.keyword:
            return None
        if len(header) != 2:
            raise AuthenticationFailed("Send the key as: Authorization: Api-Key <key>.")
        key = (
            ApiKey.all_objects.filter(key_hash=hash_key(header[1]))
            .select_related("created_by")
            .first()
        )
        if key is None or not key.is_active:
            raise AuthenticationFailed("Unknown or revoked API key.")
        user = key.created_by  # type: ignore[attr-defined]
        if user is None or not user.is_active or getattr(user, "role", "") not in IMPORT_ROLES:
            raise AuthenticationFailed("The person who created this key can no longer import.")
        now = timezone.now()
        if key.last_used_at is None or now - key.last_used_at > timedelta(minutes=5):
            key.last_used_at = now
            key.save(update_fields=["last_used_at"])
        return user, key

    def authenticate_header(self, request: Request) -> str:
        return "Api-Key"


class HasApiKey(BasePermission):
    def has_permission(self, request: Request, view: Any) -> bool:
        return isinstance(request.auth, ApiKey)


class ApiKeyThrottle(SimpleRateThrottle):
    scope = "import-api"

    def get_cache_key(self, request: Request, view: Any) -> str | None:
        if isinstance(request.auth, ApiKey):
            return f"throttle_import_api_{request.auth.pk}"
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}
