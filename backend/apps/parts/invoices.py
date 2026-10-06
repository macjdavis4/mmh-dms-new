"""Supplier invoices: upload, read, check, receive into stock, backorders.

Flow: upload a PDF or photo -> read on the server (`read_invoice`, a job in
production) -> a person checks the suggested lines -> receive what arrived
(all or some of each line) -> anything still to come waits as a backorder
until it is received or closed as "won't come"."""

from __future__ import annotations

import logging
import mimetypes
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile, File
from django.db import transaction
from django.db.models import DecimalField, F, OuterRef, QuerySet, Subquery, Sum, Value
from django.db.models.functions import Coalesce, Upper
from django.utils import timezone

from apps.units.services import MAX_UPLOAD_BYTES, inspect_upload

from . import invoice_reader, stock
from .models import CrossReference, Invoice, InvoiceLine, Part, StockMovement, normalize_number

logger = logging.getLogger(__name__)
S = Invoice.Status
ZERO = Decimal("0")
EDITABLE = (S.REVIEW,)
RECEIVABLE = (S.REVIEW, S.PARTIAL)


# --- Received and outstanding ---------------------------------------------------------------


def received_subquery() -> Coalesce:
    """Sum of stock movements on a line (receipts less their reversals)."""
    total = (
        StockMovement.objects.filter(invoice_line=OuterRef("pk"))
        .values("invoice_line")
        .annotate(t=Sum("quantity"))
        .values("t")
    )
    return Coalesce(
        Subquery(total), Value(ZERO), output_field=DecimalField(max_digits=12, decimal_places=2)
    )


def with_received(qs: QuerySet[InvoiceLine]) -> QuerySet[InvoiceLine]:
    return qs.annotate(received=received_subquery())


def received(line: InvoiceLine) -> Decimal:
    value = getattr(line, "received", None)
    if value is not None:
        return Decimal(value)
    total = StockMovement.objects.filter(invoice_line=line).aggregate(t=Sum("quantity"))["t"]
    return Decimal(total or 0)


def expected(line: InvoiceLine) -> Decimal:
    return line.quantity_shipped + line.quantity_backordered


def outstanding(line: InvoiceLine) -> Decimal:
    """Still to come on this line (0 once closed or for non-stock lines)."""
    if line.not_stocked or line.closed_at is not None:
        return ZERO
    return max(expected(line) - received(line), ZERO)


def refresh_status(invoice: Invoice) -> Invoice:
    """Partly received until every stock line is in or closed."""
    if invoice.status in (S.READING, S.CANCELLED):
        return invoice
    lines = list(with_received(invoice.lines.all()))
    any_received = any(received(line) > 0 for line in lines)
    if not any_received:
        new = S.REVIEW
    elif all(outstanding(line) == 0 for line in lines):
        new = S.RECEIVED
    else:
        new = S.PARTIAL
    if new != invoice.status:
        invoice.status = new
        invoice.save()
    return invoice


def has_receipts(invoice: Invoice) -> bool:
    return StockMovement.objects.filter(invoice_line__invoice=invoice).exists()


# --- Matching parts ------------------------------------------------------------------------


def match_part(number: str, supplier: str = "") -> Part | None:
    """Our part for a number printed on an invoice: our number, another
    brand's number, or the supplier's own number. Replaced parts lead to
    the part that replaced them. Only an unambiguous match is returned."""
    norm = normalize_number(number)
    if len(norm) < 3:
        return None
    candidates = list(Part.objects.filter(number_normalized=norm)[:2])
    if not candidates:
        candidates = list(
            Part.objects.filter(
                pk__in=CrossReference.objects.filter(number_normalized=norm).values("part_id")
            )[:2]
        )
    if not candidates:
        candidates = [
            p
            for p in Part.objects.exclude(vendor_part_number="")
            .filter(vendor_part_number__icontains=number.strip()[:60])
            .only("id", "vendor_part_number", "superseded_by")[:20]
            if normalize_number(p.vendor_part_number) == norm
        ][:2]
    if len(candidates) != 1:
        return None
    return candidates[0].current()


# --- Uploading and reading -----------------------------------------------------------------


@dataclass
class Duplicate:
    invoice: Invoice


