from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.customers.models import Customer
from apps.units.models import Unit

from .models import LaborLine, MaintenancePlan, WorkOrder

User = get_user_model()


def _name(user: Any) -> str:
    return (getattr(user, "full_name", "") or getattr(user, "email", "")) if user else ""


def unit_summary(unit: Unit) -> dict[str, Any]:
    return {
        "id": str(unit.pk),
        "make": unit.make,
        "model": unit.model,
        "serial_number": unit.serial_number,
        "stock_number": unit.stock_number,
        "year": unit.year,
    }


class LaborSerializer(serializers.ModelSerializer[LaborLine]):
    mechanic_name = serializers.SerializerMethodField()

    class Meta:
        model = LaborLine
        fields = [
            "id",
            "work_order",
            "mechanic",
            "mechanic_name",
            "work_date",
            "hours",
            "description",
            "created_at",
        ]
        read_only_fields = ["id", "work_order", "mechanic_name", "created_at"]

    def get_mechanic_name(self, obj: LaborLine) -> str:
        return _name(obj.mechanic)


class WorkOrderListSerializer(serializers.ModelSerializer[WorkOrder]):
    unit_summary = serializers.SerializerMethodField()
    customer_name = serializers.SerializerMethodField()
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)
    assigned_to_name = serializers.SerializerMethodField()
    labor_hours = serializers.DecimalField(
        max_digits=8, decimal_places=2, read_only=True, default=Decimal("0")
    )

    class Meta:
        model = WorkOrder
        fields = [
            "id",
            "number",
            "unit",
            "unit_summary",
            "customer",
            "customer_name",
            "kind",
            "kind_label",
            "status",
            "status_label",
            "location",
            "assigned_to",
            "assigned_to_name",
            "complaint",
            "hold_reason",
            "opened_on",
            "due_on",
            "completed_at",
            "labor_hours",
        ]
        read_only_fields = fields

    def get_unit_summary(self, obj: WorkOrder) -> dict[str, Any]:
        return unit_summary(obj.unit)

    def get_customer_name(self, obj: WorkOrder) -> str:
        return obj.customer.name if obj.customer else ""

    def get_assigned_to_name(self, obj: WorkOrder) -> str:
        return _name(obj.assigned_to)


class WorkOrderSerializer(WorkOrderListSerializer):
    unit = serializers.PrimaryKeyRelatedField(queryset=Unit.objects.all())
    customer = serializers.PrimaryKeyRelatedField(
        queryset=Customer.objects.all(), required=False, allow_null=True
    )
    assigned_to = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(is_active=True), required=False, allow_null=True
    )
    labor = serializers.SerializerMethodField()
    hours = serializers.DecimalField(
        max_digits=9,
        decimal_places=1,
        required=False,
        allow_null=True,
        min_value=Decimal("0"),
        write_only=True,
    )
    hour_meter = serializers.SerializerMethodField()
    location_label = serializers.CharField(source="get_location_display", read_only=True)
    created_by_name = serializers.SerializerMethodField()
    maintenance_plan_name = serializers.SerializerMethodField()

    class Meta(WorkOrderListSerializer.Meta):
        fields = [
            *WorkOrderListSerializer.Meta.fields,
            "location_label",
            "cause",
            "correction",
            "customer_po",
            "contact",
            "notes",
            "hours",
            "hour_meter",
            "labor",
            "maintenance_plan",
            "maintenance_plan_name",
            "is_deleted",
            "created_at",
            "created_by_name",
            "updated_at",
        ]
        read_only_fields = [
            "maintenance_plan",
            "maintenance_plan_name",
            "id",
            "number",
            "unit_summary",
            "customer_name",
            "status",
            "status_label",
            "kind_label",
            "location_label",
            "assigned_to_name",
            "hold_reason",
            "completed_at",
            "labor_hours",
            "hour_meter",
            "labor",
            "is_deleted",
            "created_at",
            "created_by_name",
            "updated_at",
        ]

    def get_labor(self, obj: WorkOrder) -> list[dict[str, Any]]:
        return LaborSerializer(obj.labor.select_related("mechanic"), many=True).data  # type: ignore[return-value]

    def get_hour_meter(self, obj: WorkOrder) -> dict[str, Any] | None:
        r = obj.hour_reading
        if r is None or r.deleted_at is not None:
            return None
        return {"hours": str(r.hours), "reading_date": r.reading_date.isoformat()}

    def get_maintenance_plan_name(self, obj: WorkOrder) -> str:
        return obj.maintenance_plan.name if obj.maintenance_plan else ""

    def get_created_by_name(self, obj: WorkOrder) -> str:
        return _name(obj.created_by)  # type: ignore[attr-defined]

    def validate_unit(self, unit: Unit) -> Unit:
        if self.instance is not None and unit.pk != self.instance.unit_id:
            raise serializers.ValidationError(
                "A work order's unit can't be changed. Cancel it and open a new one."
            )
        return unit

    def validate_assigned_to(self, user: Any) -> Any:
        if user is not None and getattr(user, "role", "") not in ("admin", "service"):
            raise serializers.ValidationError("Assign it to someone in service (or an admin).")
        return user

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        opened = attrs.get("opened_on", getattr(self.instance, "opened_on", None))
        due = attrs.get("due_on", getattr(self.instance, "due_on", None))
        if opened and due and due < opened:
            raise serializers.ValidationError(
                {"due_on": "The due date can't be before the date it was opened."}
            )
        return attrs


