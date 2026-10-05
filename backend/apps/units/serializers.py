from __future__ import annotations

from datetime import date
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import serializers

from apps.accounts.roles import PRICE_ROLES
from apps.customers.models import Customer

from .models import (
    HourMeterReading,
    OwnershipRecord,
    Unit,
    UnitAttachment,
    UnitComponent,
    UnitFile,
    UnitFork,
    normalize_serial,
)

STOCK_ROLES = PRICE_ROLES  # stock status follows the same rule as pricing


def can_see_pricing(context: dict[str, Any]) -> bool:
    request = context.get("request")
    return bool(request and getattr(request.user, "role", None) in PRICE_ROLES)


class PriceVisibilityMixin:
    """Cost, asking price and sale price exist only for admin and sales.
    For everyone else the fields are absent from responses and ignored on input."""

    def get_fields(self) -> dict[str, Any]:
        fields: dict[str, Any] = super().get_fields()  # type: ignore[misc]
        if not can_see_pricing(self.context):  # type: ignore[attr-defined]
            for name in Unit.PRICE_FIELDS:
                fields.pop(name, None)
            if "stock_status" in fields:
                fields["stock_status"].read_only = True
        return fields


# --- Child rows ------------------------------------------------------------------------------


class ComponentSerializer(serializers.ModelSerializer[UnitComponent]):
    id = serializers.UUIDField(required=False)
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)

    class Meta:
        model = UnitComponent
        fields = ["id", "kind", "kind_label", "make", "model", "serial_number", "spools"]

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if attrs.get("spools") and attrs.get("kind") != UnitComponent.Kind.CONTROL_VALVE:
            raise serializers.ValidationError(
                {"spools": ["Spools only apply to the control valve."]}
            )
        return attrs


class ForkSerializer(serializers.ModelSerializer[UnitFork]):
    id = serializers.UUIDField(required=False)

    class Meta:
        model = UnitFork
        fields = ["id", "dimensions", "quantity", "thickness_in", "width_in", "length_in"]
        read_only_fields = ["thickness_in", "width_in", "length_in"]


class AttachmentSerializer(serializers.ModelSerializer[UnitAttachment]):
    id = serializers.UUIDField(required=False)

    class Meta:
        model = UnitAttachment
        fields = [
            "id",
            "manufacturer",
            "type",
            "model",
            "serial_number",
            "date_code",
            "hose_reel",
            "internal_hose",
            "reel_number",
            "side",
        ]

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if not any((attrs.get(k) or "").strip() for k in ("manufacturer", "type", "model")):
            raise serializers.ValidationError(
                {"manufacturer": ["Enter at least a manufacturer, type or model."]}
            )
        return attrs


class HourReadingSerializer(serializers.ModelSerializer[HourMeterReading]):
    source_label = serializers.CharField(source="get_source_display", read_only=True)

    class Meta:
        model = HourMeterReading
        fields = ["id", "reading_date", "hours", "source", "source_label", "note", "created_at"]
        read_only_fields = ["id", "created_at"]


class DealPriceMixin:
    """An ownership record's price and cost exist only for admin and sales."""

    def get_fields(self) -> dict[str, Any]:
        fields: dict[str, Any] = super().get_fields()  # type: ignore[misc]
        if not can_see_pricing(self.context):  # type: ignore[attr-defined]
            for name in OwnershipRecord.PRICE_FIELDS:
                fields.pop(name, None)
        return fields


