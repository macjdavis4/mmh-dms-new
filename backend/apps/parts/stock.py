"""The parts stock ledger. Every change to stock goes through `_move`, which
locks the part's stock row, refuses to go below zero, writes the ledger line
and updates the on-hand count in one transaction."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import DecimalField, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import Part, PartStock, StockCheck, StockMovement

logger = logging.getLogger(__name__)
K = StockMovement.Kind
ZERO = Decimal("0")


def _qty(value: Decimal) -> str:
    """2.00 -> "2"; 1.50 -> "1.5"."""
    text = f"{value.normalize():f}"
    return text


def on_hand(part: Part) -> Decimal:
    stock = PartStock.objects.filter(part=part).first()
    return stock.on_hand if stock else ZERO


def ledger_total(part: Part) -> Decimal:
    total = StockMovement.objects.filter(part=part).aggregate(
        t=Coalesce(Sum("quantity"), Value(ZERO), output_field=DecimalField())
    )["t"]
    return Decimal(total)


def _move(
    part: Part,
    kind: str,
    quantity: Decimal,
    *,
    work_order: Any = None,
    unit_cost: Decimal | None = None,
    unit_price: Decimal | None = None,
    reference: str = "",
    note: str = "",
    reverses: StockMovement | None = None,
    occurred_at: datetime | None = None,
) -> StockMovement:
    PartStock.objects.get_or_create(part=part)
    stock = PartStock.objects.select_for_update().get(part=part)
    balance = stock.on_hand + quantity
    if balance < 0:
        raise ValidationError(
            {
                "quantity": f"Only {_qty(stock.on_hand)} of {part.part_number} on hand. "
                "If the shelf has more, count it first."
            }
        )
    movement = StockMovement(  # type: ignore[misc]  # MONEY fields are nullable
        part=part,
        kind=kind,
        quantity=quantity,
        work_order=work_order,
        unit_cost=unit_cost,
        unit_price=unit_price,
        reference=reference,
        note=note,
        reverses=reverses,
        balance_after=balance,
        occurred_at=occurred_at or timezone.now(),
    )
    movement.save()
    stock.on_hand = balance
    stock.save()
    return movement


def _positive(quantity: Decimal) -> None:
    if quantity <= 0:
        raise ValidationError({"quantity": "Must be more than zero."})


def _usable(part: Part) -> None:
    if part.is_deleted:
        raise ValidationError({"part": "That part has been removed from the catalog."})


@transaction.atomic
def receive(
    part: Part,
    quantity: Decimal,
    *,
    unit_cost: Decimal | None = None,
    reference: str = "",
    note: str = "",
) -> StockMovement:
    """Parts arrived (by hand for now; from invoices in Phase 11)."""
    _positive(quantity)
    _usable(part)
    if unit_cost is None:
        unit_cost = part.cost
    return _move(part, K.RECEIVE, quantity, unit_cost=unit_cost, reference=reference, note=note)


@transaction.atomic
def count(part: Part, counted: Decimal, *, note: str = "", reference: str = "") -> StockMovement:
    """Set stock to what's on the shelf. The first count is the opening count;
    later ones record the difference as an adjustment."""
    if counted < 0:
        raise ValidationError({"counted": "Can't be below zero."})
    _usable(part)
    PartStock.objects.get_or_create(part=part)
    current = PartStock.objects.select_for_update().get(part=part).on_hand
    difference = counted - current
    if difference == 0:
        raise ValidationError({"counted": f"That matches what we have ({_qty(current)})."})
    first = not StockMovement.objects.filter(part=part).exists()
    kind = K.OPENING if first and difference > 0 else K.ADJUST
    return _move(part, kind, difference, unit_cost=part.cost, note=note, reference=reference)


def _open_work_order(work_order: Any) -> None:
    """Lock the work order so it can't be closed while parts go on or off it."""
    work_order = type(work_order).objects.select_for_update().get(pk=work_order.pk)
    if not work_order.is_open:
        raise ValidationError(
            {"work_order": f"{work_order.number} is {work_order.get_status_display().lower()}."}
        )


@transaction.atomic
def issue(part: Part, work_order: Any, quantity: Decimal, *, note: str = "") -> StockMovement:
    """A mechanic took parts off the shelf for a job. Price and cost are
    kept as they are today."""
    _positive(quantity)
    _usable(part)
    _open_work_order(work_order)
    return _move(
        part,
        K.ISSUE,
        -quantity,
        work_order=work_order,
        unit_cost=part.cost,
        unit_price=part.list_price,
        note=note,
    )