class StatusSerializer(serializers.Serializer[Any]):
    status = serializers.ChoiceField(choices=WorkOrder.Status.choices)
    reason = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")


class LaborCreateSerializer(serializers.Serializer[Any]):
    mechanic = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    work_date = serializers.DateField()
    hours = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=Decimal("0.05"), max_value=Decimal("24")
    )
    description = serializers.CharField(
        max_length=300, required=False, allow_blank=True, default=""
    )


class MaintenancePlanSerializer(serializers.ModelSerializer[MaintenancePlan]):
    """`status` comes from the view (it needs the unit's current hours)."""

    unit = serializers.PrimaryKeyRelatedField(queryset=Unit.objects.all())
    unit_summary = serializers.SerializerMethodField()
    owner_name = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = MaintenancePlan
        fields = [
            "id",
            "unit",
            "unit_summary",
            "owner_name",
            "name",
            "tasks",
            "interval_hours",
            "interval_days",
            "last_done_on",
            "last_done_hours",
            "active",
            "status",
            "created_at",
        ]
        read_only_fields = ["id", "unit_summary", "owner_name", "status", "created_at"]

    def get_unit_summary(self, obj: MaintenancePlan) -> dict[str, Any]:
        return unit_summary(obj.unit)

    def get_owner_name(self, obj: MaintenancePlan) -> str:
        return str(self.context.get("owners", {}).get(obj.unit_id, ""))

    def get_status(self, obj: MaintenancePlan) -> dict[str, Any] | None:
        st = self.context.get("statuses", {}).get(obj.pk)
        return st.as_dict() if st is not None else None

    def validate_unit(self, unit: Unit) -> Unit:
        if self.instance is not None and unit.pk != self.instance.unit_id:
            raise serializers.ValidationError(
                "A plan belongs to its unit; add a new plan on the other unit."
            )
        return unit

    def validate_name(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError("Give the plan a name, e.g. “250-hour service”.")
        return value.strip()

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        def current(key: str) -> Any:
            return attrs[key] if key in attrs else getattr(self.instance, key, None)

        hours, days = current("interval_hours"), current("interval_days")
        if not hours and not days:
            raise serializers.ValidationError(
                {"interval_hours": "Set every how many hours, every how many days, or both."}
            )
        if hours and current("last_done_hours") is None:
            unit = current("unit")
            latest = unit.hour_readings.first() if unit is not None else None
            if latest is None:
                raise serializers.ValidationError(
                    {"last_done_hours": "Enter the hour meter reading when it was last done."}
                )
            attrs["last_done_hours"] = latest.hours
        return attrs
