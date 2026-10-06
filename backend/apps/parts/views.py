from __future__ import annotations

from typing import Any

from django.db.models import Count, DecimalField, F, Q, QuerySet, Value
from django.db.models.functions import Coalesce
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.permissions import HasRole
from apps.accounts.roles import Role
from apps.core.api import RequiresFlag, SoftDeleteViewSetMixin, flag_enabled

from . import services, stock
from .models import Bin, Part, StockCheck, StockMovement, normalize_number
from .serializers import (
    BinSerializer,
    CountSerializer,
    PartListSerializer,
    PartSerializer,
    ReceiveSerializer,
    ReverseSerializer,
    StockCheckSerializer,
    StockMovementSerializer,
    WorkOrderPartSerializer,
    can_see_cost,
)

FLAG = RequiresFlag("parts")
STOCK_FLAG = RequiresFlag("parts-stock")

# Parts staff and admins keep the catalog; everyone else can look things up.
# Tested in tests/test_parts.py.
CanEditParts = HasRole(
    Role.ADMIN, Role.PARTS, read_roles=(Role.SALES, Role.SERVICE, Role.READ_ONLY)
)

# Receiving, counting and reversing: parts staff and admins. Putting parts on a
# work order or back on the shelf: mechanics too. Everyone can see stock.
CanKeepStock = HasRole(
    Role.ADMIN, Role.PARTS, read_roles=(Role.SALES, Role.SERVICE, Role.READ_ONLY)
)
CanUseParts = HasRole(Role.ADMIN, Role.PARTS, Role.SERVICE, read_roles=(Role.SALES, Role.READ_ONLY))
CanCheckStock = HasRole(
    Role.ADMIN, read_roles=(Role.PARTS, Role.SALES, Role.SERVICE, Role.READ_ONLY)
)

ON_HAND = Coalesce(
    F("stock__on_hand"), Value(0), output_field=DecimalField(max_digits=12, decimal_places=2)
)

ORDERINGS = {
    "number": ["number_normalized", "manufacturer"],
    "description": ["description", "number_normalized"],
    "bin": ["bin__code", "number_normalized"],
    "newest": ["-created_at"],
    "on_hand": ["stock_on_hand", "number_normalized"],
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
        qs = (
            self.base_queryset()
            .select_related("bin", "superseded_by")
            .annotate(stock_on_hand=ON_HAND)
        )
        if self.action == "low_stock":
            return qs.filter(
                reorder_point__isnull=False, stock_on_hand__lte=F("reorder_point")
            ).order_by("bin__code", "number_normalized", "id")
        if self.action != "list":
            return qs
        p = self.request.query_params
        if p.get("replaced") != "1":
            qs = qs.filter(superseded_by__isnull=True)
        if category := p.get("category"):
            qs = qs.filter(category=category)
        if bin_id := p.get("bin"):
            qs = qs.filter(bin_id=bin_id)
        if p.get("stock") == "low":
            qs = qs.filter(reorder_point__isnull=False, stock_on_hand__lte=F("reorder_point"))
        elif p.get("stock") == "in":
            qs = qs.filter(stock_on_hand__gt=0)
        elif p.get("stock") == "out":
            qs = qs.filter(stock_on_hand__lte=0)
        if q := p.get("q", "").strip():
            qs = qs.filter(search_filter(q)).distinct()
        ordering = ORDERINGS.get(p.get("ordering", "number"), ORDERINGS["number"])
        return qs.order_by(*ordering, "id")

    def _respond(self, part: Part, code: int = status.HTTP_200_OK) -> Response:
        fresh = (
            self.base_queryset()
            .select_related("bin", "superseded_by")
            .annotate(stock_on_hand=ON_HAND)
            .get(pk=part.pk)
        )
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
        if stock.on_hand(instance) > 0:
            raise serializers.ValidationError(
                {"on_hand": ["This part is still in stock. Count it to zero first."]}
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

    @action(detail=False, methods=["get"], url_path="low-stock")
    def low_stock(self, request: Request) -> Response:
        """At or below the reorder point, by bin, with the last nightly check."""
        if not flag_enabled("parts-stock", request.user):
            raise NotFound("This feature is turned off.")
        parts = PartListSerializer(
            self.get_queryset(), many=True, context=self.get_serializer_context()
        ).data
        last = StockCheck.objects.first()
        return Response(
            {
                "results": parts,
                "last_check": StockCheckSerializer(last).data if last else None,
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


class StockMovementViewSet(mixins.ListModelMixin, viewsets.GenericViewSet[StockMovement]):
    """The stock ledger: read it, and add to it. Lines are never changed."""

    serializer_class = StockMovementSerializer

    def get_permissions(self) -> list[BasePermission]:
        if self.action in ("issue", "give_back"):
            return [FLAG(), STOCK_FLAG(), CanUseParts()]
        if self.action == "check":
            return [FLAG(), STOCK_FLAG(), CanCheckStock()]
        return [FLAG(), STOCK_FLAG(), CanKeepStock()]

    def get_queryset(self) -> QuerySet[StockMovement]:
        qs = StockMovement.objects.select_related("part", "work_order", "created_by", "reversed_by")
        p = self.request.query_params
        if part := p.get("part"):
            qs = qs.filter(part_id=part)
        if work_order := p.get("work_order"):
            qs = qs.filter(work_order_id=work_order)
        if kind := p.get("kind"):
            qs = qs.filter(kind=kind)
        return qs.order_by("-occurred_at", "-created_at")

    def _created(self, movement: StockMovement) -> Response:
        fresh = self.get_queryset().get(pk=movement.pk)
        return Response(
            StockMovementSerializer(fresh, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["post"])
    def receive(self, request: Request) -> Response:
        data = ReceiveSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        unit_cost = v.get("unit_cost") if can_see_cost({"request": request}) else None
        movement = stock.receive(
            v["part"], v["quantity"], unit_cost=unit_cost, reference=v["reference"], note=v["note"]
        )
        return self._created(movement)

    @action(detail=False, methods=["post"])
    def count(self, request: Request) -> Response:
        data = CountSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        return self._created(stock.count(v["part"], v["counted"], note=v["note"]))

    @action(detail=False, methods=["post"])
    def issue(self, request: Request) -> Response:
        data = WorkOrderPartSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        return self._created(stock.issue(v["part"], v["work_order"], v["quantity"], note=v["note"]))

    @action(detail=False, methods=["post"], url_path="return")
    def give_back(self, request: Request) -> Response:
        data = WorkOrderPartSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        movement = stock.return_to_stock(v["part"], v["work_order"], v["quantity"], note=v["note"])
        return self._created(movement)

    @action(detail=True, methods=["post"])
    def reverse(self, request: Request, pk: str | None = None) -> Response:
        movement = self.get_object()
        data = ReverseSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return self._created(stock.reverse(movement, note=data.validated_data["note"]))

    @action(detail=False, methods=["get", "post"])
    def check(self, request: Request) -> Response:
        """GET: the last nightly check. POST (admin): run one now."""
        run = stock.check_drift() if request.method == "POST" else StockCheck.objects.first()
        return Response(StockCheckSerializer(run).data if run else None)
