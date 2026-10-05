"""When is planned maintenance due?

A plan is due every `interval_hours` and/or every `interval_days` after it
was last done, whichever comes first. "Due soon" means within 30 days or
50 hours. Completing a work order made for a plan marks the plan done.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import OuterRef, Subquery
from django.utils import timezone

from apps.units.models import HourMeterReading, Unit

from .models import MaintenancePlan, WorkOrder

DUE_SOON_DAYS = 30
DUE_SOON_HOURS = Decimal("50")
RANK = {"overdue": 0, "due_soon": 1, "ok": 2, "paused": 3}


@dataclass
class PlanStatus:
    state: str  # overdue | due_soon | ok | paused
    next_due_on: date | None
    next_due_hours: Decimal | None
    current_hours: Decimal | None
    days_left: int | None
    hours_left: Decimal | None
    open_work_order: WorkOrder | None

    def as_dict(self) -> dict[str, Any]:
        wo = self.open_work_order
        return {
            "state": self.state,
            "next_due_on": self.next_due_on.isoformat() if self.next_due_on else None,
            "next_due_hours": str(self.next_due_hours) if self.next_due_hours is not None else None,
            "current_hours": str(self.current_hours) if self.current_hours is not None else None,
            "days_left": self.days_left,
            "hours_left": str(self.hours_left) if self.hours_left is not None else None,
            "open_work_order": {"id": str(wo.pk), "number": wo.number, "status": wo.status}
            if wo
            else None,
        }


def current_hours(unit_ids: Iterable[Any]) -> dict[Any, Decimal]:
    """Latest hour meter reading per unit."""
    latest = HourMeterReading.objects.filter(unit=OuterRef("pk")).order_by(
        "-reading_date", "-created_at"
    )
    rows = Unit.all_objects.filter(pk__in=list(unit_ids)).annotate(
        h=Subquery(latest.values("hours")[:1])
    )
    return {u.pk: u.h for u in rows if u.h is not None}


def plan_status(
    plan: MaintenancePlan, hours: Decimal | None, today: date, open_wo: WorkOrder | None = None
) -> PlanStatus:
    next_on = plan.last_done_on + timedelta(days=plan.interval_days) if plan.interval_days else None
    next_hours = (
        plan.last_done_hours + plan.interval_hours
        if plan.interval_hours and plan.last_done_hours is not None
        else None
    )
    days_left = (next_on - today).days if next_on else None
    hours_left = next_hours - hours if next_hours is not None and hours is not None else None
    if not plan.active:
        state = "paused"
    elif (days_left is not None and days_left < 0) or (hours_left is not None and hours_left <= 0):
        state = "overdue"
    elif (days_left is not None and days_left <= DUE_SOON_DAYS) or (
        hours_left is not None and hours_left <= DUE_SOON_HOURS
    ):
        state = "due_soon"
    else:
        state = "ok"
    return PlanStatus(state, next_on, next_hours, hours, days_left, hours_left, open_wo)


def statuses(
    plans: Iterable[MaintenancePlan], today: date | None = None
) -> list[tuple[MaintenancePlan, PlanStatus]]:
    plans = list(plans)
    today = today or timezone.localdate()
    hours = current_hours({p.unit_id for p in plans})
    open_wos = {
        wo.maintenance_plan_id: wo
        for wo in WorkOrder.objects.filter(
            maintenance_plan__in=plans, status__in=WorkOrder.OPEN_STATUSES
        ).order_by("opened_on")
    }
    return [(p, plan_status(p, hours.get(p.unit_id), today, open_wos.get(p.pk))) for p in plans]


def sort_key(item: tuple[MaintenancePlan, PlanStatus]) -> tuple[int, int, str]:
    plan, st = item
    soonest = min(
        [d for d in [st.days_left] if d is not None]
        + [int(h / Decimal("8")) for h in [st.hours_left] if h is not None]  # ~8 h of use a day
        or [99999]
    )
    return RANK[st.state], soonest, plan.name


def due_list(include_ok: bool = False) -> list[tuple[MaintenancePlan, PlanStatus]]:
    """Active plans on current units, most urgent first."""
    plans = MaintenancePlan.objects.filter(
        active=True, unit__deleted_at__isnull=True
    ).select_related("unit")
    items = [i for i in statuses(plans) if include_ok or i[1].state in ("overdue", "due_soon")]
    return sorted(items, key=sort_key)


@transaction.atomic
def work_order_for(plan: MaintenancePlan) -> WorkOrder:
    """Open a planned-maintenance work order for this plan (one at a time)."""
    from . import services

    MaintenancePlan.objects.select_for_update().filter(pk=plan.pk).first()
    existing = plan.work_orders.filter(status__in=WorkOrder.OPEN_STATUSES).first()
    if existing is not None:
        raise ValidationError({"plan": f"{existing.number} is already open for this."})
    if not plan.active:
        raise ValidationError({"plan": "This plan is paused."})
    complaint = plan.name if not plan.tasks.strip() else f"{plan.name}:\n{plan.tasks.strip()}"
    work_order = WorkOrder(
        unit=plan.unit,
        kind=WorkOrder.Kind.MAINTENANCE,
        complaint=complaint,
        maintenance_plan=plan,
    )
    services.save_work_order(work_order)
    return work_order


def mark_done(work_order: WorkOrder) -> None:
    """Called when a plan's work order is completed."""
    plan = work_order.maintenance_plan
    if plan is None:
        return
    plan = MaintenancePlan.objects.select_for_update().get(pk=plan.pk)
    work_order.plan_prev_done_on = plan.last_done_on
    work_order.plan_prev_done_hours = plan.last_done_hours
    done_on = (
        timezone.localdate(work_order.completed_at)
        if work_order.completed_at
        else timezone.localdate()
    )
    reading = work_order.hour_reading
    hours = (
        reading.hours
        if reading is not None and reading.deleted_at is None
        else current_hours([plan.unit_id]).get(plan.unit_id)
    )
    plan.last_done_on = max(done_on, plan.last_done_on)
    if hours is not None:
        plan.last_done_hours = hours
    plan.save()


def unmark_done(work_order: WorkOrder) -> None:
    """Called when a plan's completed work order is reopened: put the plan back
    unless it has been done again since."""
    plan = work_order.maintenance_plan
    if plan is None or work_order.plan_prev_done_on is None:
        return
    plan = MaintenancePlan.objects.select_for_update().get(pk=plan.pk)
    done_on = timezone.localdate(work_order.completed_at) if work_order.completed_at else None
    if done_on is not None and plan.last_done_on == max(done_on, work_order.plan_prev_done_on):
        plan.last_done_on = work_order.plan_prev_done_on
        plan.last_done_hours = work_order.plan_prev_done_hours
        plan.save()
    work_order.plan_prev_done_on = None
    work_order.plan_prev_done_hours = None