def find_duplicate(supplier: str, number: str, exclude: Any = None) -> Invoice | None:
    if not number.strip():
        return None
    qs = (
        Invoice.objects.exclude(status=S.CANCELLED)
        .annotate(s=Upper("supplier"), n=Upper("invoice_number"))
        .filter(s=supplier.strip().upper(), n=number.strip().upper())
    )
    if exclude is not None:
        qs = qs.exclude(pk=exclude)
    return qs.first()


def upload(file: File, *, supplier: str = "") -> Invoice:  # type: ignore[type-arg]
    """Store the file and read it (now in tests and small setups, or as a
    background job). Files are checked by content, not by name."""
    if file.size is None or file.size == 0:
        raise ValidationError({"file": "The file is empty."})
    if file.size > MAX_UPLOAD_BYTES:
        raise ValidationError({"file": "Files can be up to 25 MB."})
    data = file.read()
    content_type = inspect_upload(data).content_type
    invoice = Invoice(
        supplier=supplier.strip()[:120],
        status=S.READING,
        original_name=(file.name or "")[:255],
        content_type=content_type,
        size_bytes=len(data),
    )
    ext = mimetypes.guess_extension(content_type) or ".bin"
    invoice.file.save(f"invoice{ext}", ContentFile(data), save=False)
    invoice.save()
    start_reading(invoice)
    invoice.refresh_from_db()
    return invoice


def start_reading(invoice: Invoice) -> None:
    if settings.INVOICE_READ_INLINE:
        read_invoice(invoice.pk)
        return
    from .tasks import read_parts_invoice

    transaction.on_commit(
        lambda: read_parts_invoice.configure(queueing_lock=f"invoice-{invoice.pk}").defer(
            invoice_id=str(invoice.pk)
        )
    )


def create_blank(*, supplier: str = "") -> Invoice:
    """A paper invoice with no scan: type the lines in."""
    invoice = Invoice(supplier=supplier.strip()[:120], status=S.REVIEW)
    invoice.save()
    return invoice


def _known_supplier(text: str) -> str:
    """A supplier we already buy from whose name appears in the text."""
    lowered = text.lower()
    names = Part.objects.exclude(vendor="").values_list("vendor", flat=True).distinct().order_by()
    hits = [n for n in names if len(n) >= 3 and n.lower() in lowered]
    hits += [
        n
        for n in Invoice.objects.exclude(supplier="")
        .values_list("supplier", flat=True)
        .distinct()
        .order_by()
        if len(n) >= 3 and n.lower() in lowered and n not in hits
    ]
    return max(hits, key=len) if hits else ""


def read_invoice(invoice_id: Any) -> None:
    """Read the file and suggest the header and lines. Safe to run again:
    it only acts on an invoice still marked as reading."""
    with transaction.atomic():
        invoice = Invoice.objects.select_for_update().filter(pk=invoice_id).first()
        if invoice is None or invoice.status != S.READING:
            return
        data = invoice.file.open("rb").read() if invoice.file else b""
    try:
        result = invoice_reader.read_file(data, invoice.content_type)
    except invoice_reader.ReadError as exc:
        with transaction.atomic():
            invoice = Invoice.objects.select_for_update().get(pk=invoice_id)
            if invoice.status != S.READING:
                return
            invoice.read_error = str(exc)[:300]
            invoice.read_at = timezone.now()
            invoice.status = S.REVIEW
            invoice.save()
        logger.warning("invoice could not be read", extra={"invoice": str(invoice_id)})
        return
    suggestion = invoice_reader.suggest(result.text)
    with transaction.atomic():
        invoice = Invoice.objects.select_for_update().get(pk=invoice_id)
        if invoice.status != S.READING:
            return
        invoice.extracted_text = result.text
        invoice.read_method = result.method
        invoice.read_error = ""
        invoice.read_at = timezone.now()
        if not invoice.supplier:
            invoice.supplier = _known_supplier(result.text)[:120]
        invoice.invoice_number = invoice.invoice_number or suggestion.invoice_number
        invoice.invoice_date = invoice.invoice_date or suggestion.invoice_date
        invoice.total = invoice.total if invoice.total is not None else suggestion.total
        invoice.freight = invoice.freight if invoice.freight is not None else suggestion.freight
        invoice.tax = invoice.tax if invoice.tax is not None else suggestion.tax
        if find_duplicate(invoice.supplier, invoice.invoice_number, exclude=invoice.pk):
            # Keep what was read but don't claim the number: the person decides.
            invoice.read_error = (
                f"{invoice.supplier} invoice {invoice.invoice_number} was already entered. "
                "Check it isn't the same invoice twice."
            )[:300]
            invoice.invoice_number = ""
        if not suggestion.lines:
            invoice.read_error = invoice.read_error or (
                "No lines were recognized. Add them by hand; the text that was read is below."
            )
        invoice.status = S.REVIEW
        invoice.save()
        for line in invoice.lines.all():
            line.soft_delete()
        for position, s in enumerate(suggestion.lines):
            part = None if s.not_stocked else match_part(s.part_number, invoice.supplier)
            reason = s.check_reason
            if not part and not s.not_stocked and s.part_number:
                reason = "; ".join(x for x in (reason, "Part not in the catalog") if x)
            InvoiceLine(  # type: ignore[misc]  # MONEY fields are nullable
                invoice=invoice,
                position=position,
                raw_text=s.raw_text,
                part=part,
                part_number=s.part_number,
                description=s.description,
                quantity_shipped=s.quantity_shipped,
                quantity_backordered=s.quantity_backordered,
                unit_cost=s.unit_cost,
                not_stocked=s.not_stocked,
                check_reason=reason[:200],
            ).save()


