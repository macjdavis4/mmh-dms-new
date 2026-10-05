from __future__ import annotations

from typing import Any

from django.db import IntegrityError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from .models import AuditBypassError


def exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    """DRF errors always carry a machine-readable `code` and a plain `detail`."""
    if isinstance(exc, IntegrityError):
        return Response(
            {"code": "conflict", "detail": "That change conflicts with existing data."},
            status=status.HTTP_409_CONFLICT,
        )
    if isinstance(exc, AuditBypassError):
        return Response(
            {"code": "not_allowed", "detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST
        )
    response = drf_exception_handler(exc, context)
    if response is None:
        return None
    data = response.data
    if isinstance(data, dict) and "detail" in data:
        detail = data["detail"]
        code = getattr(detail, "code", None) or "error"
        response.data = {"code": str(code), "detail": str(detail)}
    elif isinstance(data, (dict, list)):
        response.data = {
            "code": "invalid",
            "detail": "Please fix the highlighted fields.",
            "fields": data,
        }
    return response
