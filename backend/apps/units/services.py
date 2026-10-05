"""Multi-step unit operations. Each runs in one transaction (CLAUDE.md)."""

from __future__ import annotations

import io
import mimetypes
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from PIL import Image, ImageOps, UnidentifiedImageError

from apps.customers.models import Customer

from .models import HourMeterReading, OwnershipRecord, Unit, UnitFile

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_PIXELS = 60_000_000  # refuse decompression bombs
THUMB_EDGE = 640
IMAGE_TYPES = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}


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
) -> OwnershipRecord:
    """Close the current ownership record and open a new one."""
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
        unit=unit, owner_kind=owner_kind, customer=customer, start_date=start_date, note=note
    )


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
def add_file(unit: Unit, upload: UploadedFile, *, kind: str, caption: str = "") -> UnitFile:
    """Validate by content (not by file name), store, and make a thumbnail."""
    if upload.size is None or upload.size == 0:
        raise ValidationError({"file": "The file is empty."})
    if upload.size > MAX_UPLOAD_BYTES:
        raise ValidationError({"file": "Files can be up to 25 MB."})

    data = upload.read()
    content_type = _sniff(data[:8])
    width = height = None
    thumb_bytes: bytes | None = None
    if content_type is None:
        try:
            Image.MAX_IMAGE_PIXELS = MAX_PIXELS
            with Image.open(io.BytesIO(data)) as probe:
                probe.verify()
            with Image.open(io.BytesIO(data)) as img:
                fmt = img.format or ""
                if fmt not in IMAGE_TYPES:
                    raise ValidationError({"file": "Use a JPEG, PNG or WebP photo, or a PDF."})
                content_type = IMAGE_TYPES[fmt]
                upright = ImageOps.exif_transpose(img)
                width, height = upright.size
                upright.thumbnail((THUMB_EDGE, THUMB_EDGE))
                buf = io.BytesIO()
                upright.convert("RGB").save(buf, "WEBP", quality=78, method=4)
                thumb_bytes = buf.getvalue()
        except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as exc:
            raise ValidationError(
                {"file": "That file isn't a photo or PDF we can read. Use JPEG, PNG, WebP or PDF."}
            ) from exc
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
