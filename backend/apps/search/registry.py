"""Global search registry.

Each feature app registers a provider in its AppConfig.ready(), e.g. customers
by name/phone, units by serial, work orders by number, parts by part number.
Providers must apply the caller's role permissions themselves.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class SearchResult:
    kind: str  # "customer" | "unit" | "work_order" | "part"
    id: str
    title: str
    subtitle: str
    url: str  # client-side route, e.g. /units/<id>

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


Provider = Callable[[Any, str, int], list[SearchResult]]

_providers: dict[str, Provider] = {}


def register(kind: str, provider: Provider) -> None:
    _providers[kind] = provider


def search(user: Any, query: str, limit: int = 8) -> dict[str, list[dict[str, Any]]]:
    return {
        kind: [r.as_dict() for r in provider(user, query, limit)]
        for kind, provider in _providers.items()
    }


def registered_kinds() -> list[str]:
    return sorted(_providers)
