from __future__ import annotations

from typing import Any

from django.db.models import Count, Q, QuerySet
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.permissions import HasRole
from apps.accounts.roles import Role
from apps.core.api import RequiresFlag, SoftDeleteViewSetMixin

from . import services
from .models import Bin, Part, normalize_number
from .serializers import BinSerializer, PartListSerializer, PartSerializer, can_see_cost

FLAG = RequiresFlag("parts")

# Parts staff and admins keep the catalog; everyone else can look things up.
# Tested in tests/test_parts.py.
CanEditParts = HasRole(
    Role.ADMIN, Role.PARTS, read_roles=(Role.SALES, Role.SERVICE, Role.READ_ONLY)
)

ORDERINGS = {
    "number": ["number_normalized", "manufacturer"],
    "description": ["description", "number_normalized"],
    "bin": ["bin__code", "number_normalized"],
    "newest": ["-created_at"],
}


def search_filter(q: str) -> Q:
    """Part number, cross reference, vendor's number (any punctuation), or words
    in the description, fits or vendor."""
    match = Q()
    for word in q.split():
        match &= (
            Q(description__icontains=word)
            | Q(fits__icontains=word)
            | Q(vendor__icontains=word)
            | Q(manufacturer__iexact=word)
        )
    if norm := normalize_number(q):
        match |= (
            Q(number_normalized__contains=norm)
            | Q(
                cross_references__number_normalized__contains=norm,
                cross_references__deleted_at__isnull=True,
            )
            | Q(vendor_part_number__icontains=q.strip())
        )
    return match


class PartViewSet(SoftDeleteViewSetMixin, viewsets.ModelViewSet[Part]):
    model = Part
    http_method_names = ["get", "post", "patch", "delete", "options"]

    def get_permissions(self) -> list[BasePermission]:
        return [FLAG(), CanEditParts()]

    def get_serializer_class(self) -> Any:
        return PartListSerializer if self.action == "list" else PartSerializer

    def get_queryset(self) -> QuerySet[Part]:
        qs = self.base_queryset().select_related("bin", "superseded_by")
        if self.action != "list":
            return qs
        p = self.request.query_params
        if p.get("replaced") != "1":
            qs = qs.filter(superseded_by__isnull=True)
        if category := p.get("category"):
            qs = qs.filter(category=category)
        if bin_id := p.get("bin"):
            qs = qs.filter(bin_id=bin_id)
        if q := p.get("q", "").strip():
            qs = qs.filter(search_filter(q)).distinct()
        ordering = ORDERINGS.get(p.get("ordering", "number"), ORDERINGS["number"])
        return qs.order_by(*ordering, "id")

    def _respond(self, part: Part, code: int = status.HTTP_200_OK) -> Response:
        fresh = self.base_queryset().select_related("bin", "superseded_by").get(pk=part.pk)
        return Response(PartSerializer(fresh, context=self.get_serializer_context()).data, code)

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        data = PartSerializer(data=request.data, context=self.get_serializer_context())
        data.is_valid(raise_exception=True)
        values = dict(data.validated_data)
        refs = values.pop("cross_references", [])
        part = Part(**values)
        services.save_part(part, cross_references=refs)
        return self._respond(part, status.HTTP_201_CREATED)

    def partial_update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        part = self.get_object()
        data = PartSerializer(
            part, data=request.data, partial=True, context=self.get_serializer_context()
        )
        data.is_valid(raise_exception=True)
        values = dict(data.validated_data)
        refs = values.pop("cross_references", None)
        for name, value in values.items():
            setattr(part, name, value)
        services.save_part(part, cross_references=refs)
        return self._respond(part)

    def perform_destroy(self, instance: Any) -> None:
        if instance.supersedes.exists():
            raise serializers.ValidationError(
                {"superseded_by": ["Other parts are replaced by this one. Change them first."]}
            )
        super().perform_destroy(instance)

    @action(detail=False, methods=["get"], url_path="number-check")
    def number_check(self, request: Request) -> Response:
        """Live duplicate warning while typing a part number."""
        p = request.query_params
        if not normalize_number(p.get("number", "")):
            return Response({"duplicates": []})
        dup = services.find_duplicate(p.get("manufacturer", ""), p["number"], p.get("exclude"))
        same_number = Part.all_objects.filter(number_normalized=normalize_number(p["number"]))
        if p.get("exclude"):
            same_number = same_number.exclude(pk=p["exclude"])
        return Response(
            {
                "duplicate": None
                if dup is None
                else {"id": str(dup.pk), "label": str(dup), "is_deleted": dup.is_deleted},
                "same_number": [
                    {"id": str(x.pk), "label": f"{x.manufacturer} {x.part_number}".strip()}
                    for x in same_number.exclude(pk=getattr(dup, "pk", None))[:5]
                ],
            }
        )

    @action(detail=False, methods=["get"])
    def facets(self, request: Request) -> Response:
        return Response(
            {
                "categories": [{"value": v, "label": lbl} for v, lbl in Part.Category.choices],
                "units": [{"value": v, "label": lbl} for v, lbl in Part.UnitOfMeasure.choices],
                "can_see_cost": can_see_cost({"request": request}),
            }
        )


class BinViewSet(SoftDeleteViewSetMixin, viewsets.ModelViewSet[Bin]):
    model = Bin
    serializer_class = BinSerializer
    pagination_class = None
    http_method_names = ["get", "post", "patch", "delete", "options"]

    def get_permissions(self) -> list[BasePermission]:
        return [FLAG(), CanEditParts()]

    def get_queryset(self) -> QuerySet[Bin]:
        return (
            self.base_queryset()
            .annotate(part_count=Count("parts", filter=Q(parts__deleted_at__isnull=True)))
            .order_by("code")
        )

    def perform_destroy(self, instance: Any) -> None:
        if instance.parts.exists():
            raise serializers.ValidationError(
                {"code": ["Parts are still in this bin. Move them first."]}
            )
        super().perform_destroy(instance)