def used_on(work_order: Any, part: Part) -> Decimal:
    """How many of a part are on the work order now (issued less returned)."""
    total = StockMovement.objects.filter(work_order=work_order, part=part).aggregate(
        t=Coalesce(Sum("quantity"), Value(ZERO), output_field=DecimalField())
    )["t"]
    return -Decimal(total)


@transaction.atomic
def return_to_stock(
    part: Part, work_order: Any, quantity: Decimal, *, note: str = ""
) -> StockMovement:
    """Unused parts back on the shelf from a job."""
    _positive(quantity)
    _open_work_order(work_order)
    used = used_on(work_order, part)
    if quantity > used:
        raise ValidationError(
            {"quantity": f"Only {_qty(used)} of {part.part_number} on {work_order.number}."}
        )
    last = (
        StockMovement.objects.filter(work_order=work_order, part=part, kind=K.ISSUE)
        .order_by("-occurred_at", "-created_at")
        .first()
    )
    return _move(
        part,
        K.RETURN,
        quantity,
        work_order=work_order,
        unit_cost=last.unit_cost if last else part.cost,
        unit_price=last.unit_price if last else part.list_price,
        note=note,
    )


@transaction.atomic
def reverse(movement: StockMovement, *, note: str = "") -> StockMovement:
    """Put a mistaken movement right with an equal and opposite one."""
    movement = StockMovement.objects.select_for_update().get(pk=movement.pk)
    if movement.kind == K.REVERSAL:
        raise ValidationError({"movement": "This is already a reversal."})
    if StockMovement.objects.filter(reverses=movement).exists():
        raise ValidationError({"movement": "This has already been reversed."})
    if movement.work_order is not None:
        _open_work_order(movement.work_order)
    return _move(
        movement.part,
        K.REVERSAL,
        -movement.quantity,
        work_order=movement.work_order,
        unit_cost=movement.unit_cost,
        unit_price=movement.unit_price,
        reverses=movement,
        note=note or f"Reverses: {movement.get_kind_display().lower()}",
    )


# --- Work order parts ---------------------------------------------------------------------


@dataclass
class UsedPart:
    part: Part
    quantity: Decimal
    unit_price: Decimal | None
    amount: Decimal | None


def parts_used(work_order: Any) -> list[UsedPart]:
    """Net parts on a work order, one line per part, priced as issued."""
    rows: dict[Any, dict[str, Any]] = {}
    for m in StockMovement.objects.filter(work_order=work_order).select_related("part"):
        row = rows.setdefault(
            m.part_id, {"part": m.part, "qty": ZERO, "amount": ZERO, "priced": True}
        )
        row["qty"] -= m.quantity
        if m.unit_price is None:
            row["priced"] = False
        else:
            row["amount"] -= m.quantity * m.unit_price
    result = []
    for row in rows.values():
        if row["qty"] == 0:
            continue
        price = (row["amount"] / row["qty"]).quantize(Decimal("0.01")) if row["priced"] else None
        amount = row["amount"].quantize(Decimal("0.01")) if row["priced"] else None
        result.append(UsedPart(row["part"], row["qty"], price, amount))
    return sorted(result, key=lambda r: r.part.number_normalized)


# --- Nightly check ------------------------------------------------------------------------


def check_drift() -> StockCheck:
    """Recompute every part's on hand from the ledger and compare it with the
    stored count. Differences are recorded and logged as errors (Sentry alerts);
    they are not "fixed" here, because a person needs to find out why."""
    run = StockCheck.objects.create()
    ledger = {
        row["part"]: Decimal(row["total"])
        for row in StockMovement.objects.values("part").annotate(total=Sum("quantity"))
    }
    stored = {s.part_id: s.on_hand for s in PartStock.objects.all()}
    drift = []
    for part_id in sorted(set(ledger) | set(stored), key=str):
        in_ledger = ledger.get(part_id, ZERO)
        in_store = stored.get(part_id, ZERO)
        if in_ledger != in_store:
            number = (
                Part.all_objects.filter(pk=part_id).values_list("part_number", flat=True).first()
            )
            drift.append(
                {
                    "part": str(part_id),
                    "part_number": number or "",
                    "ledger": str(in_ledger),
                    "stored": str(in_store),
                }
            )
    run.parts_checked = len(set(ledger) | set(stored))
    run.drift = drift
    run.finished_at = timezone.now()
    run.save()
    if drift:
        logger.error(
            "stock drift: %d part(s) differ from the ledger",
            len(drift),
            extra={"drift": drift},
        )
    else:
        logger.info("stock check: %d parts match the ledger", run.parts_checked)
    return run
