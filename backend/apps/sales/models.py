"""Quotes and sales. A quote lists units from our stock and other items, and
any trade-ins. Recording the sale changes hands for every unit on it (sold
units go to the customer, trade-ins come into our stock) in one transaction,
and keeps the totals as they were on the day."""

from __future__ import annotations

from decimal import Decimal
from typing import ClassVar

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import connection, models
from django.db.models import F, Q
from django.utils import timezone

from apps.core.models import AuditedModel, SoftDeleteModel
from apps.customers.models import Customer
from apps.units.models import OwnershipRecord, Unit

ALIVE = Q(deleted_at__isnull=True)
MONEY = {"max_digits": 12, "decimal_places": 2}
QUOTE_SEQUENCE = "sales_quote_number_seq"
SALE_SEQUENCE = "sales_sale_number_seq"

DEFAULT_TERMS = (
    "Prices in US dollars. Quote valid until the date shown. Units are subject to prior sale. "
    "Trade-in allowances assume the trade-in is in the condition we inspected."
)


def _next(sequence: str, prefix: str) -> str:
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT nextval('{sequence}')")
        (value,) = cursor.fetchone()  # type: ignore[misc]
    return f"{prefix}-{value}"


def default_tax_rate() -> Decimal:
    return Decimal(str(settings.SALES_TAX_RATE))


class Quote(SoftDeleteModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SENT = "sent", "Sent"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"
        CANCELLED = "cancelled", "Cancelled"
        SOLD = "sold", "Sold"

    OPEN_STATUSES: ClassVar[tuple[str, ...]] = ("draft", "sent", "accepted")

    number = models.CharField(max_length=20, unique=True, editable=False)  # Q-30001
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="quotes")
    salesperson = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="quotes",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    quote_date = models.DateField(default=timezone.localdate)
    valid_until = models.DateField(null=True, blank=True)
    attention = models.CharField(max_length=120, blank=True, default="")  # who it's for
    customer_po = models.CharField(max_length=60, blank=True, default="")
    # Percent, e.g. 5.500. Exempt customers pay none (with their certificate #).
    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=3,
        default=default_tax_rate,
        validators=[MinValueValidator(0), MaxValueValidator(25)],
    )
    tax_exempt = models.BooleanField(default=False)
    tax_exempt_number = models.CharField(max_length=60, blank=True, default="")
    terms = models.TextField(blank=True, default=DEFAULT_TERMS)  # printed
    notes = models.TextField(blank=True, default="")  # internal, never printed
    sent_at = models.DateTimeField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-quote_date", "-number"]
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    status__in=["draft", "sent", "accepted", "declined", "cancelled", "sold"]
                ),
                name="quote_status_valid",
            ),
            models.CheckConstraint(
                condition=Q(valid_until__isnull=True) | Q(valid_until__gte=F("quote_date")),
                name="quote_valid_after_date",
            ),
            models.CheckConstraint(
                condition=Q(tax_rate__gte=0, tax_rate__lte=25), name="quote_tax_rate_sane"
            ),
        ]
        indexes = [models.Index(fields=["status", "-quote_date"], name="quote_status_idx")]

    def __str__(self) -> str:
        return f"{self.number} · {self.customer.name}" if self.customer_id else self.number

    def save(self, *args: object, **kwargs: object) -> None:
        if not self.number:
            self.number = _next(QUOTE_SEQUENCE, "Q")
        super().save(*args, **kwargs)  # type: ignore[arg-type]

    @property
    def is_open(self) -> bool:
        return self.status in self.OPEN_STATUSES

    @property
    def is_expired(self) -> bool:
        return (
            self.status in ("draft", "sent")
            and self.valid_until is not None
            and self.valid_until < timezone.localdate()
        )


class QuoteLine(SoftDeleteModel):
    """One thing on the quote: a unit from our stock, or an item with a price."""

    class Kind(models.TextChoices):
        UNIT = "unit", "Unit"
        ATTACHMENT = "attachment", "Attachment or option"
        DELIVERY = "delivery", "Delivery"
        SERVICE = "service", "Service or warranty"
        OTHER = "other", "Other"
        DISCOUNT = "discount", "Discount"

    quote = models.ForeignKey(Quote, on_delete=models.PROTECT, related_name="lines")
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.OTHER)
    unit = models.ForeignKey(
        Unit, null=True, blank=True, on_delete=models.PROTECT, related_name="quote_lines"
    )
    description = models.CharField(max_length=300, blank=True, default="")
    quantity = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("1"))
    unit_price = models.DecimalField(**MONEY)  # type: ignore[arg-type]
    taxable = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    kind__in=["unit", "attachment", "delivery", "service", "other", "discount"]
                ),
                name="quote_line_kind_valid",
            ),
            models.CheckConstraint(
                condition=Q(quantity__gt=0), name="quote_line_quantity_positive"
            ),
            # A unit line is exactly one unit; only unit lines point at a unit.
            models.CheckConstraint(
                condition=Q(kind="unit", unit__isnull=False, quantity=1)
                | (~Q(kind="unit") & Q(unit__isnull=True)),
                name="quote_line_unit_consistent",
            ),
            # Discounts take money off; everything else costs something or nothing.
            models.CheckConstraint(
                condition=Q(kind="discount", unit_price__lte=0)
                | (~Q(kind="discount") & Q(unit_price__gte=0)),
                name="quote_line_price_sign",
            ),
            models.CheckConstraint(
                condition=~Q(kind="unit") | Q(unit__isnull=False) | ~Q(description=""),
                name="quote_line_described",
            ),
            models.UniqueConstraint(
                fields=["quote", "unit"],
                condition=ALIVE & Q(unit__isnull=False),
                name="quote_line_unit_once",
            ),
        ]

    def __str__(self) -> str:
        return self.description or (str(self.unit) if self.unit_id else self.get_kind_display())

    @property
    def amount(self) -> Decimal:
        return (self.quantity * self.unit_price).quantize(Decimal("0.01"))


