from __future__ import annotations

import re
from typing import Any

from django.db.models import Q

from apps.search.registry import SearchResult

from .models import WorkOrder


def search_work_orders(user: Any, query: str, limit: int) -> list[SearchResult]:
    """By number ("WO-20001", "20001") or the unit's serial."""
    digits = re.sub(r"\D", "", query)
    match = Q(number__iexact=query.strip())
    if digits:
        match |= Q(number__endswith=digits)
    match |= Q(unit__serial_number__iexact=query.strip())
    orders = (
        WorkOrder.objects.filter(match)
        .select_related("unit", "customer")
        .order_by("-opened_on")[:limit]
    )
    return [
        SearchResult(
            kind="work_order",
            id=str(w.pk),
            title=f"{w.number} · {' '.join(p for p in [w.unit.make, w.unit.model] if p) or 'Unit'}",
            subtitle=" · ".join(
                p
                for p in [w.get_status_display(), w.customer.name if w.customer else "Our stock"]
                if p
            ),
            url=f"/service/{w.pk}",
        )
        for w in orders
    ]
