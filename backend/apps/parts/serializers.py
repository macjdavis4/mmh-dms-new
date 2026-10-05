from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.accounts.roles import Role

from .models import Bin, CrossReference, Part

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
    "is_deleted",
]


class PartListSerializer(CostVisibilityMixin, serializers.ModelSerializer[Part]):
    category_label = serializers.CharField(source="get_category_display", read_only=True)
    bin_code = serializers.CharField(source="bin.code", read_only=True, default=None)
    superseded_by_summary = serializers.SerializerMethodField()
    is_deleted = serializers.BooleanField(read_only=True)

    class Meta:
        model = Part
        fields = LIST_FIELDS

    def get_superseded_by_summary(self, obj: Part) -> dict[str, Any] | None:
        return part_summary(obj.superseded_by)


class PartSerializer(CostVisibilityMixin, serializers.ModelSerializer[Part]):
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