class OwnershipSerializer(DealPriceMixin, serializers.ModelSerializer[OwnershipRecord]):
    customer_name = serializers.CharField(source="customer.name", read_only=True, default=None)
    owner_label = serializers.SerializerMethodField()
    reason_label = serializers.CharField(source="get_reason_display", read_only=True)
    hours = serializers.DecimalField(
        source="hour_reading.hours",
        max_digits=9,
        decimal_places=1,
        read_only=True,
        default=None,
    )
    can_undo = serializers.SerializerMethodField()

    class Meta:
        model = OwnershipRecord
        fields = [
            "id",
            "owner_kind",
            "customer",
            "customer_name",
            "owner_label",
            "start_date",
            "end_date",
            "note",
            "reason",
            "reason_label",
            "price",
            "cost",
            "reference",
            "hours",
            "can_undo",
        ]
        read_only_fields = [
            "id",
            "owner_kind",
            "customer",
            "start_date",
            "end_date",
        ]

    def get_owner_label(self, obj: OwnershipRecord) -> str:
        return obj.customer.name if obj.customer else "Maine Material Handling stock"

    def get_can_undo(self, obj: OwnershipRecord) -> bool:
        """Changes recorded since Phase 7 can be undone while they're the latest."""
        return obj.end_date is None and obj.unit_changes is not None


class DealEditSerializer(serializers.ModelSerializer[OwnershipRecord]):
    """Correct a recorded change: why, the money, the reference, the note."""

    price = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=0, required=False, allow_null=True
    )
    cost = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=0, required=False, allow_null=True
    )

    class Meta:
        model = OwnershipRecord
        fields = ["reason", "price", "cost", "reference", "note"]


class TransferSerializer(serializers.Serializer[Any]):
    owner_kind = serializers.ChoiceField(choices=OwnershipRecord.OwnerKind.choices)
    customer = serializers.PrimaryKeyRelatedField(
        queryset=Customer.objects.all(), required=False, allow_null=True
    )
    start_date = serializers.DateField()
    reason = serializers.ChoiceField(
        choices=OwnershipRecord.Reason.choices,
        error_messages={
            "required": "Say why it changed hands.",
            "invalid_choice": "Pick a reason.",
        },
    )
    price = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=0, required=False, allow_null=True
    )
    reference = serializers.CharField(max_length=60, required=False, allow_blank=True, default="")
    note = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    hours = serializers.DecimalField(
        max_digits=9, decimal_places=1, min_value=0, required=False, allow_null=True
    )

    def validate_start_date(self, value: date) -> date:
        if value > timezone.localdate():
            raise serializers.ValidationError("Can't be in the future. Record it on the day.")
        return value


class UnitChangeSerializer(DealPriceMixin, serializers.ModelSerializer[OwnershipRecord]):
    """One change of hands, for the "Bought and sold" list."""

    unit_label = serializers.CharField(source="unit.__str__", read_only=True)
    unit_make = serializers.CharField(source="unit.make", read_only=True)
    unit_model = serializers.CharField(source="unit.model", read_only=True)
    unit_serial = serializers.CharField(source="unit.serial_number", read_only=True)
    unit_stock_number = serializers.CharField(source="unit.stock_number", read_only=True)
    reason_label = serializers.CharField(source="get_reason_display", read_only=True)
    owner_label = serializers.SerializerMethodField()
    from_kind = serializers.CharField(read_only=True)
    from_customer = serializers.UUIDField(source="from_customer_id", read_only=True)
    from_label = serializers.SerializerMethodField()
    hours = serializers.DecimalField(
        source="hour_reading.hours",
        max_digits=9,
        decimal_places=1,
        read_only=True,
        default=None,
    )

    class Meta:
        model = OwnershipRecord
        fields = [
            "id",
            "unit",
            "unit_label",
            "unit_make",
            "unit_model",
            "unit_serial",
            "unit_stock_number",
            "start_date",
            "end_date",
            "reason",
            "reason_label",
            "owner_kind",
            "customer",
            "owner_label",
            "from_kind",
            "from_customer",
            "from_label",
            "price",
            "cost",
            "reference",
            "note",
            "hours",
        ]
        read_only_fields = fields

    def get_owner_label(self, obj: OwnershipRecord) -> str:
        return obj.customer.name if obj.customer else "Maine Material Handling stock"

    def get_from_label(self, obj: Any) -> str:
        if obj.from_kind == OwnershipRecord.OwnerKind.DEALER:
            return "Maine Material Handling stock"
        return obj.from_name or ""


