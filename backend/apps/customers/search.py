from __future__ import annotations

from typing import Any

from django.contrib.postgres.search import TrigramSimilarity
from django.db.models import Q

from apps.search.registry import SearchResult

from .models import Customer


def search_customers(user: Any, query: str, limit: int) -> list[SearchResult]:
    """Name (typo-tolerant), account number, phone, or a contact's name/email."""
    q = query.strip()
    matches = (
        Customer.objects.annotate(similarity=TrigramSimilarity("name", q))
        .filter(
            Q(name__icontains=q)
            | Q(similarity__gt=0.3)
            | Q(account_number__iexact=q)
            | Q(phone__icontains=q)
            | Q(contacts__last_name__icontains=q, contacts__deleted_at__isnull=True)
            | Q(contacts__email__icontains=q, contacts__deleted_at__isnull=True)
        )
        .distinct()
        .order_by("-similarity", "name")[:limit]
    )
    return [
        SearchResult(
            kind="customer",
            id=str(c.pk),
            title=c.name,
            subtitle=" · ".join(
                p for p in [c.account_number and f"Acct {c.account_number}", c.phone] if p
            )
            or "Customer",
            url=f"/customers/{c.pk}",
        )
        for c in matches
    ]
