"""Demo work orders for development, tests and screenshots. Idempotent:
a work order is matched on its unit and complaint."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.utils import timezone

from apps.accounts.models import User
from apps.units.models import Unit

from . import services
from .models import MaintenancePlan, WorkOrder

WORK_ORDERS: list[dict[str, Any]] = [
    {
        "serial": "HHKHFV30K00057",
        "kind": "repair",
        "location": "field",
        "complaint": "Mast chatters when lifting over 10 ft. Customer reports it started last week.",
        "cause": "Worn mast rollers on the inner rail.",
        "status": "in_progress",
        "hours": "9120",
        "days_ago": 2,
        "due_in": 3,
        "contact": "Mike at the Millinocket yard, 207-555-0144",
        "labor": [("2.5", 1, "Diagnosed, measured roller wear"), ("1.0", 0, "Travel")],
    },
    {
        "serial": "FGA25-70988",
        "kind": "repair",
        "complaint": "Hydraulic leak at the tilt cylinder.",
        "cause": "Rod seal failed.",
        "status": "on_hold",
        "hold_reason": "Waiting for seal kit (ordered from Doosan)",
        "days_ago": 5,
        "labor": [("1.5", 4, "Found leak, pulled cylinder")],
    },
    {
        "serial": "HHKHHN04L0094",
        "kind": "maintenance",
        "complaint": "250-hour service.",
        "cause": "Scheduled maintenance.",
        "correction": "Changed engine oil and filter, checked fluids, greased chassis and mast. No issues found.",
        "status": "completed",
        "hours": "6610",
        "days_ago": 12,
        "labor": [("2.0", 12, "250 h service")],
    },
    {
        "serial": "HHKHHL03P00052",
        "kind": "prep",
        "complaint": "Prep for delivery: detail, check all functions, new decals.",
        "status": "open",
        "days_ago": 1,
        "due_in": 6,
        "labor": [],
    },
]


def load_demo_work_orders() -> None:
    mechanic = User.objects.filter(email="service@mmh.test").first()
    today = timezone.localdate()
    for spec in WORK_ORDERS:
        unit = Unit.objects.filter(serial_number=spec["serial"]).first()
        if (
            unit is None
            or WorkOrder.all_objects.filter(unit=unit, complaint=spec["complaint"]).exists()
        ):
            continue
        opened = today - timedelta(days=spec["days_ago"])
        work_order = WorkOrder(
            unit=unit,
            kind=spec["kind"],
            location=spec.get("location", "shop"),
            complaint=spec["complaint"],
            cause=spec.get("cause", ""),
            correction=spec.get("correction", ""),
            opened_on=opened,
            due_on=today + timedelta(days=spec["due_in"]) if "due_in" in spec else None,
            contact=spec.get("contact", ""),
            assigned_to=mechanic,
        )
        hours = Decimal(spec["hours"]) if "hours" in spec else None
        services.save_work_order(work_order, hours=hours, hours_given=hours is not None)
        if mechanic is not None:
            for amount, ago, text in spec["labor"]:
                services.add_labor(
                    work_order,
                    mechanic=mechanic,
                    work_date=today - timedelta(days=ago),
                    hours=Decimal(amount),
                    description=text,
                )
        if spec["status"] == "on_hold":
            services.change_status(work_order, "on_hold", reason=spec["hold_reason"])
        elif spec["status"] != "open":
            services.change_status(work_order, spec["status"])


PLANS: list[dict[str, Any]] = [
    {
        "serial": "HHKHFV30K00057",
        "name": "250-hour service",
        "tasks": "Engine oil and filter, check fluids, grease chassis and mast, inspect forks and chains.",
        "hours": 250,
        "days": 90,
        "done_days_ago": 60,
        "done_hours": "8800",
    },
    {
        "serial": "HHKHHN04L0094",
        "name": "Annual safety inspection",
        "tasks": "OSHA annual inspection checklist; brakes, horn, lights, seat belt, data plate.",
        "days": 365,
        "done_days_ago": 345,
    },
    {
        "serial": "FGA25-70988",
        "name": "500-hour service",
        "tasks": "Hydraulic filter, transmission fluid, air filter, LPG system check.",
        "hours": 500,
        "days": 180,
        "done_days_ago": 20,
        "done_hours": "10100",
    },
    {
        "serial": "HHKHBT08J00221",
        "name": "Battery and charger check",
        "tasks": "Water level, specific gravity, cables and connectors, charger output.",
        "days": 30,
        "done_days_ago": 41,
    },
]


def load_demo_plans() -> None:
    today = timezone.localdate()
    for spec in PLANS:
        unit = Unit.objects.filter(serial_number=spec["serial"]).first()
        if (
            unit is None
            or MaintenancePlan.all_objects.filter(unit=unit, name=spec["name"]).exists()
        ):
            continue
        MaintenancePlan.objects.create(
            unit=unit,
            name=spec["name"],
            tasks=spec["tasks"],
            interval_hours=spec.get("hours"),
            interval_days=spec.get("days"),
            last_done_on=today - timedelta(days=spec["done_days_ago"]),
            last_done_hours=Decimal(spec["done_hours"]) if "done_hours" in spec else None,
        )