@transaction.atomic
def read_again(invoice: Invoice) -> Invoice:
    invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
    if not invoice.file:
        raise ValidationError({"file": "There's no file to read. Type the lines in."})
    if invoice.status not in EDITABLE or has_receipts(invoice):
        raise ValidationError({"status": "Parts have been received from this invoice already."})
    invoice.status = S.READING
    invoice.read_error = ""
    invoice.save()
    start_reading(invoice)
    return invoice


# --- Checking (editing) ---------------------------------------------------------------------


LINE_FIELDS = (
    "part",
    "part_number",
    "description",
    "quantity_shipped",
    "quantity_backordered",
    "unit_cost",
    "not_stocked",
)


@transaction.atomic
def save_invoice(
    invoice: Invoice, values: dict[str, Any], lines: list[dict[str, Any]] | None
) -> Invoice:
    """Save the header, and the lines when given (only before anything is
    received; afterwards lines can only be closed)."""
    invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
    if invoice.status in (S.READING, S.CANCELLED):
        raise ValidationError(
            {"status": f"This invoice is {invoice.get_status_display().lower()}."}
        )
    for name, value in values.items():
        setattr(invoice, name, value)
    if dup := find_duplicate(invoice.supplier, invoice.invoice_number, exclude=invoice.pk):
        raise ValidationError(
            {
                "invoice_number": f"{dup} is already entered"
                f" ({dup.get_status_display().lower()}). Don't receive the same invoice twice."
            }
        )
    invoice.save()
    if lines is None:
        return invoice
    if has_receipts(invoice):
        raise ValidationError(
            {"lines": "Parts have been received from this invoice, so its lines can't change."}
        )
    existing = {str(line.pk): line for line in invoice.lines.all()}
    keep: set[str] = set()
    for position, row in enumerate(lines):
        row = dict(row)
        line = existing.get(str(row.pop("id", "") or "")) or InvoiceLine(invoice=invoice)
        changed = any(
            getattr(line, f, None) != row.get(f, getattr(line, f, None)) for f in LINE_FIELDS
        )
        for name in LINE_FIELDS:
            if name in row:
                setattr(line, name, row[name])
        if line.not_stocked:
            line.part = None
        line.position = position
        if changed:
            line.check_reason = ""  # a person has looked at it
        line.save()
        keep.add(str(line.pk))
    for line_id, line in existing.items():
        if line_id not in keep:
            line.soft_delete()
    return invoice


# --- Receiving -----------------------------------------------------------------------------


