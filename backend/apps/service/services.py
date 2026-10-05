"""Work order rules. Each multi-step change runs in one transaction."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.roles import Role
from apps.units import services as unit_services
from apps.units.models import HourMeterReading, OwnershipRecord, Unit

from . import maintenance
from .models import LaborLine, WorkOrder

S = WorkOrder.Status

# Which status can follow which.
TRANSITIONS: dict[str, set[str]] = {
    S.OPEN: {S.IN_PROGRESS, S.ON_HOLD, S.COMPLETED, S.CANCELLED},
    S.IN_PROGRESS: {S.ON_HOLD, S.COMPLETED, S.CANCELLED},
    S.ON_HOLD: {S.IN_PROGRESS, S.COMPLETED, S.CANCELLED},
    S.COMPLETED: {S.IN_PROGRESS},  # reopen
    S.CANCELLED: {S.OPEN},  # reopen
}
MECHANIC_ROLES = (Role.ADMIN, Role.SERVICE)


def default_customer(unit: Unit) -> Any:
    owner = unit_services.open_ownership(unit)
    if owner is not None and owner.owner_kind == OwnershipRecord.OwnerKind.CUSTOMER:
        return owner.customer
    return None


def _hours(work_order: WorkOrder, hours: Decimal, reading_date: date) -> str | None:
    """Record (or correct) the hour meter reading taken for this work order."""
    current = work_order.hour_reading
    if current is not None:
        if current.hours == hours and current.reading_date == reading_date:
            return None
        current.soft_delete()
    result = unit_services.record_hours(
        work_order.unit,
        hours=hours,
        reading_date=reading_date,
        source=HourMeterReading.Source.SERVICE,
        note=f"Work order {work_order.number}",
    )
    work_order.hour_reading = result.reading
    work_order.save()
    return result.warning


@transaction.atomic
def save_work_order(
    work_order: WorkOrder, *, hours: Decimal | None = None, hours_given: bool = False
) -> str | None:
    """Create or update. Returns a warning to show (e.g. hours went backwards)."""
    if work_order._state.adding and work_order.customer is None:
        work_order.customer = default_customer(work_order.unit)
    if work_order.status != S.COMPLETED and work_order.status != S.CANCELLED:
        work_order.completed_at = None
    work_order.save()
    if hours_given:
        if hours is None:
            if work_order.hour_reading is not None:
                work_order.hour_reading.soft_delete()
                work_order.hour_reading = None
                work_order.save()
            return None
        return _hours(work_order, hours, work_order.opened_on)
    return None


@transaction.atomic
def change_status(work_order: WorkOrder, new_status: str, *, reason: str = "") -> WorkOrder:
    locked = WorkOrder.objects.select_for_update().get(pk=work_order.pk)
    if new_status == locked.status:
        return locked
    if new_status not in TRANSITIONS.get(locked.status, set()):
        raise ValidationError(
            {
                "status": f"A {locked.get_status_display().lower()} work order "
                f"can't be marked {S(new_status).label.lower()}."
            }
        )
    if new_status == S.COMPLETED:
        missing = []
        if not locked.correction.strip():
            missing.append("what was done (correction)")
        if missing:
            raise ValidationError(
                {"correction": f"Before completing, fill in {' and '.join(missing)}."}
            )
        locked.completed_at = timezone.now()
        maintenance.mark_done(locked)
    else:
        if locked.status == S.COMPLETED:
            maintenance.unmark_done(locked)  # reopening: the plan isn't done after all
        locked.completed_at = None
    if new_status == S.ON_HOLD:
        if not reason.strip():
            raise ValidationError({"reason": "Say why it's on hold, e.g. waiting for parts."})
        locked.hold_reason = reason.strip()[:200]
    elif locked.status == S.ON_HOLD:
        locked.hold_reason = ""
    locked.status = new_status
    locked.save()
    return locked


def check_mechanic(user: Any) -> None:
    if user is None or not user.is_active or getattr(user, "role", "") not in MECHANIC_ROLES:
        raise ValidationError({"mechanic": "Pick an active service or admin user."})


@transaction.atomic
def add_labor(
    work_order: WorkOrder, *, mechanic: Any, work_date: date, hours: Decimal, description: str = ""
) -> LaborLine:
    if work_order.status == S.CANCELLED:
        raise ValidationError({"work_order": "This work order is cancelled."})
    check_mechanic(mechanic)
    if work_date > timezone.localdate():
        raise ValidationError({"work_date": "Labor can't be logged for a future date."})
    line = LaborLine(
        work_order=work_order,
        mechanic=mechanic,
        work_date=work_date,
        hours=hours,
        description=description,
    )
    line.full_clean(exclude=["work_order", "mechanic"])
    line.save()
    return line