class TradeIn(SoftDeleteModel):
    """A unit the customer gives us as part of the deal. Either a unit we
    already know (by serial) or one described here; recording the sale adds
    a described one to our units."""

    quote = models.ForeignKey(Quote, on_delete=models.PROTECT, related_name="trade_ins")
    unit = models.ForeignKey(
        Unit, null=True, blank=True, on_delete=models.PROTECT, related_name="trade_ins"
    )
    make = models.CharField(max_length=60, blank=True, default="")
    model = models.CharField(max_length=80, blank=True, default="")
    serial_number = models.CharField(max_length=80, blank=True, default="")
    year = models.PositiveSmallIntegerField(null=True, blank=True)
    hours = models.DecimalField(
        max_digits=9, decimal_places=1, null=True, blank=True, validators=[MinValueValidator(0)]
    )
    description = models.CharField(max_length=300, blank=True, default="")  # condition etc.
    allowance = models.DecimalField(
        **MONEY,  # type: ignore[arg-type]
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    # Still owed to the customer's lender; we pay it off, so it adds to the deal.
    payoff = models.DecimalField(
        **MONEY,  # type: ignore[arg-type]
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    payoff_to = models.CharField(max_length=100, blank=True, default="")

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(unit__isnull=False) | ~Q(serial_number="") | ~Q(model=""),
                name="trade_in_identified",
            ),
            models.CheckConstraint(
                condition=Q(allowance__gte=0) & (Q(payoff__isnull=True) | Q(payoff__gte=0)),
                name="trade_in_money_not_negative",
            ),
            models.CheckConstraint(
                condition=Q(hours__isnull=True) | Q(hours__gte=0), name="trade_in_hours_sane"
            ),
            models.UniqueConstraint(
                fields=["quote", "unit"],
                condition=ALIVE & Q(unit__isnull=False),
                name="trade_in_unit_once",
            ),
        ]

    def __str__(self) -> str:
        if self.unit_id:
            return str(self.unit)
        return " ".join(x for x in [self.make, self.model, self.serial_number] if x)


class Sale(SoftDeleteModel):
    """A recorded sale. The totals are kept as they were on the day."""

    class Status(models.TextChoices):
        COMPLETED = "completed", "Completed"
        VOIDED = "voided", "Voided"

    number = models.CharField(max_length=20, unique=True, editable=False)  # S-40001
    # A voided sale keeps its quote; the quote can then be sold again.
    quote = models.ForeignKey(Quote, on_delete=models.PROTECT, related_name="sales")
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="sales")
    salesperson = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="sales",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.COMPLETED)
    sale_date = models.DateField(default=timezone.localdate)
    invoice_number = models.CharField(max_length=60, blank=True, default="")
    subtotal = models.DecimalField(**MONEY)  # type: ignore[arg-type]
    trade_allowance = models.DecimalField(**MONEY)  # type: ignore[arg-type]
    trade_payoff = models.DecimalField(**MONEY)  # type: ignore[arg-type]
    taxable_amount = models.DecimalField(**MONEY)  # type: ignore[arg-type]
    tax_rate = models.DecimalField(max_digits=5, decimal_places=3)
    tax = models.DecimalField(**MONEY)  # type: ignore[arg-type]
    total = models.DecimalField(**MONEY)  # type: ignore[arg-type]
    voided_at = models.DateTimeField(null=True, blank=True)
    void_reason = models.CharField(max_length=300, blank=True, default="")

    class Meta:
        ordering = ["-sale_date", "-number"]
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=["completed", "voided"]), name="sale_status_valid"
            ),
            models.CheckConstraint(
                condition=~Q(status="voided") | (Q(voided_at__isnull=False) & ~Q(void_reason="")),
                name="sale_voided_has_reason",
            ),
            models.UniqueConstraint(
                fields=["quote"],
                condition=ALIVE & Q(status="completed"),
                name="sale_one_completed_per_quote",
            ),
            models.CheckConstraint(
                condition=Q(trade_allowance__gte=0, trade_payoff__gte=0, tax__gte=0)
                & Q(taxable_amount__gte=0),
                name="sale_money_sane",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.number} · {self.customer.name}" if self.customer_id else self.number

    def save(self, *args: object, **kwargs: object) -> None:
        if not self.number:
            self.number = _next(SALE_SEQUENCE, "S")
        super().save(*args, **kwargs)  # type: ignore[arg-type]


class SaleUnitChange(AuditedModel):
    """Which ownership change a sale made, so voiding it can undo exactly those."""

    class Kind(models.TextChoices):
        SOLD = "sold", "Sold"
        TRADE_IN = "trade_in", "Trade-in"

    sale = models.ForeignKey(Sale, on_delete=models.PROTECT, related_name="unit_changes")
    ownership = models.OneToOneField(
        OwnershipRecord, on_delete=models.PROTECT, related_name="sale_change"
    )
    kind = models.CharField(max_length=10, choices=Kind.choices)
    # Set when the sale added the trade-in unit to our records.
    created_unit = models.BooleanField(default=False)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(kind__in=["sold", "trade_in"]), name="sale_change_kind_valid"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.sale.number}: {self.get_kind_display()}"
