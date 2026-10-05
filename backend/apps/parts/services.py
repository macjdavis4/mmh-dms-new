"""Multi-step part operations, each in one transaction."""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import CrossReference, Part, normalize_number


def check_supersession(part: Part, replacement: Part | None) -> None:
    """A part can't be replaced by itself, a removed part, or a part that is
    (eventually) replaced by it: the chain must end."""
    if replacement is None:
        return
    if part.pk is not None and replacement.pk == part.pk:
        raise ValidationError({"superseded_by": "A part can't replace itself."})
    if replacement.is_deleted:
        raise ValidationError({"superseded_by": "That part has been removed."})
    seen = {part.pk}
    step: Part | None = replacement
    while step is not None:
        if step.pk in seen:
            raise ValidationError(
                {
                    "superseded_by": f"{replacement.part_number} is already replaced by "
                    f"{part.part_number}. That would go round in a circle."
                }
            )
        seen.add(step.pk)
        step = step.superseded_by


def find_duplicate(manufacturer: str, number: str, exclude: Any = None) -> Part | None:
    qs = Part.all_objects.filter(
        manufacturer_normalized=normalize_number(manufacturer),
        number_normalized=normalize_number(number),
    )
    if exclude is not None:
        qs = qs.exclude(pk=exclude)
    return qs.first()


def _sync_cross_refs(part: Part, rows: list[dict[str, Any]] | None) -> None:
    if rows is None:
        return
    existing = {str(r.pk): r for r in CrossReference.objects.filter(part=part)}
    incoming = {str(r.get("id") or "") for r in rows}
    for row_id, obj in existing.items():
        if row_id not in incoming:
            obj.soft_delete()
    for row in rows:
        row = dict(row)
        obj = existing.get(str(row.pop("id", "") or "")) or CrossReference(part=part)
        for key, value in row.items():
            setattr(obj, key, value)
        obj.save()


@transaction.atomic
def save_part(part: Part, *, cross_references: list[dict[str, Any]] | None = None) -> Part:
    dup = find_duplicate(part.manufacturer, part.part_number, exclude=part.pk)
    if dup is not None:
        where = " (removed; restore it instead)" if dup.is_deleted else ""
        raise ValidationError(
            {
                "part_number": f"{dup.manufacturer} {dup.part_number} is already "
                f"in the catalog{where}."
            }
        )
    check_supersession(part, part.superseded_by)
    if part.superseded_by is None:
        part.superseded_on = None
    elif part.superseded_on is None:
        part.superseded_on = timezone.localdate()
    numbers = [normalize_number(r.get("part_number", "")) for r in cross_references or []]
    if len(numbers) != len(set(numbers)):
        raise ValidationError({"cross_references": "The same number is listed twice."})
    try:
        with transaction.atomic():
            part.save()
            _sync_cross_refs(part, cross_references)
    except IntegrityError as exc:
        if "part_number_unique" in str(exc):
            raise ValidationError({"part_number": "Another part already has this number."}) from exc
        raise
    return part
