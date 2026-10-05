from __future__ import annotations

from typing import Any

from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.request import Request

from .roles import Role


def is_verified(user: Any) -> bool:
    """True when this session signed in with a second factor (set by django-otp)."""
    check = getattr(user, "is_verified", None)
    if callable(check):
        return bool(check())
    # Right after otp_login() in the same request the middleware wrapper is not
    # there yet, but the device is attached to the user.
    return getattr(user, "otp_device", None) is not None


def _role(request: Request) -> str | None:
    user = request.user
    if not user or not user.is_authenticated:
        return None
    return getattr(user, "role", None)


class IsAuthenticatedAndVerified(BasePermission):
    """Signed in, active and, for roles that require it, verified with 2FA.
    (RequireAdminTwoFactorMiddleware also enforces 2FA before views run.)"""

    def has_permission(self, request: Request, view: Any) -> bool:
        user = request.user
        if not user or not user.is_authenticated or not user.is_active:
            return False
        return not (getattr(user, "requires_two_factor", False) and not is_verified(user))


def HasRole(*roles: str, read_roles: tuple[str, ...] = ()) -> type[BasePermission]:  # noqa: N802
    """Permission class allowing `roles` full access and `read_roles` GET only.

    permission_classes = [HasRole(Role.ADMIN, Role.SALES, read_roles=(Role.READ_ONLY,))]
    """
    allowed = frozenset(roles)
    readers = frozenset(read_roles) | allowed

    class _HasRole(IsAuthenticatedAndVerified):
        def has_permission(self, request: Request, view: Any) -> bool:
            if not super().has_permission(request, view):
                return False
            role = _role(request)
            if request.method in SAFE_METHODS:
                return role in readers
            return role in allowed

    _HasRole.__name__ = f"HasRole({','.join(sorted(allowed))})"
    return _HasRole


IsAdmin = HasRole(Role.ADMIN)
