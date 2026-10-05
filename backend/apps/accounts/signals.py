"""Write sign-in events to the audit log (covers the Django admin too)."""

from __future__ import annotations

from typing import Any

from axes.signals import user_locked_out
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from apps.core.context import get_context
from apps.core.models import AuditLog


@receiver(user_logged_in)
def on_login(sender: Any, request: Any, user: Any, **kwargs: Any) -> None:
    ctx = get_context()
    ctx.user_id = user.pk
    ctx.user_role = getattr(user, "role", "")
    AuditLog.record(AuditLog.Action.LOGIN, user, actor=user)


@receiver(user_logged_out)
def on_logout(sender: Any, request: Any, user: Any, **kwargs: Any) -> None:
    if user is not None:
        AuditLog.record(AuditLog.Action.LOGOUT, user, actor=user)


@receiver(user_login_failed)
def on_login_failed(
    sender: Any, credentials: dict[str, Any], request: Any = None, **kwargs: Any
) -> None:
    username = str(credentials.get("username") or credentials.get("email") or "")[:200]
    AuditLog.record(AuditLog.Action.LOGIN_FAILED, None, object_repr=username)


@receiver(user_locked_out)
def on_locked_out(sender: Any, request: Any, username: str, ip_address: str, **kwargs: Any) -> None:
    AuditLog.record(AuditLog.Action.LOCKED_OUT, None, object_repr=str(username)[:200])
