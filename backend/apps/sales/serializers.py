from __future__ import annotations

from decimal import Decimal
from typing import Any

from rest_framework import serializers

from apps.customers.models import Customer
from apps.units.models import Unit

from .models import Quote, QuoteLine, Sale, TradeIn
from .totals import quote_totals


def _name(user: Any) -> str:
    return (getattr(user, "full_name", "") or getattr(user, "email", "")) if user else ""


def unit_summary(unit: Unit | None) -> dict[str, Any] | None:
    if unit is None:
        return None
    return {
        "id": str(unit.pk),
        "make": unit.make,
        "model": unit.model,
        "serial_number": unit.serial_number,
        "stock_number": unit.stock_number,
        "year": unit.year,
        "condition": unit.condition,
        "stock_status": unit.stock_status,
    }


class QuoteLineSerializer(serializers.ModelSerializer[QuoteLine]):
    id = serializers.UUIDField(required=False)
    unit = serializers.PrimaryKeyRelatedField(
        queryset=Unit.objects.all(), required=False, allow_null=True
    )
    unit_summary = serializers.SerializerMethodField()
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = QuoteLine
        fields = [
            "id",
            "kind",
            "kind_label",
            "unit",
            "unit_summary",
            "description",
            "quantity",
            "unit_price",
            "taxable",
            "amount",
        ]

    def get_unit_summary(self, obj: QuoteLine) -> dict[str, Any] | None:
        return unit_summary(obj.unit)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        kind = attrs.get("kind", QuoteLine.Kind.OTHER)
        price = attrs.get("unit_price", Decimal("0"))
        if kind == QuoteLine.Kind.UNIT:
            if not attrs.get("unit"):
                raise serializers.ValidationError({"unit": ["Pick the unit."]})
            attrs["quantity"] = Decimal("1")
        else:
            attrs["unit"] = None
            if not (attrs.get("description") or "").strip():
                raise serializers.ValidationError({"description": ["Say what it is."]})
        if attrs.get("quantity", Decimal("1")) <= 0:
            raise serializers.ValidationError({"quantity": ["Must be more than zero."]})
        if kind == QuoteLine.Kind.DISCOUNT:
            attrs["unit_price"] = -abs(price)  # a discount always takes money off
        elif price < 0:
            raise serializers.ValidationError(
                {"unit_price": ["Can't be negative. Add a discount line instead."]}
            )
        return attrs


class TradeInSerializer(serializers.ModelSerializer[TradeIn]):
    id = serializers.UUIDField(required=False)
    unit = serializers.PrimaryKeyRelatedField(
        queryset=Unit.objects.all(), required=False, allow_null=True
    )
    unit_summary = serializers.SerializerMethodField()

    class Meta:
        model = TradeIn
        fields = [
            "id",
            "unit",
            "unit_summary",
            "make",
            "model",
            "serial_number",
            "year",
            "hours",
            "description",
            "allowance",
            "payoff",
            "payoff_to",
        ]

    def get_unit_summary(self, obj: TradeIn) -> dict[str, Any] | None:
        return unit_summary(obj.unit)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if not attrs.get("unit") and not any(
            (attrs.get(k) or "").strip() for k in ("serial_number", "model")
        ):
            raise serializers.ValidationError(
                {"serial_number": ["Pick the unit, or enter at least its model or serial."]}
            )
        return attrs


def sale_summary(sale: Sale | None) -> dict[str, Any] | None:
    if sale is None:
        return None
    return {
        "id": str(sale.pk),
        "number": sale.number,
        "status": sale.status,
        "sale_date": sale.sale_date.isoformat(),
        "invoice_number": sale.invoice_number,
        "total": str(sale.total),
        "void_reason": sale.void_reason,
    }


