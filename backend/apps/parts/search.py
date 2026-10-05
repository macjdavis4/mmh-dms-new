from __future__ import annotations

from typing import Any

from django.db.models import Q

from apps.core.api import flag_enabled
from apps.search.registry import SearchResult

from .models import Part, normalize_number


def search_parts(user: Any, query: str, limit: int) -> list[SearchResult]:
    """By part number, cross reference or vendor's number, ignoring dashes and
    spaces ("31n4-01050" finds 31N4-01050). Everyone can look parts up."""
    norm = normalize_number(query)
    if len(norm) < 3 or not flag_enabled("parts", user):
        return []
    parts = (
        Part.objects.filter(
            Q(number_normalized__contains=norm)
            | Q(
                cross_references__number_normalized__contains=norm,
                cross_references__deleted_at__isnull=True,
            )
            | Q(vendor_part_number__iexact=query.strip())
        )
        .select_related("bin", "superseded_by")
        .distinct()
        .order_by("number_normalized")[:limit]
    )
    results = []
    for part in parts:
        bits = [part.manufacturer, f"Bin {part.bin.code}" if part.bin else ""]
        if part.superseded_by:
            bits.append(f"Replaced by {part.superseded_by.part_number}")
        results.append(
            SearchResult(
                kind="part",
                id=str(part.pk),
                title=f"{part.part_number} · {part.description}",
                subtitle=" · ".join(b for b in bits if b),
                url=f"/parts/{part.pk}",
            )
        )
    return results
