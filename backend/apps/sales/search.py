from __future__ import annotations

import re
from typing import Any

from django.db.models import Q

from apps.accounts.roles import PRICE_ROLES
from apps.core.api import flag_enabled
from apps.search.registry import SearchResult

from .models import Quote


def search_quotes(user: Any, query: str, limit: int) -> list[SearchResult]:
    """Quotes by number ("Q-30001", "30001") or their sale's number or invoice #.
    Admin and sales only: quotes carry prices."""
    if getattr(user, "role", None) not in PRICE_ROLES or not flag_enabled("sales", user):
        return []
    q = query.strip()
    digits = re.sub(r"\D", "", q)
    match = Q(number__iexact=q) | Q(sales__number__iexact=q) | Q(sales__invoice_number__iexact=q)
    if len(digits) >= 4:
        match |= Q(number__endswith=digits) | Q(sales__number__endswith=digits)
    quotes = (
        Quote.objects.filter(match).select_related("customer").distinct().order_by("-quote_date")
    )[:limit]
    return [
        SearchResult(
            kind="quote",
            id=str(x.pk),
            title=f"{x.number} · {x.customer.name}",
            subtitle=x.get_status_display(),
            url=f"/sales/{x.pk}",
        )
        for x in quotes
    ]
