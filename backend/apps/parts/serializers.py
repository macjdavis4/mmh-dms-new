from __future__ import annotations

from decimal import Decimal
from typing import Any

from rest_framework import serializers

from apps.accounts.roles import Role
from apps.service.models import WorkOrder

from .models import Bin, CrossReference, Part, StockCheck, StockMovement

# Our cost of a part: admin, sales and parts. (List prices are for everyone.)
COST_ROLES = frozenset({Role.ADMIN, Role.SALES, Role.PARTS})


def can_see_cost(context: dict[str, Any]) -> bool:
    request = context.get("request")
    return bool(request and getattr(request.user, "role", None) in COST_ROLES)


class CostVisibilityMixin:
    def get_fields(self) -> dict[str, Any]:
        fields: dict[str, Any] = super().get_fields()  # type: ignore[misc]
        if not can_see_cost(self.context):  # type: ignore[attr-defined]
            for name in Part.COST_FIELDS:
                fields.pop(name, None)
        return fields


def part_summary(part: Part | None) -> dict[str, Any] | None:
    if part is None:
        return None
    return {
        "id": str(part.pk),
        "manufacturer": part.manufacturer,
        "part_number": part.part_number,
        "description": part.description,
        "is_deleted": part.is_deleted,
    }


class BinSerializer(serializers.ModelSerializer[Bin]):
    part_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Bin
        fields = ["id", "code", "description", "part_count"]

    def validate_code(self, value: str) -> str:
        value = value.strip().upper()
        if not value:
            raise serializers.ValidationError("Enter the bin code.")
        clash = Bin.objects.filter(code__iexact=value)
        if self.instance is not None:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError(f"Bin {value} already exists.")
        return value


class CrossReferenceSerializer(serializers.ModelSerializer[CrossReference]):
    id = serializers.UUIDField(required=False)

    class Meta:
        model = CrossReference
        fields = ["id", "manufacturer", "part_number", "note"]

    def validate_part_number(self, value: str) -> str:
        value = value.strip()
        if not any(c.isalnum() for c in value):
            raise serializers.ValidationError("Enter the part number.")
        return value


LIST_FIELDS = [
    "id",
    "manufacturer",
    "part_number",
    "description",
    "category",
    "category_label",
    "unit_of_measure",
    "cost",
    "list_price",
    "bin",
    "bin_code",
    "reorder_point",
    "reorder_quantity",
    "vendor",
    "superseded_by",
    "superseded_by_summary",
    "on_hand",
    "low",
    "is_deleted",
]


class StockFields(serializers.Serializer[Any]):
    """On hand comes from the stock table (annotated by the view as stock_on_hand)."""

    on_hand = serializers.DecimalField(
        source="stock_on_hand", max_digits=12, decimal_places=2, read_only=True, default=None
    )
    low = serializers.SerializerMethodField()

    def get_low(self, obj: Part) -> bool:
        on_hand = getattr(obj, "stock_on_hand", None)
        return (
            obj.reorder_point is not None and on_hand is not None and on_hand <= obj.reorder_point
        )


class PartListSerializer(CostVisibilityMixin, StockFields, serializers.ModelSerializer[Part]):
    category_label = serializers.CharField(source="get_category_display", read_only=True)
    bin_code = serializers.CharField(source="bin.code", read_only=True, default=None)
    superseded_by_summary = serializers.SerializerMethodField()
    is_deleted = serializers.BooleanField(read_only=True)

    class Meta:
        model = Part
        fields = LIST_FIELDS

    def get_superseded_by_summary(self, obj: Part) -> dict[str, Any] | None:
        return part_summary(obj.superseded_by)


