from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from django.contrib.contenttypes.models import ContentType
from django.db.models import OuterRef, Q, QuerySet, Subquery
from django.http import FileResponse, Http404, HttpResponse
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.permissions import HasRole
from apps.accounts.roles import Role
from apps.core.api import RequiresFlag, SoftDeleteViewSetMixin
from apps.core.models import AuditLog
from apps.core.pdf import pdf_response, safe_filename
from apps.core.views import AuditLogSerializer

from . import services
from .models import (
    IN_STOCK,
    Condition,
    FuelType,
    HourMeterReading,
    OwnershipRecord,
    StockStatus,
    Unit,
    UnitFile,
    normalize_serial,
)
from .pdf import spec_sheet_pdf
from .search import every_word
from .serializers import (
    HourReadingSerializer,
    OwnershipSerializer,
    TransferSerializer,
    UnitFileSerializer,
    UnitListSerializer,
    UnitSerializer,
    can_see_pricing,
)

FLAG = RequiresFlag("customers-units")

# Who may do what (enforced here; tested in tests/test_units_permissions.py).
CanEditUnits = HasRole(
    Role.ADMIN, Role.SALES, Role.SERVICE, read_roles=(Role.PARTS, Role.READ_ONLY)
)
CanRemoveUnits = HasRole(Role.ADMIN)
CanTransferOwnership = HasRole(Role.ADMIN, Role.SALES)

ORDERINGS = {
    "make": ["make", "model", "serial_number"],
    "newest": ["-created_at"],
    "year": ["-year", "make"],
    "capacity": ["capacity_lbs", "make"],
    "-capacity": ["-capacity_lbs", "make"],
    "hours": ["current_hours", "make"],
    "serial": ["serial_normalized"],
}
PRICE_ORDERINGS = {"price": ["asking_price", "make"], "-price": ["-asking_price", "make"]}


def annotate_units(qs: QuerySet[Unit]) -> QuerySet[Unit]:
    latest_reading = HourMeterReading.objects.filter(unit=OuterRef("pk")).order_by(
        "-reading_date", "-created_at"
    )
    open_owner = OwnershipRecord.objects.filter(unit=OuterRef("pk"), end_date__isnull=True)
    primary_photo = UnitFile.objects.filter(unit=OuterRef("pk"), kind=UnitFile.Kind.PHOTO).order_by(
        "-is_primary", "sort_order", "created_at"
    )
    return qs.annotate(
        current_hours=Subquery(latest_reading.values("hours")[:1]),
        current_hours_date=Subquery(latest_reading.values("reading_date")[:1]),
        owner_kind=Subquery(open_owner.values("owner_kind")[:1]),
        owner_customer_id=Subquery(open_owner.values("customer_id")[:1]),
        owner_name=Subquery(open_owner.values("customer__name")[:1]),
        primary_photo_id=Subquery(primary_photo.values("id")[:1]),
    )


def _number(value: str | None) -> Decimal | None:
    if not value:
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


