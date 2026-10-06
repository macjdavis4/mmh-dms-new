"""API for supplier invoices: /parts-invoices and /parts-invoice-lines.

Invoices show what we pay, so only admin, parts and sales (who can see our
cost) may see them; admin and parts do the receiving. Tested in
tests/test_invoices.py."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db.models import Count, Q, QuerySet
from django.http import FileResponse, Http404
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.permissions import HasRole
from apps.accounts.roles import Role
from apps.core.api import RequiresFlag

from . import invoices
from .models import Invoice, InvoiceLine, Part
from .serializers import part_summary

FLAG = RequiresFlag("parts")
INVOICE_FLAG = RequiresFlag("parts-invoices")
CanReceiveInvoices = HasRole(Role.ADMIN, Role.PARTS, read_roles=(Role.SALES,))

S = Invoice.Status


# --- Serializers ---------------------------------------------------------------------------


class LineSerializer(serializers.ModelSerializer[InvoiceLine]):
    id = serializers.UUIDField(required=False)
    part = serializers.PrimaryKeyRelatedField(
        queryset=Part.objects.all(), required=False, allow_null=True
    )
    part_summary = serializers.SerializerMethodField()
    part_on_hand = serializers.SerializerMethodField()
    received = serializers.SerializerMethodField()
    outstanding = serializers.SerializerMethodField()
    amount = serializers.SerializerMethodField()

    class Meta:
        model = InvoiceLine
        fields = [
            "id",
            "position",
            "raw_text",
            "part",
            "part_summary",
            "part_on_hand",
            "part_number",
            "description",
            "quantity_shipped",
            "quantity_backordered",
            "unit_cost",
            "amount",
            "not_stocked",
            "check_reason",
            "received",
            "outstanding",
            "closed_at",
            "closed_reason",
        ]
        read_only_fields = [
            "position",
            "raw_text",
            "check_reason",
            "closed_at",
            "closed_reason",
        ]
        extra_kwargs = {
            "quantity_shipped": {"min_value": Decimal("0")},
            "quantity_backordered": {"min_value": Decimal("0")},
            "unit_cost": {"min_value": Decimal("0")},
        }

    def get_part_summary(self, obj: InvoiceLine) -> dict[str, Any] | None:
        return part_summary(obj.part)

    def get_part_on_hand(self, obj: InvoiceLine) -> str | None:
        if obj.part is None:
            return None
        stock = getattr(obj.part, "stock", None)
        return str(stock.on_hand) if stock else "0.00"

    def get_received(self, obj: InvoiceLine) -> str:
        return f"{invoices.received(obj):.2f}"

    def get_outstanding(self, obj: InvoiceLine) -> str:
        return f"{invoices.outstanding(obj):.2f}"

    def get_amount(self, obj: InvoiceLine) -> str | None:
        if obj.unit_cost is None:
            return None
        return str((obj.unit_cost * obj.quantity_shipped).quantize(Decimal("0.01")))

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        stocked = not attrs.get("not_stocked", False)
        shipped = attrs.get("quantity_shipped", Decimal("0"))
        backordered = attrs.get("quantity_backordered", Decimal("0"))
        if stocked and shipped + backordered <= 0:
            raise serializers.ValidationError(
                {"quantity_shipped": "Enter how many were shipped or backordered."}
            )
        if not any(str(attrs.get(f) or "").strip() for f in ("part_number", "description")) and (
            attrs.get("part") is None
        ):
            raise serializers.ValidationError({"description": "Say what the line is."})
        return attrs


class InvoiceListSerializer(serializers.ModelSerializer[Invoice]):
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    line_count = serializers.IntegerField(read_only=True, default=0)
    to_check = serializers.IntegerField(read_only=True, default=0)
    title = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = [
            "id",
            "title",
            "supplier",
            "invoice_number",
            "invoice_date",
            "status",
            "status_label",
            "total",
            "line_count",
            "to_check",
            "original_name",
            "read_error",
            "created_at",
        ]
        read_only_fields = fields

    def get_title(self, obj: Invoice) -> str:
        return str(obj)


class InvoiceSerializer(serializers.ModelSerializer[Invoice]):
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    title = serializers.SerializerMethodField()
    lines = LineSerializer(many=True, required=False)
    lines_total = serializers.SerializerMethodField()
    has_file = serializers.SerializerMethodField()
    has_receipts = serializers.SerializerMethodField()
    is_image = serializers.SerializerMethodField()
    duplicate = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = [
            "id",
            "title",
            "supplier",
            "invoice_number",
            "invoice_date",
            "status",
            "status_label",
            "freight",
            "tax",
            "total",
            "lines_total",
            "note",
            "cancel_reason",
            "original_name",
            "content_type",
            "has_file",
            "is_image",
            "read_method",
            "read_error",
            "read_at",
            "extracted_text",
            "has_receipts",
            "duplicate",
            "lines",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "cancel_reason",
            "original_name",
            "content_type",
            "read_method",
            "read_error",
            "read_at",
            "extracted_text",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "freight": {"min_value": Decimal("0")},
            "tax": {"min_value": Decimal("0")},
            "total": {"min_value": Decimal("0")},
        }

    def to_representation(self, instance: Invoice) -> dict[str, Any]:
        data = super().to_representation(instance)
        lines = invoices.with_received(
            instance.lines.select_related("part", "part__stock", "part__superseded_by")
        )
        data["lines"] = LineSerializer(lines, many=True).data
        return data

    def get_title(self, obj: Invoice) -> str:
        return str(obj)

    def get_lines_total(self, obj: Invoice) -> str:
        total = sum(
            ((line.unit_cost or Decimal("0")) * line.quantity_shipped for line in obj.lines.all()),
            Decimal("0"),
        )
        return str(Decimal(total).quantize(Decimal("0.01")))

    def get_has_file(self, obj: Invoice) -> bool:
        return bool(obj.file)

    def get_is_image(self, obj: Invoice) -> bool:
        return obj.content_type.startswith("image/")

    def get_has_receipts(self, obj: Invoice) -> bool:
        return invoices.has_receipts(obj)

    def get_duplicate(self, obj: Invoice) -> dict[str, str] | None:
        """Another invoice that looks like this one (warning while checking)."""
        dup = invoices.find_duplicate(obj.supplier, obj.invoice_number, exclude=obj.pk)
        return {"id": str(dup.pk), "label": str(dup)} if dup else None


class ReceiveRowSerializer(serializers.Serializer[Any]):
    line = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0"))


class ReceiveSerializer(serializers.Serializer[Any]):
    lines = ReceiveRowSerializer(many=True)
    update_costs = serializers.BooleanField(required=False, default=False)


class ReasonSerializer(serializers.Serializer[Any]):
    reason = serializers.CharField(max_length=200, allow_blank=True, required=False, default="")


class BackorderSerializer(LineSerializer):
    invoice_id = serializers.UUIDField(source="invoice.pk", read_only=True)
    invoice_label = serializers.CharField(source="invoice.__str__", read_only=True)
    invoice_date = serializers.DateField(source="invoice.invoice_date", read_only=True)
    supplier = serializers.CharField(source="invoice.supplier", read_only=True)

    class Meta(LineSerializer.Meta):
        fields = [
            *LineSerializer.Meta.fields,
            "invoice_id",
            "invoice_label",
            "invoice_date",
            "supplier",
        ]


# --- Views ---------------------------------------------------------------------------------


class InvoiceViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet[Invoice],
):
    http_method_names = ["get", "post", "patch", "options"]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_permissions(self) -> list[BasePermission]:
        return [FLAG(), INVOICE_FLAG(), CanReceiveInvoices()]

    def get_serializer_class(self) -> Any:
        return InvoiceListSerializer if self.action == "list" else InvoiceSerializer

    def get_queryset(self) -> QuerySet[Invoice]:
        qs = Invoice.objects.all()
        if self.action != "list":
            return qs
        qs = qs.annotate(
            line_count=Count("lines", filter=Q(lines__deleted_at__isnull=True)),
            to_check=Count(
                "lines", filter=Q(lines__deleted_at__isnull=True) & ~Q(lines__check_reason="")
            ),
        )
        p = self.request.query_params
        scope = p.get("status", "open")
        if scope == "open":
            qs = qs.filter(status__in=[S.READING, S.REVIEW, S.PARTIAL])
        elif scope in S.values:
            qs = qs.filter(status=scope)
        if q := p.get("q", "").strip():
            qs = qs.filter(
                Q(supplier__icontains=q)
                | Q(invoice_number__icontains=q)
                | Q(lines__part_number__icontains=q, lines__deleted_at__isnull=True)
                | Q(lines__part__part_number__icontains=q, lines__deleted_at__isnull=True)
            ).distinct()
        return qs.order_by("-created_at")

    def _respond(self, invoice: Invoice, code: int = status.HTTP_200_OK) -> Response:
        fresh = Invoice.objects.get(pk=invoice.pk)
        return Response(InvoiceSerializer(fresh, context=self.get_serializer_context()).data, code)

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Upload a file (multipart `file`), or start a blank one to type in."""
        supplier = str(request.data.get("supplier", ""))
        upload = request.FILES.get("file")
        invoice = (
            invoices.upload(upload, supplier=supplier)
            if upload is not None
            else invoices.create_blank(supplier=supplier)
        )
        return self._respond(invoice, status.HTTP_201_CREATED)

    def partial_update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        invoice = self.get_object()
        data = InvoiceSerializer(
            invoice, data=request.data, partial=True, context=self.get_serializer_context()
        )
        data.is_valid(raise_exception=True)
        values = dict(data.validated_data)
        lines = values.pop("lines", None)
        invoices.save_invoice(invoice, values, lines)
        return self._respond(invoice)

    @action(detail=True, methods=["post"])
    def receive(self, request: Request, pk: str | None = None) -> Response:
        invoice = self.get_object()
        data = ReceiveSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        invoices.receive(
            invoice,
            data.validated_data["lines"],
            update_costs=data.validated_data["update_costs"],
        )
        return self._respond(invoice)

    @action(detail=True, methods=["post"], url_path="read-again")
    def read_again(self, request: Request, pk: str | None = None) -> Response:
        invoice = invoices.read_again(self.get_object())
        return self._respond(invoice)

    @action(detail=True, methods=["post"])
    def cancel(self, request: Request, pk: str | None = None) -> Response:
        data = ReasonSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        invoice = invoices.cancel(self.get_object(), data.validated_data["reason"])
        return self._respond(invoice)

    @action(detail=True, methods=["get"])
    def file(self, request: Request, pk: str | None = None) -> FileResponse:
        """The uploaded invoice, streamed through the app (permission-checked)."""
        invoice = self.get_object()
        if not invoice.file:
            raise Http404
        try:
            handle = invoice.file.open("rb")
        except FileNotFoundError as exc:
            raise Http404 from exc
        response = FileResponse(handle, content_type=invoice.content_type)
        response["Content-Disposition"] = "inline"
        response["Cache-Control"] = "private, max-age=3600"
        response["X-Content-Type-Options"] = "nosniff"
        return response

    @action(detail=False, methods=["get"])
    def backorders(self, request: Request) -> Response:
        """Everything still to come on invoices that have started receiving."""
        rows = invoices.backorders().select_related("part__stock")
        return Response(BackorderSerializer(rows, many=True).data)

    @action(detail=False, methods=["get"])
    def counts(self, request: Request) -> Response:
        base = Invoice.objects.all()
        return Response(
            {
                "to_check": base.filter(status__in=[S.READING, S.REVIEW]).count(),
                "partial": base.filter(status=S.PARTIAL).count(),
                "backorder_lines": invoices.backorders().count(),
            }
        )


class InvoiceLineViewSet(viewsets.GenericViewSet[InvoiceLine]):
    """Close the rest of a line (won't come), or reopen it."""

    serializer_class = LineSerializer

    def get_permissions(self) -> list[BasePermission]:
        return [FLAG(), INVOICE_FLAG(), CanReceiveInvoices()]

    def get_queryset(self) -> QuerySet[InvoiceLine]:
        return InvoiceLine.objects.select_related("invoice", "part")

    @action(detail=True, methods=["post"])
    def close(self, request: Request, pk: str | None = None) -> Response:
        data = ReasonSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        line = invoices.close_line(self.get_object(), data.validated_data["reason"])
        return Response(
            LineSerializer(invoices.with_received(InvoiceLine.objects).get(pk=line.pk)).data
        )

    @action(detail=True, methods=["post"])
    def reopen(self, request: Request, pk: str | None = None) -> Response:
        line = invoices.reopen_line(self.get_object())
        return Response(
            LineSerializer(invoices.with_received(InvoiceLine.objects).get(pk=line.pk)).data
        )
