from __future__ import annotations

from typing import Any

from django.db.models import Q

from apps.search.registry import SearchResult

from .models import Unit, normalize_serial


def every_word(query: str, fields: tuple[str, ...] = ("make", "model")) -> Q | None:
    """For multi-word queries like "hyundai 35": each word must appear in
    one of `fields`. None for single words (the plain match covers those)."""
    words = query.split()
    if len(words) < 2:
        return None
    match = Q()
    for word in words:
        any_field = Q()
        for field in fields:
            any_field |= Q(**{f"{field}__icontains": word})
        match &= any_field
    return match


def search_units(user: Any, query: str, limit: int) -> list[SearchResult]:
    """Any serial on the unit (unit, engine, battery, attachments...), stock
    number, or model. Serials match ignoring case, spaces and dashes."""
    norm = normalize_serial(query)
    match = Q(model__icontains=query) | Q(stock_number__iexact=query)
    if words := every_word(query):
        match |= words
    if len(norm) >= 3:
        match |= (
            Q(serial_normalized__contains=norm)
            | Q(components__serial_number__icontains=query, components__deleted_at__isnull=True)
            | Q(attachments__serial_number__icontains=query, attachments__deleted_at__isnull=True)
            | Q(battery_serial__icontains=query)
            | Q(charger_serial__icontains=query)
        )
    units = Unit.objects.filter(match).distinct().order_by("make", "model")[:limit]
    return [
        SearchResult(
            kind="unit",
            id=str(u.pk),
            title=" ".join(p for p in [u.make, u.model] if p) or "Unit",
            subtitle=" · ".join(
                p
                for p in [
                    u.serial_number and f"S/N {u.serial_number}",
                    u.stock_number and f"Stock {u.stock_number}",
                    u.get_stock_status_display() if u.stock_status else "",
                ]
                if p
            ),
            url=f"/units/{u.pk}",
        )
        for u in units
    ]
