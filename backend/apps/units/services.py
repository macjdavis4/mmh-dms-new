"""Multi-step unit operations. Each runs in one transaction (CLAUDE.md)."""

from __future__ import annotations

import io
import mimetypes
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile, File
from django.db import transaction
from PIL import Image, ImageOps, UnidentifiedImageError

from apps.customers.models import Customer

from .models import (
    TO_CUSTOMER_REASONS,
    TO_STOCK_REASONS,
    Condition,
    HourMeterReading,
    OwnershipRecord,
    StockStatus,
    Unit,
    UnitFile,
)

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_PIXELS = 60_000_000  # refuse decompression bombs
THUMB_EDGE = 640
IMAGE_TYPES = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
MONEY_FIELDS = ("cost", "asking_price", "sale_price")


# --- Ownership --------------------------------------------------------------------------


def open_ownership(unit: Unit) -> OwnershipRecord | None:
    return unit.ownerships.filter(end_date__isnull=True).select_related("customer").first()


@transaction.atomic
def transfer_ownership(
    unit: Unit,
    *,
    owner_kind: str,
    customer: Customer | None = None,
    start_date: date,
    note: str = "",
    reason: str = "",
) -> OwnershipRecord:
    """Close the current ownership record and open a new one. Only the
    records change; `change_hands` also updates the unit's stock and prices."""
    Unit.objects.select_for_update().filter(pk=unit.pk).first()  # serialize transfers per unit
    if owner_kind == OwnershipRecord.OwnerKind.CUSTOMER and customer is None:
        raise ValidationError({"customer": "Pick the customer who owns it now."})
    if owner_kind == OwnershipRecord.OwnerKind.DEALER:
        customer = None
    current = open_ownership(unit)
    if current is not None:
        if current.owner_kind == owner_kind and current.customer_id == (
            customer.pk if customer else None
        ):
            raise ValidationError({"customer": "That's already the current owner."})
        if start_date < current.start_date:
            raise ValidationError(
                {
                    "start_date": f"Must be on or after {current.start_date:%b %d, %Y}, "
                    "when the current owner took it."
                }
            )
        current.end_date = start_date
        current.save()
    return OwnershipRecord.objects.create(
        unit=unit,
        owner_kind=owner_kind,
        customer=customer,
        start_date=start_date,
        note=note,
        reason=reason,
    )


# --- Units changing hands ------------------------------------------------------------------

Reason = OwnershipRecord.Reason
DEALER = OwnershipRecord.OwnerKind.DEALER
CUSTOMER = OwnershipRecord.OwnerKind.CUSTOMER
# Unit fields a change of hands can set, and an undo can put back.
DEAL_UNIT_FIELDS = ("stock_status", "condition", "cost", "asking_price", "sale_price")


def check_reason(reason: str, *, owner_kind: str, from_kind: str | None) -> None:
    """The reason must fit who had it and who has it now."""
    allowed = TO_CUSTOMER_REASONS if owner_kind == CUSTOMER else TO_STOCK_REASONS
    if reason not in allowed:
        raise ValidationError(
            {
                "reason": "Coming back to our stock: trade-in, repossession, bought back, "
                "lease return, bought used or other."
                if owner_kind == DEALER
                else "Going to a customer: sold, sold between customers or other."
            }
        )
    if reason == Reason.SOLD and from_kind == CUSTOMER:
        raise ValidationError(
            {"reason": "It belongs to a customer, not our stock. Use 'Sold between customers'."}
        )
    if reason == Reason.PRIVATE_SALE and from_kind != CUSTOMER:
        raise ValidationError(
            {"reason": "'Sold between customers' is for a unit a customer owns. Use 'Sold'."}
        )


def _money(value: Any) -> Any:
    """JSON-safe, comparable copy of a unit field (money as '1234.00')."""
    return f"{Decimal(value):.2f}" if isinstance(value, Decimal) else value


def _from_our_stock(record: OwnershipRecord) -> bool:
    previous = previous_ownership(record)
    return previous is not None and previous.owner_kind == DEALER


@dataclass
class ChangeResult:
    record: OwnershipRecord
    hours_warning: str | None


