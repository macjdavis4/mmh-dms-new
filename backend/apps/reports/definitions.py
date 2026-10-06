"""The reports. Each one reads straight from the records (nothing is
stored), so it always matches what the rest of the app shows."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from django.db.models import Count, DecimalField, F, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.accounts.roles import PRICE_ROLES, Role
from apps.parts.models import Part, StockMovement
from apps.parts.serializers import COST_ROLES
from apps.service.models import LaborLine, WorkOrder
from apps.units.models import OwnershipRecord, StockStatus, Unit
from apps.units.views import DIRECTIONS, changes_queryset

from .periods import Period
from .registry import Column, Report, Result, Row, register

ZERO = Decimal("0")
EVERYONE = frozenset(Role.values)
PRICES = frozenset(PRICE_ROLES)
COSTS = frozenset(COST_ROLES)
MONEY: DecimalField[Decimal, Decimal] = DecimalField(max_digits=14, decimal_places=2)


def unit_label(unit: Unit) -> str:
    return " ".join(x for x in (unit.make, unit.model) if x) or "Unit"


def _sum(rows: list[Row], key: str) -> Decimal | None:
    values = [r[key] for r in rows if r.get(key) is not None]
    return sum(values, ZERO) if values else None


# --- Units ------------------------------------------------------------------------------


def units_sold(period: Period, role: str) -> Result:
    qs = (
        changes_queryset()
        .filter(DIRECTIONS["out"], start_date__range=(period.start, period.end))
        .order_by("start_date", "created_at")
    )
    rows: list[Row] = []
    for r in qs:
        margin = r.price - r.cost if r.price is not None and r.cost is not None else None
        rows.append(
            {
                "date": r.start_date,
                "unit": unit_label(r.unit),
                "serial": r.unit.serial_number,
                "customer": r.customer.name if r.customer else "",
                "reason": r.get_reason_display() if r.reason else "",
                "reference": r.reference,
                "price": r.price,
                "cost": r.cost,
                "margin": margin,
                "_to": f"/units/{r.unit_id}",
            }
        )
    notes = []
    missing = sum(1 for r in rows if r["margin"] is None)
    if missing:
        notes.append(f"{missing} sale(s) have no price or cost recorded, so no margin.")
    return Result(
        rows,
        {
            "unit": f"{len(rows)} sold",
            "price": _sum(rows, "price"),
            "cost": _sum(rows, "cost"),
            "margin": _sum(rows, "margin"),
        },
        notes,
    )


register(
    Report(
        key="units-sold",
        title="Units sold",
        description=(
            "Every unit that left our stock in the period, with the price, our cost and the margin."
        ),
        group="Units and sales",
        roles=PRICES,
        flags=("customers-units", "units-changing-hands"),
        columns=(
            Column("date", "Date", "date", primary=True),
            Column("unit", "Unit", primary=True),
            Column("serial", "Serial"),
            Column("customer", "Customer", primary=True),
            Column("reason", "Why"),
            Column("reference", "Invoice #"),
            Column("price", "Price", "money", primary=True),
            Column("cost", "Our cost", "money"),
            Column("margin", "Margin", "money", primary=True),
        ),
        run=units_sold,
    )
)


IN_STOCK = (StockStatus.AVAILABLE, StockStatus.ON_HOLD, StockStatus.IN_PREP)


def units_in_stock(period: Period, role: str) -> Result:
    today = timezone.localdate()
    units = list(
        Unit.objects.filter(stock_status__in=IN_STOCK).order_by("stock_status", "make", "model")
    )
    since = {
        r.unit_id: r.start_date
        for r in OwnershipRecord.objects.filter(
            unit__in=units, end_date__isnull=True, owner_kind=OwnershipRecord.OwnerKind.DEALER
        )
    }
    rows: list[Row] = []
    for u in units:
        start = since.get(u.pk)
        rows.append(
            {
                "stock_number": u.stock_number,
                "unit": unit_label(u),
                "serial": u.serial_number,
                "condition": u.get_condition_display() if u.condition else "",
                "status": u.get_stock_status_display(),
                "since": start,
                "days": (today - start).days if start else None,
                "cost": u.cost,
                "asking": u.asking_price,
                "_to": f"/units/{u.pk}",
            }
        )
    rows.sort(key=lambda r: -(r["days"] or 0))
    days = [r["days"] for r in rows if r["days"] is not None]
    return Result(
        rows,
        {
            "unit": f"{len(rows)} units",
            "days": round(sum(days) / len(days)) if days else None,
            "cost": _sum(rows, "cost"),
            "asking": _sum(rows, "asking"),
        },
        ["Days is the average across units."] if days else [],
    )


register(
    Report(
        key="units-in-stock",
        title="Units in stock",
        description=(
            "Units we own today (available, on hold or in prep), "
            "oldest first, with cost and asking price."
        ),
        group="Units and sales",
        roles=PRICES,
        flags=("customers-units",),
        columns=(
            Column("stock_number", "Stock #"),
            Column("unit", "Unit", primary=True),
            Column("serial", "Serial"),
            Column("condition", "Condition"),
            Column("status", "Status", primary=True),
            Column("since", "In stock since", "date"),
            Column("days", "Days", "days", primary=True),
            Column("cost", "Our cost", "money", primary=True),
            Column("asking", "Asking", "money"),
        ),
        run=units_in_stock,
        uses_period=False,
    )
)


# --- Parts --------------------------------------------------------------------------------


def parts_valuation(period: Period, role: str) -> Result:
    parts = (
        Part.objects.filter(stock__on_hand__gt=0)
        .select_related("bin", "stock")
        .order_by("category", "number_normalized")
    )
    rows: list[Row] = []
    by_category: dict[str, Decimal] = defaultdict(lambda: ZERO)
    no_cost = 0
    for p in parts:
        on_hand = p.stock.on_hand
        value = (on_hand * p.cost).quantize(Decimal("0.01")) if p.cost is not None else None
        if value is None:
            no_cost += 1
        else:
            by_category[p.get_category_display()] += value
        rows.append(
            {
                "part_number": p.part_number,
                "description": p.description,
                "category": p.get_category_display(),
                "bin": p.bin.code if p.bin else "",
                "on_hand": on_hand,
                "cost": p.cost,
                "value": value,
                "_to": f"/parts/{p.pk}",
            }
        )
    notes = (
        [
            "By category: "
            + "; ".join(f"{name} ${amount:,.2f}" for name, amount in sorted(by_category.items()))
        ]
        if by_category
        else []
    )
    if no_cost:
        notes.append(
            f"{no_cost} part(s) in stock have no cost, so they aren't counted in the value."
        )
    return Result(
        rows,
        {
            "part_number": f"{len(rows)} parts",
            "on_hand": _sum(rows, "on_hand"),
            "value": _sum(rows, "value"),
        },
        notes,
    )


register(
    Report(
        key="parts-valuation",
        title="Parts valuation",
        description="What the parts on our shelves are worth today, at our cost.",
        group="Parts",
        roles=COSTS,
        flags=("parts", "parts-stock"),
        columns=(
            Column("part_number", "Part #", primary=True),
            Column("description", "Description", primary=True),
            Column("category", "Category"),
            Column("bin", "Bin"),
            Column("on_hand", "On hand", "qty", primary=True),
            Column("cost", "Cost each", "money"),
            Column("value", "Value", "money", primary=True),
        ),
        run=parts_valuation,
        uses_period=False,
    )
)


def parts_used(period: Period, role: str) -> Result:
    """Parts on work orders, net of returns and reversals, by part."""
    moves = (
        StockMovement.objects.filter(
            work_order__isnull=False, occurred_at__date__range=(period.start, period.end)
        )
        .values("part_id", "part__part_number", "part__description")
        .annotate(
            qty=Sum("quantity"),
            price=Sum(F("quantity") * F("unit_price"), output_field=MONEY),
            cost=Sum(F("quantity") * F("unit_cost"), output_field=MONEY),
            jobs=Count("work_order", distinct=True),
        )
    )
    rows: list[Row] = []
    for m in moves:
        qty = -(m["qty"] or ZERO)
        if qty == 0:
            continue
        rows.append(
            {
                "part_number": m["part__part_number"],
                "description": m["part__description"],
                "quantity": qty,
                "jobs": m["jobs"],
                "price": -m["price"] if m["price"] is not None else None,
                "cost": -m["cost"] if m["cost"] is not None else None,
                "_to": f"/parts/{m['part_id']}",
            }
        )
    rows.sort(key=lambda r: (-r["quantity"], r["part_number"]))
    return Result(
        rows,
        {
            "part_number": f"{len(rows)} parts",
            "quantity": _sum(rows, "quantity"),
            "price": _sum(rows, "price"),
            "cost": _sum(rows, "cost"),
        },
    )


register(
    Report(
        key="parts-used",
        title="Parts used on work orders",
        description=(
            "Parts taken off the shelf for jobs in the period (less any returned), most used first."
        ),
        group="Parts",
        roles=EVERYONE,
        flags=("parts", "parts-stock"),
        columns=(
            Column("part_number", "Part #", primary=True),
            Column("description", "Description", primary=True),
            Column("quantity", "Used", "qty", primary=True),
            Column("jobs", "Work orders", "int"),
            Column("price", "At list price", "money", primary=True),
            Column("cost", "Our cost", "money", roles=COSTS),
        ),
        run=parts_used,
    )
)


def parts_received(period: Period, role: str) -> Result:
    """Receipts by invoice or reference (reversed receipts count against them)."""
    moves = StockMovement.objects.filter(
        Q(kind="receive") | Q(kind="reversal", reverses__kind="receive"),
        occurred_at__date__range=(period.start, period.end),
    ).select_related("invoice_line__invoice")
    groups: dict[str, Row] = {}
    for m in moves.order_by("occurred_at"):
        invoice = m.invoice_line.invoice if m.invoice_line else None
        key = str(invoice.pk) if invoice else (m.reference or "by-hand")
        row = groups.setdefault(
            key,
            {
                "date": timezone.localtime(m.occurred_at).date(),
                "supplier": invoice.supplier if invoice else "",
                "reference": (invoice.invoice_number if invoice else m.reference) or "Typed in",
                "parts": set(),
                "quantity": ZERO,
                "value": None,
                "_to": f"/parts/invoices/{invoice.pk}" if invoice else "",
            },
        )
        row["parts"].add(m.part_id)
        row["quantity"] += m.quantity
        if m.unit_cost is not None:
            row["value"] = (row["value"] or ZERO) + m.quantity * m.unit_cost
    rows = []
    for row in groups.values():
        if row["quantity"] == 0:
            continue
        row["parts"] = len(row["parts"])
        rows.append(row)
    return Result(
        rows,
        {
            "reference": f"{len(rows)} receipts",
            "quantity": _sum(rows, "quantity"),
            "value": _sum(rows, "value"),
        },
    )


register(
    Report(
        key="parts-received",
        title="Parts received",
        description="Deliveries put into stock in the period, by invoice, at our cost.",
        group="Parts",
        roles=COSTS,
        flags=("parts", "parts-stock"),
        columns=(
            Column("date", "Date", "date", primary=True),
            Column("supplier", "Supplier", primary=True),
            Column("reference", "Invoice #", primary=True),
            Column("parts", "Parts", "int"),
            Column("quantity", "Pieces", "qty"),
            Column("value", "Value", "money", primary=True),
        ),
        run=parts_received,
    )
)


# --- Service ------------------------------------------------------------------------------


def labor_by_mechanic(period: Period, role: str) -> Result:
    lines = (
        LaborLine.objects.filter(
            work_date__range=(period.start, period.end), work_order__deleted_at__isnull=True
        )
        .values("mechanic_id", "mechanic__first_name", "mechanic__last_name", "mechanic__email")
        .annotate(
            hours=Sum("hours"),
            jobs=Count("work_order", distinct=True),
            days=Count("work_date", distinct=True),
        )
        .order_by("-hours")
    )
    rows: list[Row] = []
    for line in lines:
        name = f"{line['mechanic__first_name']} {line['mechanic__last_name']}".strip()
        rows.append(
            {
                "mechanic": name or line["mechanic__email"],
                "hours": line["hours"],
                "jobs": line["jobs"],
                "days": line["days"],
            }
        )
    return Result(
        rows,
        {"mechanic": f"{len(rows)} people", "hours": _sum(rows, "hours")},
    )


register(
    Report(
        key="labor-by-mechanic",
        title="Labor by mechanic",
        description="Hours logged on work orders in the period, per person.",
        group="Service",
        roles=frozenset({Role.ADMIN, Role.SERVICE}),
        flags=("service",),
        columns=(
            Column("mechanic", "Mechanic", primary=True),
            Column("hours", "Hours", "qty", primary=True),
            Column("jobs", "Work orders", "int", primary=True),
            Column("days", "Days worked", "int"),
        ),
        run=labor_by_mechanic,
    )
)


def work_orders_completed(period: Period, role: str) -> Result:
    wos = (
        WorkOrder.objects.filter(
            status=WorkOrder.Status.COMPLETED,
            completed_at__date__range=(period.start, period.end),
        )
        .select_related("unit", "customer")
        .annotate(
            hours=Coalesce(
                Sum("labor__hours", filter=Q(labor__deleted_at__isnull=True)),
                ZERO,
                output_field=MONEY,
            )
        )
        .order_by("completed_at")
    )
    parts_value = {
        row["work_order_id"]: -(row["v"] or ZERO)
        for row in StockMovement.objects.filter(work_order__in=wos)
        .values("work_order_id")
        .annotate(v=Sum(F("quantity") * F("unit_price"), output_field=MONEY))
    }
    rows: list[Row] = []
    for wo in wos:
        completed = timezone.localtime(wo.completed_at).date() if wo.completed_at else None
        rows.append(
            {
                "number": wo.number,
                "completed": completed,
                "kind": wo.get_kind_display(),
                "unit": unit_label(wo.unit),
                "customer": wo.customer.name if wo.customer else "Our stock",
                "days_open": (completed - wo.opened_on).days if completed else None,
                "hours": wo.hours,
                "parts": parts_value.get(wo.pk),
                "_to": f"/service/{wo.pk}",
            }
        )
    days = [r["days_open"] for r in rows if r["days_open"] is not None]
    return Result(
        rows,
        {
            "number": f"{len(rows)} jobs",
            "days_open": round(sum(days) / len(days)) if days else None,
            "hours": _sum(rows, "hours"),
            "parts": _sum(rows, "parts"),
        },
        ["Days open is the average across jobs."] if days else [],
    )


register(
    Report(
        key="work-orders-completed",
        title="Work orders completed",
        description=(
            "Jobs finished in the period: how long they were open, "
            "labor hours and parts (at list price)."
        ),
        group="Service",
        roles=EVERYONE,
        flags=("service",),
        columns=(
            Column("number", "Work order", primary=True),
            Column("completed", "Completed", "date", primary=True),
            Column("kind", "Type"),
            Column("unit", "Unit", primary=True),
            Column("customer", "Customer"),
            Column("days_open", "Days open", "days"),
            Column("hours", "Labor hours", "qty", primary=True),
            Column("parts", "Parts", "money"),
        ),
        run=work_orders_completed,
    )
)