class PartSerializer(CostVisibilityMixin, StockFields, serializers.ModelSerializer[Part]):
    category_label = serializers.CharField(source="get_category_display", read_only=True)
    unit_label = serializers.CharField(source="get_unit_of_measure_display", read_only=True)
    bin = serializers.PrimaryKeyRelatedField(
        queryset=Bin.objects.all(), required=False, allow_null=True
    )
    bin_code = serializers.CharField(source="bin.code", read_only=True, default=None)
    superseded_by = serializers.PrimaryKeyRelatedField(
        queryset=Part.objects.all(), required=False, allow_null=True
    )
    superseded_by_summary = serializers.SerializerMethodField()
    current_part = serializers.SerializerMethodField()
    supersedes = serializers.SerializerMethodField()
    cross_references = CrossReferenceSerializer(many=True, required=False)
    is_deleted = serializers.BooleanField(read_only=True)

    class Meta:
        model = Part
        fields = [
            "id",
            "manufacturer",
            "part_number",
            "description",
            "category",
            "category_label",
            "unit_of_measure",
            "unit_label",
            "cost",
            "list_price",
            "bin",
            "bin_code",
            "reorder_point",
            "reorder_quantity",
            "vendor",
            "vendor_part_number",
            "fits",
            "notes",
            "superseded_by",
            "superseded_by_summary",
            "superseded_on",
            "current_part",
            "supersedes",
            "cross_references",
            "on_hand",
            "low",
            "is_deleted",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "superseded_on", "created_at", "updated_at"]

    def to_representation(self, instance: Part) -> dict[str, Any]:
        data = super().to_representation(instance)
        data["cross_references"] = CrossReferenceSerializer(
            instance.cross_references.all(), many=True
        ).data
        return data

    def get_superseded_by_summary(self, obj: Part) -> dict[str, Any] | None:
        return part_summary(obj.superseded_by)

    def get_current_part(self, obj: Part) -> dict[str, Any] | None:
        """The end of the replacement chain, when it's more than one step away."""
        current = obj.current()
        if current.pk in (obj.pk, obj.superseded_by_id):
            return None
        return part_summary(current)

    def get_supersedes(self, obj: Part) -> list[dict[str, Any]]:
        return [s for s in (part_summary(p) for p in obj.supersedes.all()) if s]

    def validate_part_number(self, value: str) -> str:
        value = value.strip()
        if not any(c.isalnum() for c in value):
            raise serializers.ValidationError("Enter the part number.")
        return value

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        point = attrs.get("reorder_point", getattr(self.instance, "reorder_point", None))
        qty = attrs.get("reorder_quantity", getattr(self.instance, "reorder_quantity", None))
        if qty is not None and qty <= 0:
            raise serializers.ValidationError(
                {"reorder_quantity": ["Order at least one, or leave it blank."]}
            )
        if point is not None and qty is None:
            raise serializers.ValidationError(
                {"reorder_quantity": ["Say how many to order when it gets that low."]}
            )
        return attrs


# --- Stock ------------------------------------------------------------------------------


class StockMovementSerializer(serializers.ModelSerializer[StockMovement]):
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)
    part_summary = serializers.SerializerMethodField()
    work_order_number = serializers.CharField(
        source="work_order.number", read_only=True, default=None
    )
    by = serializers.SerializerMethodField()
    reversed = serializers.SerializerMethodField()
    can_reverse = serializers.SerializerMethodField()

    class Meta:
        model = StockMovement
        fields = [
            "id",
            "part",
            "part_summary",
            "kind",
            "kind_label",
            "quantity",
            "balance_after",
            "occurred_at",
            "work_order",
            "work_order_number",
            "unit_cost",
            "unit_price",
            "reference",
            "note",
            "reverses",
            "reversed",
            "can_reverse",
            "by",
        ]
        read_only_fields = fields

    def get_fields(self) -> dict[str, Any]:
        fields = super().get_fields()
        if not can_see_cost(self.context):
            for name in StockMovement.COST_FIELDS:
                fields.pop(name, None)
        return fields

    def get_part_summary(self, obj: StockMovement) -> dict[str, Any] | None:
        return part_summary(obj.part)

    def get_by(self, obj: StockMovement) -> str:
        user = obj.created_by
        return (user.full_name or user.email) if user else ""

    def get_reversed(self, obj: StockMovement) -> bool:
        return hasattr(obj, "reversed_by")

    def get_can_reverse(self, obj: StockMovement) -> bool:
        return (
            obj.kind != StockMovement.Kind.REVERSAL
            and not hasattr(obj, "reversed_by")
            and (obj.work_order is None or obj.work_order.is_open)
        )


QUANTITY = {"max_digits": 10, "decimal_places": 2, "min_value": Decimal("0.01")}


class ReceiveSerializer(serializers.Serializer[Any]):
    part = serializers.PrimaryKeyRelatedField(queryset=Part.objects.all())
    quantity = serializers.DecimalField(**QUANTITY)  # type: ignore[arg-type]
    unit_cost = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0"), required=False, allow_null=True
    )
    reference = serializers.CharField(max_length=60, required=False, allow_blank=True, default="")
    note = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")


class CountSerializer(serializers.Serializer[Any]):
    part = serializers.PrimaryKeyRelatedField(queryset=Part.objects.all())
    counted = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0"))
    note = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")


class WorkOrderPartSerializer(serializers.Serializer[Any]):
    part = serializers.PrimaryKeyRelatedField(queryset=Part.objects.all())
    work_order = serializers.PrimaryKeyRelatedField(queryset=WorkOrder.objects.all())
    quantity = serializers.DecimalField(**QUANTITY)  # type: ignore[arg-type]
    note = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")


class ReverseSerializer(serializers.Serializer[Any]):
    note = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")


class StockCheckSerializer(serializers.ModelSerializer[StockCheck]):
    ok = serializers.BooleanField(read_only=True)

    class Meta:
        model = StockCheck
        fields = ["id", "started_at", "finished_at", "parts_checked", "drift", "ok"]
        read_only_fields = fields


def used_parts_data(work_order: Any) -> list[dict[str, Any]]:
    """Parts on a work order for its page and PDF (list prices only, no cost)."""
    from . import stock

    return [
        {
            "part": part_summary(row.part),
            "quantity": str(row.quantity),
            "unit_price": None if row.unit_price is None else str(row.unit_price),
            "amount": None if row.amount is None else str(row.amount),
        }
        for row in stock.parts_used(work_order)
    ]
