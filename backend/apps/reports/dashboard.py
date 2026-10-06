"""Dashboard tiles: a few numbers for each person, depending on their role
and which features are switched on. Everything is counted live."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any

from django.db.models import DecimalField, F, Sum
from django.utils import timezone

from apps.accounts.roles import PRICE_ROLES, Role
from apps.core.api import flag_enabled
from apps.parts.serializers import COST_ROLES

MONEY: DecimalField[Decimal, Decimal] = DecimalField(max_digits=14, decimal_places=2)


@dataclass
class Tile:
    key: str
    label: str
    value: str
    kind: str  # count | money
    to: str
    # "warning" when the number needs someone's attention.
    tone: str = ""
    hint: str = ""


def _count(
    key: str, label: str, n: int, to: str, *, attention: bool = False, hint: str = ""
) -> Tile:
    return Tile(key, label, str(n), "count", to, "warning" if attention and n else "", hint)


def tiles_for(user: Any) -> list[Tile]:
    role = getattr(user, "role", "")

    def on(key: str) -> bool:
        return flag_enabled(key, user)

    reports = on("reports")
    tiles: list[Tile] = []

    if on("customers-units"):
        from apps.units.models import Unit

        n = Unit.objects.filter(stock_status__in=("available", "on_hold", "in_prep")).count()
        to = "/reports/units-in-stock" if reports and role in PRICE_ROLES else "/units"
        tiles.append(_count("units-in-stock", "Units in stock", n, to))

    if on("service"):
        from apps.service import maintenance
        from apps.service.models import WorkOrder

        open_wos = WorkOrder.objects.filter(status__in=WorkOrder.OPEN_STATUSES)
        tiles.append(_count("open-work-orders", "Open work orders", open_wos.count(), "/service"))
        if role in (Role.SERVICE, Role.ADMIN):
            mine = open_wos.filter(assigned_to=user).count()
            tiles.append(_count("my-work-orders", "Assigned to me", mine, "/service?mine=1"))
        due = sum(1 for _, st in maintenance.due_list() if st.state in ("overdue", "due_soon"))
        tiles.append(
            _count(
                "maintenance-due", "Maintenance due", due, "/service/maintenance", attention=True
            )
        )

    if on("sales") and role in (Role.ADMIN, Role.SALES):
        from apps.sales.models import Quote

        n = Quote.objects.filter(status__in=Quote.OPEN_STATUSES).count()
        tiles.append(_count("open-quotes", "Open quotes", n, "/sales"))

    if on("customers-units") and on("units-changing-hands") and role in PRICE_ROLES:
        from apps.units.views import DIRECTIONS, changes_queryset

        today = timezone.localdate()
        sold = (
            changes_queryset()
            .filter(DIRECTIONS["out"], start_date__gte=today.replace(day=1), start_date__lte=today)
            .order_by()
            .aggregate(total=Sum("price", output_field=MONEY))["total"]
        )
        tiles.append(
            Tile(
                "sales-this-month",
                "Units sold this month",
                f"{(sold or Decimal('0')):.2f}",
                "money",
                "/reports/units-sold" if reports else "/units/changes",
            )
        )

    if on("parts") and on("parts-stock"):
        from apps.parts.models import Part, PartStock

        low = (
            Part.objects.filter(reorder_point__isnull=False)
            .exclude(stock__on_hand__gt=F("reorder_point"))
            .count()
        )
        tiles.append(
            _count("low-stock", "Low-stock parts", low, "/parts/low-stock", attention=True)
        )
        if role in COST_ROLES:
            value = PartStock.objects.filter(
                on_hand__gt=0, part__deleted_at__isnull=True, part__cost__isnull=False
            ).aggregate(v=Sum(F("on_hand") * F("part__cost"), output_field=MONEY))["v"]
            tiles.append(
                Tile(
                    "parts-value",
                    "Parts on the shelf (at cost)",
                    f"{(value or Decimal('0')):.2f}",
                    "money",
                    "/reports/parts-valuation" if reports else "/parts",
                )
            )

    if on("parts") and on("parts-invoices") and role in COST_ROLES:
        from apps.parts import invoices
        from apps.parts.models import Invoice

        to_check = Invoice.objects.filter(status__in=("reading", "review")).count()
        tiles.append(
            _count(
                "invoices-to-check",
                "Invoices to check",
                to_check,
                "/parts/invoices",
                attention=True,
            )
        )
        tiles.append(
            _count(
                "backorders",
                "Parts on backorder",
                invoices.backorders().count(),
                "/parts/invoices?tab=backorders",
            )
        )
    return tiles


def as_json(tiles: list[Tile]) -> list[dict[str, str]]:
    return [asdict(t) for t in tiles]