class QuoteSerializer(serializers.ModelSerializer[Quote]):
    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all())
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    salesperson_name = serializers.SerializerMethodField()
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    lines = QuoteLineSerializer(many=True, required=False)
    trade_ins = TradeInSerializer(many=True, required=False)
    totals = serializers.SerializerMethodField()
    is_expired = serializers.BooleanField(read_only=True)
    is_open = serializers.BooleanField(read_only=True)
    sale = serializers.SerializerMethodField()
    past_sales = serializers.SerializerMethodField()

    class Meta:
        model = Quote
        fields = [
            "id",
            "number",
            "customer",
            "customer_name",
            "salesperson",
            "salesperson_name",
            "status",
            "status_label",
            "quote_date",
            "valid_until",
            "attention",
            "customer_po",
            "tax_rate",
            "tax_exempt",
            "tax_exempt_number",
            "terms",
            "notes",
            "sent_at",
            "decided_at",
            "lines",
            "trade_ins",
            "totals",
            "is_expired",
            "is_open",
            "sale",
            "past_sales",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "number", "status", "sent_at", "decided_at"]

    def to_representation(self, instance: Quote) -> dict[str, Any]:
        data = super().to_representation(instance)
        data["lines"] = QuoteLineSerializer(instance.lines.select_related("unit"), many=True).data
        data["trade_ins"] = TradeInSerializer(
            instance.trade_ins.select_related("unit"), many=True
        ).data
        return data

    def get_salesperson_name(self, obj: Quote) -> str:
        return _name(obj.salesperson)

    def get_totals(self, obj: Quote) -> dict[str, str]:
        return quote_totals(obj).as_dict()

    def get_sale(self, obj: Quote) -> dict[str, Any] | None:
        return sale_summary(obj.sales.filter(status=Sale.Status.COMPLETED).first())

    def get_past_sales(self, obj: Quote) -> list[dict[str, Any]]:
        voided = obj.sales.filter(status=Sale.Status.VOIDED)
        return [s for s in (sale_summary(v) for v in voided) if s]

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        quote_date = attrs.get("quote_date", getattr(self.instance, "quote_date", None))
        valid_until = attrs.get("valid_until", getattr(self.instance, "valid_until", None))
        if quote_date and valid_until and valid_until < quote_date:
            raise serializers.ValidationError(
                {"valid_until": ["Must be on or after the quote date."]}
            )
        return attrs


class QuoteListSerializer(serializers.ModelSerializer[Quote]):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    salesperson_name = serializers.SerializerMethodField()
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    total = serializers.SerializerMethodField()
    units = serializers.SerializerMethodField()
    trade_in_count = serializers.SerializerMethodField()
    sale_number = serializers.SerializerMethodField()

    class Meta:
        model = Quote
        fields = [
            "id",
            "number",
            "customer",
            "customer_name",
            "salesperson_name",
            "status",
            "status_label",
            "quote_date",
            "valid_until",
            "is_expired",
            "total",
            "units",
            "trade_in_count",
            "sale_number",
        ]

    def get_salesperson_name(self, obj: Quote) -> str:
        return _name(obj.salesperson)

    def get_total(self, obj: Quote) -> str:
        return str(quote_totals(obj).total)

    def get_units(self, obj: Quote) -> list[str]:
        return [
            " ".join(p for p in [x.unit.make, x.unit.model] if p) or "Unit"
            for x in obj.lines.all()
            if x.unit is not None
        ]

    def get_trade_in_count(self, obj: Quote) -> int:
        return len(obj.trade_ins.all())

    def get_sale_number(self, obj: Quote) -> str | None:
        done = [s for s in obj.sales.all() if s.status == Sale.Status.COMPLETED]
        return done[0].number if done else None


class StatusSerializer(serializers.Serializer[Any]):
    status = serializers.ChoiceField(
        choices=[c for c in Quote.Status.choices if c[0] != Quote.Status.SOLD]
    )


class RecordSaleSerializer(serializers.Serializer[Any]):
    sale_date = serializers.DateField()
    invoice_number = serializers.CharField(
        max_length=60, required=False, allow_blank=True, default=""
    )
    # Hour meter of each sold unit at delivery: {unit id: hours}.
    hours = serializers.DictField(
        child=serializers.DecimalField(max_digits=9, decimal_places=1, min_value=0),
        required=False,
        default=dict,
    )


class SaleSerializer(serializers.ModelSerializer[Sale]):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    quote_number = serializers.CharField(source="quote.number", read_only=True)
    salesperson_name = serializers.SerializerMethodField()
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    units = serializers.SerializerMethodField()

    class Meta:
        model = Sale
        fields = [
            "id",
            "number",
            "quote",
            "quote_number",
            "customer",
            "customer_name",
            "salesperson_name",
            "status",
            "status_label",
            "sale_date",
            "invoice_number",
            "subtotal",
            "trade_allowance",
            "trade_payoff",
            "taxable_amount",
            "tax_rate",
            "tax",
            "total",
            "voided_at",
            "void_reason",
            "units",
        ]
        read_only_fields = fields

    def get_salesperson_name(self, obj: Sale) -> str:
        return _name(obj.salesperson)

    def get_units(self, obj: Sale) -> list[dict[str, Any]]:
        return [
            {
                "kind": c.kind,
                "created_unit": c.created_unit,
                "unit": unit_summary(c.ownership.unit),
                "price": str(c.ownership.price) if c.ownership.price is not None else None,
            }
            for c in obj.unit_changes.select_related("ownership", "ownership__unit")
        ]
