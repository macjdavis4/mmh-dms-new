"""Shared DRF building blocks for feature apps."""

from __future__ import annotations

from typing import Any

from django.db import transaction
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.response import Response

from .models import FeatureFlag, SoftDeleteModel


def flag_enabled(key: str, user: Any) -> bool:
    """A missing flag counts as on: flags exist to switch features *off*."""
    flag = FeatureFlag.objects.filter(key=key).first()
    return True if flag is None else flag.is_on_for(user)


def RequiresFlag(key: str) -> type[BasePermission]:  # noqa: N802
    """Endpoints of a switched-off feature answer 404, as if they don't exist."""

    class _RequiresFlag(BasePermission):
        def has_permission(self, request: Request, view: Any) -> bool:
            if not flag_enabled(key, request.user):
                raise NotFound("This feature is turned off.")
            return True

    _RequiresFlag.__name__ = f"RequiresFlag({key})"
    return _RequiresFlag


class SoftDeleteViewSetMixin:
    """DELETE soft-deletes; POST {id}/restore brings it back (same permission
    as delete). `?include_deleted=1` lists removed rows too."""

    model: type[SoftDeleteModel]

    def include_deleted(self) -> bool:
        return self.request.query_params.get("include_deleted") == "1"  # type: ignore[attr-defined,no-any-return]

    def base_queryset(self) -> Any:
        manager = self.model.all_objects if self.include_deleted() else self.model.objects
        return manager.all()

    def perform_destroy(self, instance: SoftDeleteModel) -> None:
        instance.soft_delete()

    @action(detail=True, methods=["post"])
    def restore(self, request: Request, pk: str | None = None) -> Response:
        obj = self.model.all_objects.filter(pk=self.kwargs["pk"]).first()  # type: ignore[attr-defined]
        if obj is None:
            raise NotFound()
        self.check_object_permissions(request, obj)  # type: ignore[attr-defined]
        with transaction.atomic():
            obj.restore()
        serializer = self.get_serializer(obj)  # type: ignore[attr-defined]
        return Response(serializer.data, status=status.HTTP_200_OK)
