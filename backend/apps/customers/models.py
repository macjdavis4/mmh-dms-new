from __future__ import annotations

from django.contrib.postgres.indexes import GinIndex
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower

from apps.core.models import SoftDeleteModel

ALIVE = Q(deleted_at__isnull=True)


class Customer(SoftDeleteModel):
    class Kind(models.TextChoices):
        BUSINESS = "business", "Business"
        INDIVIDUAL = "individual", "Individual"

    name = models.CharField(max_length=200)
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.BUSINESS)
    account_number = models.CharField(max_length=40, blank=True, default="")
    phone = models.CharField(max_length=40, blank=True, default="")
    email = models.EmailField(max_length=254, blank=True, default="")
    website = models.CharField(max_length=200, blank=True, default="")
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(condition=~Q(name=""), name="customer_name_not_blank"),
            models.CheckConstraint(
                condition=Q(kind__in=["business", "individual"]), name="customer_kind_valid"
            ),
            models.UniqueConstraint(
                Lower("account_number"),
                condition=ALIVE & ~Q(account_number=""),
                name="customer_account_number_unique",
            ),
        ]
        indexes = [
            # Fuzzy name matching (search now, import matching in Phase 3).
            GinIndex(fields=["name"], name="customer_name_trgm", opclasses=["gin_trgm_ops"]),
        ]

    def __str__(self) -> str:
        return self.name


class Contact(SoftDeleteModel):
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="contacts")
    first_name = models.CharField(max_length=80, blank=True, default="")
    last_name = models.CharField(max_length=80, blank=True, default="")
    title = models.CharField(max_length=100, blank=True, default="")
    phone = models.CharField(max_length=40, blank=True, default="")
    mobile = models.CharField(max_length=40, blank=True, default="")
    email = models.EmailField(max_length=254, blank=True, default="")
    is_primary = models.BooleanField(default=False)
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-is_primary", "last_name", "first_name"]
        constraints = [
            models.CheckConstraint(
                condition=~Q(first_name="") | ~Q(last_name=""), name="contact_has_a_name"
            ),
            models.UniqueConstraint(
                fields=["customer"],
                condition=ALIVE & Q(is_primary=True),
                name="contact_one_primary_per_customer",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


class Address(SoftDeleteModel):
    class Kind(models.TextChoices):
        BILLING = "billing", "Billing"
        SHIPPING = "shipping", "Shipping"
        SITE = "site", "Job site"
        OTHER = "other", "Other"

    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="addresses")
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.BILLING)
    label = models.CharField(max_length=100, blank=True, default="")
    line1 = models.CharField(max_length=200)
    line2 = models.CharField(max_length=200, blank=True, default="")
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=40, default="ME")
    postal_code = models.CharField(max_length=20, blank=True, default="")
    country = models.CharField(max_length=2, default="US")
    is_primary = models.BooleanField(default=False)
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-is_primary", "kind", "city"]
        verbose_name_plural = "addresses"
        constraints = [
            models.CheckConstraint(
                condition=Q(kind__in=["billing", "shipping", "site", "other"]),
                name="address_kind_valid",
            ),
            models.CheckConstraint(condition=~Q(line1=""), name="address_line1_not_blank"),
            models.CheckConstraint(condition=~Q(city=""), name="address_city_not_blank"),
            models.UniqueConstraint(
                fields=["customer"],
                condition=ALIVE & Q(is_primary=True),
                name="address_one_primary_per_customer",
            ),
        ]

    def __str__(self) -> str:
        return ", ".join(p for p in [self.line1, self.city, self.state] if p)
