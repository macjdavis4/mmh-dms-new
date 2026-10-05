from __future__ import annotations

from typing import Any

from django.db.models import Prefetch, Q, QuerySet
from django.http import HttpResponse
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.permissions import HasRole
from apps.accounts.roles import Role
from apps.core.api import RequiresFlag, SoftDeleteViewSetMixin
from apps.core.pdf import pdf_response, safe_filename
from apps.units.models import normalize_serial

from . import services
from .models import Quote, QuoteLine, Sale, TradeIn
from .pdf import quote_pdf
from .serializers import (
    QuoteListSerializer,
    QuoteSerializer,
    RecordSaleSerializer,
    SaleSerializer,
    StatusSerializer,
)

FLAG = RequiresFlag("sales")

# Quotes and sales carry prices, so only admin and sales see them
# (CLAUDE.md). Tested in tests/test_sales.py.
CanSell = HasRole(Role.ADMIN, Role.SALES)
AdminOnly = HasRole(Role.ADMIN)

SCOPES = {
    "open": Q(status__in=Quote.OPEN_STATUSES),
    "sold": Q(status=Quote.Status.SOLD),
    "closed": Q(status__in=[Quote.Status.DECLINED, Quote.Status.CANCELLED]),
    "all": Q(),
}


def _search(q: str) -> Q:
    match = (
        Q(number__icontains=q)
        | Q(customer__name__icontains=q)
        | Q(attention__icontains=q)
        | Q(customer_po__iexact=q)
        | Q(lines__unit__model__icontains=q, lines__deleted_at__isnull=True)
        | Q(sales__number__iexact=q)
        | Q(sales__invoice_number__iexact=q)
    )
    if norm := normalize_serial(q):
        match |= Q(lines__unit__serial_normalized__contains=norm, lines__deleted_at__isnull=True)
    return match


class QuoteViewSet(SoftDeleteViewSetMixin, viewsets.ModelViewSet[Quote]):
    model = Quote
    http_method_names = ["get", "post", "patch", "delete", "options"]

    def get_permissions(self) -> list[BasePermission]:
        if self.action in ("destroy", "restore"):
            return [FLAG(), AdminOnly()]
        return [FLAG(), CanSell()]

    def get_serializer_class(self) -> Any:
        return QuoteListSerializer if self.action == "list" else QuoteSerializer

    def get_queryset(self) -> QuerySet[Quote]:
        qs = self.base_queryset().select_related("customer", "salesperson")
        if self.action != "list":
            return qs
        qs = qs.prefetch_related(
            Prefetch("lines", queryset=QuoteLine.objects.select_related("unit")),
            Prefetch("trade_ins", queryset=TradeIn.objects.all()),
            "sales",
        )
        p = self.request.query_params
        qs = qs.filter(SCOPES.get(p.get("scope", "open"), SCOPES["open"]))
        if customer := p.get("customer"):
            qs = qs.filter(customer_id=customer)
        if unit := p.get("unit"):
            qs = qs.filter(
                Q(lines__unit_id=unit, lines__deleted_at__isnull=True)
                | Q(trade_ins__unit_id=unit, trade_ins__deleted_at__isnull=True)
            )
        if p.get("mine") == "1":
            qs = qs.filter(salesperson=self.request.user)
        if q := p.get("q", "").strip():
            qs = qs.filter(_search(q))
        return qs.distinct().order_by("-quote_date", "-number")

    def _respond(self, quote: Quote, code: int = status.HTTP_200_OK) -> Response:
        fresh = self.get_queryset().get(pk=quote.pk)
        return Response(
            QuoteSerializer(fresh, context=self.get_serializer_context()).data, status=code
        )

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        data = QuoteSerializer(data=request.data, context=self.get_serializer_context())
        data.is_valid(raise_exception=True)
        values = dict(data.validated_data)
        lines = values.pop("lines", [])
        trades = values.pop("trade_ins", [])
        quote = Quote(**values)
        if quote.salesperson_id is None:
            quote.salesperson = request.user  # type: ignore[assignment]
        services.save_quote(quote, lines=lines, trade_ins=trades)
        return self._respond(quote, status.HTTP_201_CREATED)

    def partial_update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        quote = self.get_object()
        data = QuoteSerializer(
            quote, data=request.data, partial=True, context=self.get_serializer_context()
        )
        data.is_valid(raise_exception=True)
        values = dict(data.validated_data)
        lines = values.pop("lines", None)
        trades = values.pop("trade_ins", None)
        for name, value in values.items():
            setattr(quote, name, value)
        services.save_quote(quote, lines=lines, trade_ins=trades)
        return self._respond(quote)

    @action(detail=True, methods=["post"], url_path="status")
    def set_status(self, request: Request, pk: str | None = None) -> Response:
        quote = self.get_object()
        data = StatusSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        services.set_status(quote, data.validated_data["status"])
        return self._respond(quote)

    @action(detail=True, methods=["get", "post"])
    def sell(self, request: Request, pk: str | None = None) -> Response:
        """GET: what would stop the sale. POST: record it."""
        quote = self.get_object()
        if request.method == "GET":
            return Response({"problems": services.sale_problems(quote)})
        data = RecordSaleSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        result = services.record_sale(
            quote,
            sale_date=data.validated_data["sale_date"],
            invoice_number=data.validated_data["invoice_number"],
            hours={str(k): v for k, v in data.validated_data["hours"].items()},
        )
        body = dict(QuoteSerializer(self.get_queryset().get(pk=quote.pk)).data)
        body["warnings"] = result.warnings
        return Response(body, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def pdf(self, request: Request, pk: str | None = None) -> HttpResponse:
        quote = self.get_object()
        return pdf_response(quote_pdf(quote), safe_filename(f"{quote.number}.pdf"))

    def perform_destroy(self, instance: Any) -> None:
        if instance.status == Quote.Status.SOLD:
            raise serializers.ValidationError(
                {"status": ["A sold quote can't be removed. Void the sale first."]}
            )
        super().perform_destroy(instance)


class SaleViewSet(viewsets.ReadOnlyModelViewSet[Sale]):
    serializer_class = SaleSerializer

    def get_permissions(self) -> list[BasePermission]:
        if self.action == "void":
            return [FLAG(), AdminOnly()]
        return [FLAG(), CanSell()]

    def get_queryset(self) -> QuerySet[Sale]:
        qs = Sale.objects.select_related("customer", "quote", "salesperson")
        p = self.request.query_params
        if (state := p.get("status")) in Sale.Status.values:
            qs = qs.filter(status=state)
        if customer := p.get("customer"):
            qs = qs.filter(customer_id=customer)
        return qs.order_by("-sale_date", "-number")

    @action(detail=True, methods=["post"])
    def void(self, request: Request, pk: str | None = None) -> Response:
        """Admins: undo the sale's changes of hands (body: {"reason": ...})."""
        sale = services.void_sale(self.get_object(), str(request.data.get("reason", "")))
        return Response(SaleSerializer(sale).data)
