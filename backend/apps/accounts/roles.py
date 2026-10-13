"""Roles from CLAUDE.md. Permissions are enforced server side on every endpoint."""

from collections.abc import Iterable
from typing import Any

from django.db import models


class Role(models.TextChoices):
    ADMIN = "admin", "Admin"
    SALES = "sales", "Sales"
    SERVICE = "service", "Service"
    PARTS = "parts", "Parts"
    READ_ONLY = "read_only", "Read only"


ALL_ROLES = frozenset(Role.values)

# Cost, asking price and sale price are visible to these roles only.
PRICE_ROLES = frozenset({Role.ADMIN, Role.SALES})

# Roles that must use two-factor authentication.
TWO_FACTOR_REQUIRED_ROLES = frozenset({Role.ADMIN})


# --- People can hold several roles --------------------------------------------
#
# Admin and read-only stand alone. Sales, service and parts can be held in any
# non-empty combination (e.g. sales + parts, or all three).

# Canonical order, used whenever roles are stored or shown.
ROLE_ORDER = (Role.ADMIN, Role.SALES, Role.SERVICE, Role.PARTS, Role.READ_ONLY)
EXCLUSIVE_ROLES = frozenset({Role.ADMIN, Role.READ_ONLY})
COMBINABLE_ROLES = frozenset({Role.SALES, Role.SERVICE, Role.PARTS})


def normalize_roles(roles: Iterable[str] | None) -> list[str]:
    """Remove duplicates and put known roles in canonical order. Unknown values
    are kept (at the end) so the database check can refuse them."""
    given = list(dict.fromkeys(roles or []))
    known = [r.value for r in ROLE_ORDER if r.value in given]
    return known + [r for r in given if r not in ALL_ROLES]


def roles_problem(roles: Iterable[str] | None) -> str | None:
    """Plain-language reason these roles are not allowed, or None if they are."""
    given = normalize_roles(roles)
    if not given:
        return "Choose at least one role."
    unknown = [r for r in given if r not in ALL_ROLES]
    if unknown:
        return f"Unknown role: {unknown[0]}."
    exclusive = [r for r in given if r in EXCLUSIVE_ROLES]
    if exclusive and len(given) > 1:
        label = Role(exclusive[0]).label
        return f"{label} cannot be combined with any other role."
    return None


def primary_role(roles: Iterable[str] | None) -> str:
    """The single role kept in the legacy `role` column: the first by priority."""
    given = normalize_roles(roles)
    return given[0] if given else Role.READ_ONLY.value


def role_labels(roles: Iterable[str] | None) -> str:
    labels = []
    for r in normalize_roles(roles):
        labels.append(Role(r).label if r in ALL_ROLES else r)
    return ", ".join(labels)


def user_roles(user: Any) -> list[str]:
    """The roles of any user-like object (a real user, or one with only `role`)."""
    roles = getattr(user, "effective_roles", None)
    if roles is None:
        single = getattr(user, "role", None)
        return [single] if single else []
    return list(roles)


def has_any_role(user: Any, allowed: Iterable[str]) -> bool:
    """True when ANY of the user's roles is in `allowed`."""
    return not set(user_roles(user)).isdisjoint(allowed)
