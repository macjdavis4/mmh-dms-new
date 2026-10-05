"""Multi-step quote and sale operations, each in one transaction."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.units import services as unit_services
from apps.units.models import OwnershipRecord, StockStatus, Unit, normalize_serial

from .models import Quote, QuoteLine, Sale, SaleUnitChange, TradeIn
from .totals import quote_totals

S = Quote.Status
DEALER = OwnershipRecord.OwnerKind.DEALER
CUSTOMER = OwnershipRecord.OwnerKind.CUSTOMER

# Which status can follow which. "sold" only comes from recording the sale.
TRANSITIONS: dict[str, set[str]] = {
    S.DRAFT: {S.SENT, S.ACCEPTED, S.DECLINED, S.CANCELLED},
    S.SENT: {S.DRAFT, S.ACCEPTED, S.DECLINED, S.CANCELLED},
    S.ACCEPTED: {S.DRAFT, S.SENT, S.DECLINED, S.CANCELLED},
    S.DECLINED: {S.DRAFT},
    S.CANCELLED: {S.DRAFT},
    S.SOLD: set(),
}


def check_editable(quote: Quote) -> None:
    if not quote.is_open:
        raise ValidationError(
            {"status": f"This quote is {quote.get_status_display().lower()}; it can't be changed."}
        )


def _sync(quote: Quote, model: Any, rows: list[dict[str, Any]] | None) -> None:
    """Make the quote's live rows match `rows`: update by id, add new ones,
    remove (soft delete) the ones left out. None leaves them alone."""
    if rows is None:
        return
    existing = {str(r.pk): r for r in model.objects.filter(quote=quote)}
    incoming = {str(r.get("id") or "") for r in rows}
    for row_id, obj in existing.items():
        if row_id not in incoming:
            obj.soft_delete()
    for order, row in enumerate(rows):
        row = dict(row)
        obj = existing.get(str(row.pop("id", "") or "")) or model(quote=quote)
        for key, value in row.items():
            setattr(obj, key, value)
        if model is QuoteLine:
            obj.sort_order = order
        obj.save()


@transaction.atomic
def save_quote(
    quote: Quote,
    *,
    lines: list[dict[str, Any]] | None = None,
    trade_ins: list[dict[str, Any]] | None = None,
) -> Quote:
    if not quote._state.adding:
        locked = Quote.objects.select_for_update().get(pk=quote.pk)
        check_editable(locked)
    try:
        with transaction.atomic():
            quote.save()
            _sync(quote, QuoteLine, lines)
            _sync(quote, TradeIn, trade_ins)
    except IntegrityError as exc:
        if "quote_line_unit_once" in str(exc):
            raise ValidationError({"lines": "The same unit is on the quote twice."}) from exc
        if "trade_in_unit_once" in str(exc):
            raise ValidationError({"trade_ins": "The same trade-in is listed twice."}) from exc
        raise
    return quote


@transaction.atomic
def set_status(quote: Quote, status: str) -> Quote:
    quote = Quote.objects.select_for_update().get(pk=quote.pk)
    if status == quote.status:
        return quote
    if status not in TRANSITIONS.get(quote.status, set()):
        raise ValidationError(
            {
                "status": f"A {quote.get_status_display().lower()} quote can't be marked "
                f"{Quote.Status(status).label.lower()}."
                if status in Quote.Status.values
                else "Unknown status."
            }
        )
    now = timezone.now()
    if status == S.SENT:
        quote.sent_at = quote.sent_at or now
    if status in (S.ACCEPTED, S.DECLINED):
        quote.decided_at = now
    if status == S.DRAFT:
        quote.decided_at = None
    quote.status = status
    quote.save()
    return quote


# --- Recording the sale ----------------------------------------------------------------


@dataclass
class SaleResult:
    sale: Sale
    warnings: list[str]


def _problems(quote: Quote) -> dict[str, list[str]]:
    """Everything that would stop the sale, worded for the salesperson."""
    problems: dict[str, list[str]] = {}
    lines = list(quote.lines.select_related("unit"))
    trades = list(quote.trade_ins.select_related("unit"))
    if not lines:
        problems.setdefault("lines", []).append("Add at least one item to sell.")
    for line in lines:
        if line.unit is None:
            continue
        if line.unit.is_deleted:
            problems.setdefault("lines", []).append(f"{line.unit} has been removed.")
            continue
        owner = unit_services.open_ownership(line.unit)
        if owner is None or owner.owner_kind != DEALER:
            problems.setdefault("lines", []).append(
                f"{line.unit} isn't in our stock now"
                + (f" ({owner.customer.name} owns it)." if owner and owner.customer else ".")
            )
        elif line.unit.stock_status == StockStatus.SOLD:
            problems.setdefault("lines", []).append(f"{line.unit} is already marked sold.")
    for trade in trades:
        if trade.unit is not None:
            owner = unit_services.open_ownership(trade.unit)
            if owner is not None and owner.owner_kind == DEALER:
                problems.setdefault("trade_ins", []).append(
                    f"Trade-in {trade.unit} is already in our stock."
                )
        else:
            norm = normalize_serial(trade.serial_number)
            clash = Unit.all_objects.filter(serial_normalized=norm).first() if norm else None
            if clash is not None:
                problems.setdefault("trade_ins", []).append(
                    f"Trade-in serial {trade.serial_number} is already on {clash}. "
                    "Pick that unit on the trade-in instead."
                )
    return problems


def sale_problems(quote: Quote) -> dict[str, list[str]]:
    return _problems(quote)


def _change(unit: Unit, **kwargs: Any) -> unit_services.ChangeResult:
    """change_hands, with its date error worded for the sale."""
    try:
        return unit_services.change_hands(unit, **kwargs)
    except ValidationError as exc:
        detail = getattr(exc, "message_dict", {})
        if "start_date" in detail:
            raise ValidationError({"sale_date": f"{unit}: {detail['start_date'][0]}"}) from exc
        raise


@transaction.atomic
def record_sale(
    quote: Quote,
    *,
    sale_date: date,
    invoice_number: str = "",
    hours: dict[str, Decimal] | None = None,
) -> SaleResult:
    """Sold units go to the customer (reason: sold, with the line's price);
    trade-ins come into our stock (reason: trade-in, with the allowance).
    A described trade-in becomes a unit first. Everything or nothing."""
    quote = Quote.objects.select_for_update().select_related("customer").get(pk=quote.pk)
    if quote.status not in Quote.OPEN_STATUSES:
        raise ValidationError(
            {"status": f"This quote is {quote.get_status_display().lower()}; it can't be sold."}
        )
    if sale_date > timezone.localdate():
        raise ValidationError({"sale_date": "Can't be in the future. Record it on the day."})
    if problems := _problems(quote):
        raise ValidationError(problems)
    hours = hours or {}
    totals = quote_totals(quote)
    sale = Sale.objects.create(
        quote=quote,
        customer=quote.customer,
        salesperson=quote.salesperson,
        sale_date=sale_date,
        invoice_number=invoice_number,
        subtotal=totals.subtotal,
        trade_allowance=totals.trade_allowance,
        trade_payoff=totals.trade_payoff,
        taxable_amount=totals.taxable_amount,
        tax_rate=totals.tax_rate,
        tax=totals.tax,
        total=totals.total,
    )
    reference = (f"{sale.number} / {invoice_number}" if invoice_number else sale.number)[:60]
    warnings: list[str] = []

    for trade in quote.trade_ins.select_related("unit"):
        created = False
        unit = trade.unit
        if unit is None:
            unit = Unit.objects.create(
                make=trade.make,
                model=trade.model,
                serial_number=trade.serial_number,
                year=trade.year,
                condition="used",
                notes=trade.description,
            )
            unit_services.transfer_ownership(
                unit,
                owner_kind=CUSTOMER,
                customer=quote.customer,
                start_date=sale_date,
                note=f"Added from trade-in on {quote.number}",
            )
            trade.unit = unit
            trade.save()
            created = True
        change = _change(
            unit,
            owner_kind=DEALER,
            reason=OwnershipRecord.Reason.TRADE_IN,
            start_date=sale_date,
            price=trade.allowance,
            hours=trade.hours,
            reference=reference,
            note=f"Trade-in on {quote.number}",
        )
        if change.hours_warning:
            warnings.append(f"{unit}: {change.hours_warning}")
        SaleUnitChange.objects.create(
            sale=sale, ownership=change.record, kind="trade_in", created_unit=created
        )

    for line in quote.lines.select_related("unit"):
        if line.unit is None:
            continue
        change = _change(
            line.unit,
            owner_kind=CUSTOMER,
            customer=quote.customer,
            reason=OwnershipRecord.Reason.SOLD,
            start_date=sale_date,
            price=line.amount,
            hours=hours.get(str(line.unit_id)),
            reference=reference,
            note=f"Sold on {quote.number}",
        )
        if change.hours_warning:
            warnings.append(f"{line.unit}: {change.hours_warning}")
        SaleUnitChange.objects.create(sale=sale, ownership=change.record, kind="sold")

    quote.status = S.SOLD
    quote.decided_at = quote.decided_at or timezone.now()
    quote.save()
    return SaleResult(sale, warnings)


@transaction.atomic
def void_sale(sale: Sale, reason: str) -> Sale:
    """Undo every change of hands the sale made and reopen the quote (as
    accepted). Only possible while those changes are still each unit's latest."""
    sale = Sale.objects.select_for_update().get(pk=sale.pk)
    if sale.status == Sale.Status.VOIDED:
        raise ValidationError({"status": "This sale is already voided."})
    if not reason.strip():
        raise ValidationError({"reason": "Say why the sale is being voided."})
    changes = list(sale.unit_changes.select_related("ownership", "ownership__unit"))
    moved_on = [
        str(c.ownership.unit)
        for c in changes
        if c.ownership.is_deleted or c.ownership.end_date is not None
    ]
    if moved_on:
        raise ValidationError(
            {
                "status": "These units have changed hands again since: "
                + ", ".join(moved_on)
                + ". Undo those changes first."
            }
        )
    for change in reversed(changes):
        unit_services.undo_change(change.ownership.unit, change.ownership.pk)
    sale.status = Sale.Status.VOIDED
    sale.voided_at = timezone.now()
    sale.void_reason = reason.strip()[:300]
    sale.save()
    quote = Quote.objects.select_for_update().get(pk=sale.quote_id)
    quote.status = S.ACCEPTED
    quote.save()
    return sale