@transaction.atomic
def change_hands(
    unit: Unit,
    *,
    owner_kind: str,
    reason: str,
    start_date: date,
    customer: Customer | None = None,
    price: Decimal | None = None,
    reference: str = "",
    note: str = "",
    hours: Decimal | None = None,
) -> ChangeResult:
    """Record a sale, trade-in, repossession, buy-back, lease return or
    purchase. The unit stays one record (one serial); its stock status,
    condition and prices follow the new owner:

    * Out of our stock to a customer: Sold. The sale keeps its own price and
      the unit's cost at the time; the unit's sale price is set.
    * Back into our stock: In prep and Used. What we paid becomes the unit's
      cost; asking and sale price start again empty for this time in stock.
      The previous sale keeps its own price and cost on its record.
    * Between customers: only the owner changes.
    """
    unit = Unit.objects.select_for_update().get(pk=unit.pk)
    current = open_ownership(unit)
    from_kind = current.owner_kind if current else None
    check_reason(reason, owner_kind=owner_kind, from_kind=from_kind)
    if price is not None and not (owner_kind == DEALER or from_kind == DEALER):
        raise ValidationError({"price": "A price is only kept for units we buy or sell."})

    before = {f: getattr(unit, f) for f in DEAL_UNIT_FIELDS}
    if (
        current is not None
        and current.owner_kind == CUSTOMER
        and unit.stock_status == StockStatus.SOLD
        and _from_our_stock(current)
    ):
        # Keep the closing sale's numbers with it before the unit changes.
        if current.price is None and unit.sale_price is not None:
            current.price = unit.sale_price
        if current.cost is None and unit.cost is not None:
            current.cost = unit.cost
        current.save()

    sale_out = owner_kind == CUSTOMER and from_kind == DEALER
    record = transfer_ownership(
        unit,
        owner_kind=owner_kind,
        customer=customer,
        start_date=start_date,
        note=note,
        reason=reason,
    )
    if owner_kind == DEALER:
        unit.stock_status = StockStatus.IN_PREP
        unit.condition = Condition.USED
        unit.cost = price  # type: ignore[assignment]
        unit.asking_price = None  # type: ignore[assignment]
        unit.sale_price = None  # type: ignore[assignment]
        record.price = price  # type: ignore[assignment]
    elif sale_out:
        unit.stock_status = StockStatus.SOLD
        record.price = price if price is not None else unit.sale_price
        record.cost = unit.cost
        unit.sale_price = record.price  # type: ignore[assignment]
    record.reference = reference

    warning = None
    if hours is not None:
        label = Reason(reason).label
        owner = customer.name if customer else "our stock"
        result = record_hours(
            unit,
            hours=hours,
            reading_date=start_date,
            source=HourMeterReading.Source.SALE,
            note=f"{label}: to {owner}"[:200],
        )
        record.hour_reading = result.reading
        warning = result.warning

    after = {f: getattr(unit, f) for f in DEAL_UNIT_FIELDS}
    changed = {f: [_money(before[f]), _money(after[f])] for f in DEAL_UNIT_FIELDS}
    record.unit_changes = {f: v for f, v in changed.items() if v[0] != v[1]}
    if record.unit_changes:
        unit.save()
    record.save()
    return ChangeResult(record, warning)


@transaction.atomic
def edit_deal(record: OwnershipRecord, changes: dict[str, Any]) -> OwnershipRecord:
    """Correct a recorded change (reason, price, cost, reference, note). On the
    current owner's record, a unit price that matched the old figure follows."""
    record = OwnershipRecord.objects.select_for_update().get(pk=record.pk)
    previous = previous_ownership(record)
    if "reason" in changes and changes["reason"] != record.reason:
        if previous is None:
            raise ValidationError({"reason": "The first owner on record has no reason."})
        check_reason(changes["reason"], owner_kind=record.owner_kind, from_kind=previous.owner_kind)
    has_deal = record.owner_kind == DEALER or (
        previous is not None and previous.owner_kind == DEALER
    )
    if not has_deal and any(changes.get(k) is not None for k in ("price", "cost")):
        raise ValidationError({"price": "A price is only kept for units we buy or sell."})
    old_price = record.price
    for key, value in changes.items():
        setattr(record, key, value)
    record.save()

    if record.end_date is None and "price" in changes and record.price != old_price:
        unit = Unit.objects.select_for_update().get(pk=record.unit_id)
        field = "cost" if record.owner_kind == DEALER else "sale_price"
        follows = record.owner_kind == DEALER or unit.stock_status == StockStatus.SOLD
        if follows and getattr(unit, field) == old_price:
            setattr(unit, field, record.price)
            unit.save()
    return record


def previous_ownership(record: OwnershipRecord) -> OwnershipRecord | None:
    """The record this one followed (closed on the day this one started)."""
    return (
        OwnershipRecord.objects.filter(unit_id=record.unit_id, end_date=record.start_date)
        .exclude(pk=record.pk)
        .filter(created_at__lte=record.created_at)
        .order_by("-created_at")
        .first()
    )


@dataclass
class UndoResult:
    restored: OwnershipRecord
    kept: list[str]


@transaction.atomic
def undo_change(unit: Unit, record_id: Any) -> UndoResult:
    """Undo the latest change of hands: the previous owner is current again,
    and the unit's stock status, condition and prices go back to what they
    were, except any changed by hand since (those are kept and listed)."""
    unit = Unit.objects.select_for_update().get(pk=unit.pk)
    record = open_ownership(unit)
    if record is None or str(record.pk) != str(record_id):
        raise ValidationError({"record": "Only the latest change can be undone. Reload the page."})
    previous = previous_ownership(record)
    if previous is None or record.unit_changes is None:
        raise ValidationError(
            {"record": "This change can't be undone here. Change the owner back instead."}
        )
    kept: list[str] = []
    dirty = False
    for field, (was, became) in record.unit_changes.items():
        if _money(getattr(unit, field)) == became:
            setattr(unit, field, Decimal(was) if was is not None and field in MONEY_FIELDS else was)
            dirty = True
        else:
            kept.append(field)
    if record.hour_reading_id:
        reading = HourMeterReading.objects.filter(pk=record.hour_reading_id).first()
        if reading is not None:
            reading.soft_delete()
    record.soft_delete()
    previous.end_date = None
    previous.save()
    if dirty:
        unit.save()
    return UndoResult(previous, kept)