class UnitViewSet(SoftDeleteViewSetMixin, viewsets.ModelViewSet[Unit]):
    model = Unit
    http_method_names = ["get", "post", "patch", "delete", "options"]

    def get_permissions(self) -> list[BasePermission]:
        if self.action in ("destroy", "restore"):
            return [FLAG(), CanRemoveUnits()]
        if self.action == "transfer":
            return [FLAG(), CanTransferOwnership()]
        return [FLAG(), CanEditUnits()]

    def get_serializer_class(self) -> Any:
        return UnitListSerializer if self.action == "list" else UnitSerializer

    def get_queryset(self) -> QuerySet[Unit]:
        qs = annotate_units(self.base_queryset())
        if self.action != "list":
            return qs
        p = self.request.query_params
        pricing = can_see_pricing({"request": self.request})

        scope = p.get("scope", "stock")
        if scope == "stock":
            qs = qs.filter(stock_status__in=IN_STOCK)
        elif scope == "customer":
            qs = qs.filter(owner_kind=OwnershipRecord.OwnerKind.CUSTOMER)  # type: ignore[misc]
        if status_value := p.get("status"):
            qs = qs.filter(stock_status=status_value)
        if q := p.get("q", "").strip():
            norm = normalize_serial(q)
            match = (
                Q(model__icontains=q)
                | Q(make__icontains=q)
                | Q(stock_number__iexact=q)
                | Q(card_customer_name__icontains=q)
                | Q(owner_name__icontains=q)
            )
            if norm:
                match |= Q(serial_normalized__contains=norm)
            if words := every_word(q, ("make", "model", "owner_name", "card_customer_name")):
                match |= words
            qs = qs.filter(match)
        for name in ("condition", "fuel_type", "make", "model"):
            if values := p.getlist(name):
                qs = qs.filter(**{f"{name}__in": [v for v in values if v]})
        if owner := p.get("owner"):
            qs = qs.filter(owner_customer_id=owner)  # type: ignore[misc]
        if p.get("needs_review") == "1":
            qs = qs.filter(needs_review=True)
        ranges = [
            ("capacity_lbs", _number(p.get("capacity_min")), _number(p.get("capacity_max"))),
            ("mast_lift_height_in", _number(p.get("lift_min")), _number(p.get("lift_max"))),
        ]
        if pricing:  # price filters would leak prices to roles that can't see them
            ranges.append(
                ("asking_price", _number(p.get("price_min")), _number(p.get("price_max")))
            )
        for field, low, high in ranges:
            if low is not None:
                qs = qs.filter(**{f"{field}__gte": low})
            if high is not None:
                qs = qs.filter(**{f"{field}__lte": high})
        orderings = {**ORDERINGS, **(PRICE_ORDERINGS if pricing else {})}
        return qs.order_by(*orderings.get(p.get("ordering", "make"), ORDERINGS["make"]), "id")

    # --- Duplicate serial warning -----------------------------------------------------------
    @action(detail=False, methods=["get"], url_path="serial-check")
    def serial_check(self, request: Request) -> Response:
        norm = normalize_serial(request.query_params.get("serial", ""))
        if not norm:
            return Response({"duplicates": []})
        qs = Unit.all_objects.filter(serial_normalized=norm)
        if exclude := request.query_params.get("exclude"):
            qs = qs.exclude(pk=exclude)
        return Response(
            {
                "duplicates": [
                    {
                        "id": str(u.pk),
                        "label": str(u),
                        "is_deleted": u.is_deleted,
                        "stock_status": u.stock_status,
                    }
                    for u in qs[:5]
                ]
            }
        )

    # --- Filter choices ------------------------------------------------------------------------
    @action(detail=False, methods=["get"])
    def facets(self, request: Request) -> Response:
        live = Unit.objects.all()
        makes = sorted({m for m in live.values_list("make", flat=True) if m})
        models: dict[str, list[str]] = {}
        for make, model in live.values_list("make", "model").distinct():
            if make and model:
                models.setdefault(make, []).append(model)
        return Response(
            {
                "makes": makes,
                "models": {k: sorted(v) for k, v in models.items()},
                "fuel_types": [{"value": v, "label": label} for v, label in FuelType.choices],
                "conditions": [{"value": v, "label": label} for v, label in Condition.choices],
                "stock_statuses": [
                    {"value": v, "label": label} for v, label in StockStatus.choices
                ],
                "can_see_pricing": can_see_pricing({"request": request}),
            }
        )

    # --- Hour meter ------------------------------------------------------------------------------
    @action(detail=True, methods=["get", "post"])
    def hours(self, request: Request, pk: str | None = None) -> Response:
        unit = self.get_object()
        if request.method == "GET":
            return Response(HourReadingSerializer(unit.hour_readings.all(), many=True).data)
        data = HourReadingSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        result = services.record_hours(
            unit,
            hours=data.validated_data["hours"],
            reading_date=data.validated_data["reading_date"],
            source=data.validated_data.get("source", HourMeterReading.Source.MANUAL),
            note=data.validated_data.get("note", ""),
        )
        return Response(
            {"reading": HourReadingSerializer(result.reading).data, "warning": result.warning},
            status=status.HTTP_201_CREATED,
        )

    # --- Ownership -------------------------------------------------------------------------------
    @action(detail=True, methods=["get"])
    def ownership(self, request: Request, pk: str | None = None) -> Response:
        unit = self.get_object()
        return Response(
            OwnershipSerializer(unit.ownerships.select_related("customer"), many=True).data
        )

    @action(detail=True, methods=["post"])
    def transfer(self, request: Request, pk: str | None = None) -> Response:
        unit = self.get_object()
        data = TransferSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        record = services.transfer_ownership(unit, **data.validated_data)
        return Response(OwnershipSerializer(record).data, status=status.HTTP_201_CREATED)

    # --- Files ------------------------------------------------------------------------------------
    @action(detail=True, methods=["get", "post"], parser_classes=[MultiPartParser, FormParser])
    def files(self, request: Request, pk: str | None = None) -> Response:
        unit = self.get_object()
        if request.method == "GET":
            return Response(UnitFileSerializer(unit.files.all(), many=True).data)
        upload = request.FILES.get("file")
        if upload is None:
            raise serializers.ValidationError({"file": ["Choose a file to upload."]})
        kind = request.data.get("kind", UnitFile.Kind.PHOTO)
        if kind not in UnitFile.Kind.values:
            raise serializers.ValidationError({"kind": ["Unknown file type."]})
        record = services.add_file(
            unit, upload, kind=kind, caption=str(request.data.get("caption", ""))[:200]
        )
        return Response(UnitFileSerializer(record).data, status=status.HTTP_201_CREATED)

    # --- Printout ---------------------------------------------------------------------------------
    @action(detail=True, methods=["get"], url_path="spec-sheet")
    def spec_sheet(self, request: Request, pk: str | None = None) -> HttpResponse:
        """Printable spec sheet. `?price=1` adds the asking price (admin and sales only)."""
        unit = self.get_object()
        price = request.query_params.get("price") == "1"
        if price and not can_see_pricing({"request": request}):
            raise PermissionDenied("Only admin and sales can print prices.")
        name = "-".join(x for x in [unit.make, unit.model, unit.serial_number] if x) or "unit"
        return pdf_response(
            spec_sheet_pdf(unit, price=price), safe_filename(f"{name}-spec-sheet.pdf")
        )

    # --- History ----------------------------------------------------------------------------------
    @action(detail=True, methods=["get"])
    def history(self, request: Request, pk: str | None = None) -> Response:
        unit = self.get_object()
        entries = AuditLog.objects.filter(
            content_type=ContentType.objects.get_for_model(Unit), object_id=str(unit.pk)
        ).select_related("actor", "content_type")[:100]
        rows = AuditLogSerializer(entries, many=True).data
        if not can_see_pricing({"request": request}):
            for row in rows:
                for side in ("before", "after"):
                    if isinstance(row.get(side), dict):
                        row[side] = {
                            k: v for k, v in row[side].items() if k not in Unit.PRICE_FIELDS
                        }
                row["changed_fields"] = [
                    f for f in row["changed_fields"] if f not in Unit.PRICE_FIELDS
                ]
        return Response(rows)


