"""Roles from CLAUDE.md. Permissions are enforced server side on every endpoint."""

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