@transaction.atomic
def receive(
    invoice: Invoice, rows: list[dict[str, Any]], *, update_costs: bool = False
) -> list[StockMovement]:
    """Put what arrived into stock: any part of each line, any number of times."""
    invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
    if invoice.status not in RECEIVABLE:
        raise ValidationError(
            {"status": f"This invoice is {invoice.get_status_display().lower()}."}
        )
    if not invoice.supplier.strip() or not invoice.invoice_number.strip():
        raise ValidationError(
            {"invoice_number": "Fill in the supplier and invoice number before receiving."}
        )
    lines = {str(line.pk): line for line in with_received(invoice.lines.select_related("part"))}
    reference = f"{invoice.supplier} {invoice.invoice_number}"[:60]
    errors: dict[str, str] = {}
    todo: list[tuple[InvoiceLine, Decimal]] = []
    for row in rows:
        line = lines.get(str(row["line"]))
        qty = Decimal(row["quantity"])
        if line is None:
            raise ValidationError({"lines": "That line isn't on this invoice."})
        if qty == 0:
            continue
        label = line.part_number or line.description or f"Line {line.position + 1}"
        if line.not_stocked:
            errors[str(line.pk)] = f"{label} isn't a stock item."
        elif line.part is None:
            errors[str(line.pk)] = f"Pick our part for {label} first."
        elif qty < 0:
            errors[str(line.pk)] = "Can't be below zero."
        elif qty > outstanding(line):
            errors[str(line.pk)] = (
                f"Only {stock._qty(outstanding(line))} of {label} still to come on this invoice."
            )
        else:
            todo.append((line, qty))
    if errors:
        raise ValidationError({"lines": [f"{msg}" for msg in errors.values()]})
    if not todo:
        raise ValidationError({"lines": "Enter how many arrived on at least one line."})
    movements = []
    for line, qty in todo:
        assert line.part is not None
        movements.append(
            stock.receive(
                line.part,
                qty,
                unit_cost=line.unit_cost,
                reference=reference,
                invoice_line=line,
            )
        )
        if update_costs and line.unit_cost is not None and line.part.cost != line.unit_cost:
            part = Part.objects.select_for_update().get(pk=line.part_id)
            part.cost = line.unit_cost
            part.save()
    refresh_status(invoice)
    return movements


@transaction.atomic
def close_line(line: InvoiceLine, reason: str) -> InvoiceLine:
    """The rest of this line won't come (e.g. the supplier cancelled the backorder)."""
    line = InvoiceLine.objects.select_for_update().select_related("invoice").get(pk=line.pk)
    if line.invoice.status not in RECEIVABLE:
        raise ValidationError({"status": "This invoice is closed."})
    if not reason.strip():
        raise ValidationError({"reason": "Say why the rest won't come."})
    if line.closed_at is not None:
        raise ValidationError({"reason": "This line is already closed."})
    line.closed_at = timezone.now()
    line.closed_reason = reason.strip()[:200]
    line.save()
    refresh_status(line.invoice)
    return line


@transaction.atomic
def reopen_line(line: InvoiceLine) -> InvoiceLine:
    line = InvoiceLine.objects.select_for_update().select_related("invoice").get(pk=line.pk)
    if line.invoice.status == S.CANCELLED:
        raise ValidationError({"status": "This invoice is cancelled."})
    line.closed_at = None
    line.closed_reason = ""
    line.save()
    refresh_status(line.invoice)
    return line


@transaction.atomic
def cancel(invoice: Invoice, reason: str) -> Invoice:
    invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
    if has_receipts(invoice):
        raise ValidationError(
            {"status": "Parts were received from this invoice. Reverse them first (part page)."}
        )
    if not reason.strip():
        raise ValidationError({"reason": "Say why, e.g. entered twice."})
    invoice.status = S.CANCELLED
    invoice.cancel_reason = reason.strip()[:200]
    invoice.save()
    return invoice


def backorders() -> QuerySet[InvoiceLine]:
    """Stock lines still to come on invoices that have started receiving."""
    return (
        with_received(
            InvoiceLine.objects.filter(
                invoice__deleted_at__isnull=True,
                invoice__status=S.PARTIAL,
                not_stocked=False,
                closed_at__isnull=True,
            ).select_related("invoice", "part")
        )
        .filter(received__lt=F("quantity_shipped") + F("quantity_backordered"))  # type: ignore[misc]
        .order_by("invoice__invoice_date", "invoice__created_at", "position")
    )