class HourReadingViewSet(SoftDeleteViewSetMixin, viewsets.GenericViewSet[HourMeterReading]):
    """Remove a mistaken reading (admins only; it stays in the audit log)."""

    model = HourMeterReading
    serializer_class = HourReadingSerializer
    permission_classes = [FLAG, CanRemoveUnits]

    def get_queryset(self) -> Any:
        return self.base_queryset()

    def destroy(self, request: Request, pk: str | None = None) -> Response:
        reading = self.get_object()
        reading.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class UnitFileViewSet(SoftDeleteViewSetMixin, viewsets.ModelViewSet[UnitFile]):
    model = UnitFile
    serializer_class = UnitFileSerializer
    http_method_names = ["get", "patch", "delete", "options"]

    def get_permissions(self) -> list[BasePermission]:
        return [FLAG(), CanEditUnits()]

    def get_queryset(self) -> Any:
        return self.base_queryset().filter(unit__deleted_at__isnull=True)

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        raise Http404  # files are listed per unit

    def partial_update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        record = self.get_object()
        if request.data.get("is_primary") is True:
            if record.kind != UnitFile.Kind.PHOTO:
                raise serializers.ValidationError(
                    {"is_primary": ["Only a photo can be the main photo."]}
                )
            services.make_primary_photo(record)
        return super().partial_update(request, *args, **kwargs)

    @action(detail=True, methods=["get"])
    def content(self, request: Request, pk: str | None = None) -> FileResponse:
        """Stream the file through the app, so access is permission-checked and
        the browser never needs direct access to the storage bucket."""
        record = self.get_object()
        thumb = request.query_params.get("size") == "thumb" and record.thumbnail
        field = record.thumbnail if thumb else record.file
        content_type = "image/webp" if thumb else record.content_type
        try:
            handle = field.open("rb")
        except FileNotFoundError as exc:
            raise Http404 from exc
        response = FileResponse(handle, content_type=content_type)
        response["Content-Disposition"] = "inline"
        response["Cache-Control"] = "private, max-age=3600"
        response["X-Content-Type-Options"] = "nosniff"
        return response