class UnitFileSerializer(serializers.ModelSerializer[UnitFile]):
    url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)

    class Meta:
        model = UnitFile
        fields = [
            "id",
            "unit",
            "kind",
            "kind_label",
            "original_name",
            "content_type",
            "size_bytes",
            "width",
            "height",
            "caption",
            "is_primary",
            "sort_order",
            "url",
            "thumbnail_url",
            "created_at",
        ]
        read_only_fields = [f for f in fields if f not in ("caption", "sort_order")]

    def get_url(self, obj: UnitFile) -> str:
        return f"/api/v1/unit-files/{obj.pk}/content"

    def get_thumbnail_url(self, obj: UnitFile) -> str | None:
        return f"/api/v1/unit-files/{obj.pk}/content?size=thumb" if obj.thumbnail else None


# --- Units ------------------------------------------------------------------------------------

LIST_FIELDS = [
    "id",
    "make",
    "model",
    "serial_number",
    "stock_number",
    "year",
    "condition",
    "fuel_type",
    "capacity_lbs",
    "mast_lift_height_in",
    "stock_status",
    "needs_review",
    "current_hours",
    "owner_kind",
    "owner_customer_id",
    "owner_name",
    "primary_photo_id",
    "asking_price",
    "is_deleted",
]


class UnitListSerializer(PriceVisibilityMixin, serializers.ModelSerializer[Unit]):
    current_hours = serializers.DecimalField(
        max_digits=9, decimal_places=1, read_only=True, allow_null=True
    )
    owner_kind = serializers.CharField(read_only=True, allow_null=True)
    owner_customer_id = serializers.UUIDField(read_only=True, allow_null=True)
    owner_name = serializers.CharField(read_only=True, allow_null=True)
    primary_photo_id = serializers.UUIDField(read_only=True, allow_null=True)

    class Meta:
        model = Unit
        fields = LIST_FIELDS