# --- Hour meter ---------------------------------------------------------------------------


@dataclass
class HoursResult:
    reading: HourMeterReading
    warning: str | None


@transaction.atomic
def record_hours(
    unit: Unit, *, hours: Decimal, reading_date: date, source: str, note: str = ""
) -> HoursResult:
    """Readings are kept as entered. A reading lower than an earlier one is
    allowed (meters get replaced) but returns a warning to show the user."""
    previous = (
        unit.hour_readings.filter(reading_date__lte=reading_date)
        .order_by("-reading_date", "-created_at")
        .first()
    )
    reading = HourMeterReading.objects.create(
        unit=unit, hours=hours, reading_date=reading_date, source=source, note=note
    )
    warning = None
    if previous is not None and hours < previous.hours:
        warning = (
            f"This is lower than the {previous.hours} h recorded on "
            f"{previous.reading_date:%b %d, %Y}. "
            "If the hour meter was replaced, add a note saying so."
        )
    return HoursResult(reading, warning)


# --- Files ----------------------------------------------------------------------------------


def _sniff(head: bytes) -> str | None:
    if head.startswith(b"%PDF-"):
        return "application/pdf"
    return None


@transaction.atomic
@dataclass
class Inspected:
    content_type: str
    width: int | None
    height: int | None
    thumbnail: bytes | None


def inspect_upload(data: bytes) -> Inspected:
    """Work out what a file really is from its contents (never its name).
    PDFs pass through; images are verified and get a WebP thumbnail."""
    content_type = _sniff(data[:8])
    if content_type is not None:
        return Inspected(content_type, None, None, None)
    try:
        Image.MAX_IMAGE_PIXELS = MAX_PIXELS
        with Image.open(io.BytesIO(data)) as probe:
            probe.verify()
        with Image.open(io.BytesIO(data)) as img:
            fmt = img.format or ""
            if fmt not in IMAGE_TYPES:
                raise ValidationError({"file": "Use a JPEG, PNG or WebP photo, or a PDF."})
            upright = ImageOps.exif_transpose(img)
            width, height = upright.size
            upright.thumbnail((THUMB_EDGE, THUMB_EDGE))
            buf = io.BytesIO()
            upright.convert("RGB").save(buf, "WEBP", quality=78, method=4)
            return Inspected(IMAGE_TYPES[fmt], width, height, buf.getvalue())
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as exc:
        raise ValidationError(
            {"file": "That file isn't a photo or PDF we can read. Use JPEG, PNG, WebP or PDF."}
        ) from exc


def add_file(unit: Unit, upload: File, *, kind: str, caption: str = "") -> UnitFile:  # type: ignore[type-arg]
    """Validate by content (not by file name), store, and make a thumbnail."""
    if upload.size is None or upload.size == 0:
        raise ValidationError({"file": "The file is empty."})
    if upload.size > MAX_UPLOAD_BYTES:
        raise ValidationError({"file": "Files can be up to 25 MB."})

    data = upload.read()
    inspected = inspect_upload(data)
    content_type, width, height, thumb_bytes = (
        inspected.content_type,
        inspected.width,
        inspected.height,
        inspected.thumbnail,
    )
    if kind == UnitFile.Kind.PHOTO and not content_type.startswith("image/"):
        raise ValidationError({"file": "Photos must be images (JPEG, PNG or WebP)."})

    is_first_photo = (
        kind == UnitFile.Kind.PHOTO and not unit.files.filter(kind=UnitFile.Kind.PHOTO).exists()
    )
    ext = mimetypes.guess_extension(content_type) or ".bin"
    record = UnitFile(
        unit=unit,
        kind=kind,
        original_name=(upload.name or "")[:255],
        content_type=content_type,
        size_bytes=len(data),
        width=width,
        height=height,
        caption=caption,
        is_primary=is_first_photo,
        sort_order=unit.files.count(),
    )
    record.file.save(f"upload{ext}", ContentFile(data), save=False)
    if thumb_bytes is not None:
        record.thumbnail.save("thumb.webp", ContentFile(thumb_bytes), save=False)
    record.save()
    return record


@transaction.atomic
def make_primary_photo(photo: UnitFile) -> None:
    for other in UnitFile.objects.filter(unit=photo.unit, is_primary=True).exclude(pk=photo.pk):
        other.is_primary = False
        other.save()
    photo.is_primary = True
    photo.save()