class UnitSerializer(PriceVisibilityMixin, serializers.ModelSerializer[Unit]):
    components = ComponentSerializer(many=True, required=False)
    forks = ForkSerializer(many=True, required=False)
    attachments = AttachmentSerializer(many=True, required=False)

    current_hours = serializers.DecimalField(
        max_digits=9, decimal_places=1, read_only=True, allow_null=True
    )
    current_hours_date = serializers.DateField(read_only=True, allow_null=True)
    owner_kind = serializers.CharField(read_only=True, allow_null=True)
    owner_customer_id = serializers.UUIDField(read_only=True, allow_null=True)
    owner_name = serializers.CharField(read_only=True, allow_null=True)
    primary_photo_id = serializers.UUIDField(read_only=True, allow_null=True)

    # Only on create: who owns it and the hour meter reading from the card.
    initial_owner_kind = serializers.ChoiceField(
        choices=OwnershipRecord.OwnerKind.choices, write_only=True, required=False
    )
    initial_owner_customer = serializers.PrimaryKeyRelatedField(
        queryset=Customer.objects.all(), write_only=True, required=False, allow_null=True
    )
    initial_hours = serializers.DecimalField(
        max_digits=9,
        decimal_places=1,
        min_value=0,
        write_only=True,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Unit
        exclude = ["created_by", "updated_by", "deleted_by", "deleted_at", "serial_normalized"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def to_representation(self, instance: Unit) -> dict[str, Any]:
        data = super().to_representation(instance)
        data["is_deleted"] = instance.is_deleted
        # Children: only live rows, in a stable order.
        data["components"] = ComponentSerializer(
            sorted(
                instance.components.filter(deleted_at__isnull=True),
                key=lambda c: UnitComponent.ORDER.index(c.kind),
            ),
            many=True,
        ).data
        data["forks"] = ForkSerializer(
            instance.forks.filter(deleted_at__isnull=True), many=True
        ).data
        data["attachments"] = AttachmentSerializer(
            instance.attachments.filter(deleted_at__isnull=True), many=True
        ).data
        return data

    # --- validation -----------------------------------------------------------------
    def validate_serial_number(self, value: str) -> str:
        value = value.strip()
        norm = normalize_serial(value)
        if norm:
            clash = Unit.all_objects.filter(serial_normalized=norm)
            if self.instance is not None:
                clash = clash.exclude(pk=self.instance.pk)
            other = clash.first()
            if other is not None:
                where = " (removed; restore it instead)" if other.is_deleted else ""
                raise serializers.ValidationError(
                    f"Serial {value} is already on {other}{where}.", code="duplicate_serial"
                )
        return value

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        instance = self.instance
        merged = {
            f: attrs.get(f, getattr(instance, f, ""))
            for f in ("serial_number", "model", "stock_number")
        }
        if not any((v or "").strip() for v in merged.values()):
            raise serializers.ValidationError(
                {"serial_number": ["Enter at least a serial number, model or stock number."]}
            )
        kinds = [c["kind"] for c in attrs.get("components", [])]
        if len(kinds) != len(set(kinds)):
            raise serializers.ValidationError(
                {"components": ["Each component type can appear only once."]}
            )
        if (
            instance is None
            and attrs.get("initial_owner_kind") == OwnershipRecord.OwnerKind.CUSTOMER
            and not attrs.get("initial_owner_customer")
        ):
            raise serializers.ValidationError(
                {"initial_owner_customer": ["Pick the customer who owns it."]}
            )
        return attrs

    # --- writes -----------------------------------------------------------------------
    @staticmethod
    def _sync(unit: Unit, model: Any, rows: list[dict[str, Any]] | None) -> None:
        """Make the unit's live child rows match `rows`: update by id, create
        new ones, soft-delete the ones left out. None = leave untouched."""
        if rows is None:
            return
        existing = {str(r.pk): r for r in model.objects.filter(unit=unit)}
        incoming_ids = {str(r.get("id") or "") for r in rows}
        # Remove first, so a replacement row never collides with the old one
        # (e.g. a new engine replacing the old engine).
        for row_id, obj in existing.items():
            if row_id not in incoming_ids:
                obj.soft_delete()
        for row in rows:
            row = dict(row)
            obj = existing.get(str(row.pop("id", "") or "")) or model(unit=unit)
            for key, value in row.items():
                setattr(obj, key, value)
            obj.save()

    def _save(self, instance: Unit | None, validated: dict[str, Any]) -> Unit:
        from .services import record_hours, transfer_ownership

        children = {
            UnitComponent: validated.pop("components", None),
            UnitFork: validated.pop("forks", None),
            UnitAttachment: validated.pop("attachments", None),
        }
        owner_kind = validated.pop("initial_owner_kind", None)
        owner_customer = validated.pop("initial_owner_customer", None)
        initial_hours = validated.pop("initial_hours", None)
        try:
            with transaction.atomic():
                unit = instance or Unit()
                for key, value in validated.items():
                    setattr(unit, key, value)
                unit.save()
                for model, rows in children.items():
                    self._sync(unit, model, rows)
                if instance is None:
                    kind = owner_kind or (
                        OwnershipRecord.OwnerKind.CUSTOMER
                        if owner_customer
                        else OwnershipRecord.OwnerKind.DEALER
                    )
                    start = unit.card_date or unit.created_at.date()
                    transfer_ownership(
                        unit, owner_kind=kind, customer=owner_customer, start_date=start
                    )
                    if initial_hours is not None:
                        record_hours(
                            unit,
                            hours=initial_hours,
                            reading_date=start,
                            source=HourMeterReading.Source.CARD,
                        )
        except IntegrityError as exc:
            if "unit_serial_unique" in str(exc):
                raise serializers.ValidationError(
                    {"serial_number": ["Another unit already has this serial number."]}
                ) from exc
            if "unit_stock_number_unique" in str(exc):
                raise serializers.ValidationError(
                    {"stock_number": ["Another unit already has this stock number."]}
                ) from exc
            raise
        return unit

    def create(self, validated_data: dict[str, Any]) -> Unit:
        return self._save(None, validated_data)

    def update(self, instance: Unit, validated_data: dict[str, Any]) -> Unit:
        for name in ("initial_owner_kind", "initial_owner_customer", "initial_hours"):
            validated_data.pop(name, None)
        return self._save(instance, validated_data)
