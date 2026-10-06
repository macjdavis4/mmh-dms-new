"""Parts catalog: part numbers, bins, reorder points, supersessions and
cross references. Quantities come later from the stock ledger (Phase 10);
nothing here stores an on-hand count.

Part numbers are kept exactly as written. A normalized copy (no case,
spaces or punctuation) finds duplicates and matches searches, so
"HY-31N4-01050" and "31n401050" are the same part."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import ClassVar

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.db.models.functions import Upper
from django.utils import timezone

from apps.core.models import AuditedModel, SoftDeleteModel

ALIVE = Q(deleted_at__isnull=True)
MONEY = {"max_digits": 12, "decimal_places": 2, "null": True, "blank": True}
QTY = {"max_digits": 10, "decimal_places": 2, "null": True, "blank": True}


def normalize_number(value: str) -> str:
    """'hy-31N4 01050' -> 'HY31N401050'."""
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


class Bin(SoftDeleteModel):
    """A shelf location in the parts room, e.g. "A-03-2"."""

    code = models.CharField(max_length=30)
    description = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        ordering = ["code"]
        constraints = [
            models.CheckConstraint(condition=~Q(code=""), name="bin_code_not_blank"),
            models.UniqueConstraint(Upper("code"), condition=ALIVE, name="bin_code_unique"),
        ]

    def __str__(self) -> str:
        return self.code


class Part(SoftDeleteModel):
    class Category(models.TextChoices):
        FILTERS = "filters", "Filters"
        ENGINE = "engine", "Engine and fuel"
        HYDRAULICS = "hydraulics", "Hydraulics"
        BRAKES = "brakes", "Brakes"
        ELECTRICAL = "electrical", "Electrical"
        MAST = "mast", "Mast, chains and forks"
        TIRES = "tires", "Tires and wheels"
        DRIVETRAIN = "drivetrain", "Transmission and drivetrain"
        STEERING = "steering", "Steering"
        SAFETY = "safety", "Lights and safety"
        ATTACHMENTS = "attachments", "Attachments"
        FLUIDS = "fluids", "Fluids and shop supplies"
        OTHER = "other", "Other"

    class UnitOfMeasure(models.TextChoices):
        EACH = "each", "Each"
        PAIR = "pair", "Pair"
        SET = "set", "Set"
        KIT = "kit", "Kit"
        BOX = "box", "Box"
        FOOT = "foot", "Foot"
        QUART = "quart", "Quart"
        GALLON = "gallon", "Gallon"

    manufacturer = models.CharField(max_length=60, blank=True, default="")  # e.g. Hyundai
    part_number = models.CharField(max_length=60)  # as written
    number_normalized = models.CharField(max_length=60, editable=False)
    manufacturer_normalized = models.CharField(
        max_length=60, blank=True, default="", editable=False
    )
    description = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.OTHER)
    unit_of_measure = models.CharField(
        max_length=10, choices=UnitOfMeasure.choices, default=UnitOfMeasure.EACH
    )
    # Our cost: admin, sales and parts only. List price: everyone.
    cost = models.DecimalField(**MONEY, validators=[MinValueValidator(Decimal("0"))])  # type: ignore[arg-type]
    list_price = models.DecimalField(**MONEY, validators=[MinValueValidator(Decimal("0"))])  # type: ignore[arg-type]
    bin = models.ForeignKey(
        Bin, null=True, blank=True, on_delete=models.PROTECT, related_name="parts"
    )
    # Reorder when on hand falls to the point; order this many.
    reorder_point = models.DecimalField(**QTY, validators=[MinValueValidator(Decimal("0"))])  # type: ignore[arg-type]
    reorder_quantity = models.DecimalField(**QTY, validators=[MinValueValidator(Decimal("0"))])  # type: ignore[arg-type]
    vendor = models.CharField(max_length=100, blank=True, default="")  # who we buy it from
    vendor_part_number = models.CharField(max_length=60, blank=True, default="")
    fits = models.CharField(max_length=300, blank=True, default="")  # e.g. "35LN-9A, 30L-9A"
    notes = models.TextField(blank=True, default="")
    # Replaced by a newer part number. Follow the chain to the current part.
    superseded_by = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="supersedes"
    )
    superseded_on = models.DateField(null=True, blank=True)

    COST_FIELDS: ClassVar[tuple[str, ...]] = ("cost",)

    class Meta:
        ordering = ["manufacturer", "part_number"]
        constraints = [
            models.CheckConstraint(condition=~Q(number_normalized=""), name="part_number_given"),
            models.CheckConstraint(condition=~Q(description=""), name="part_described"),
            # One record per manufacturer + number, removed ones included:
            # a removed part is restored, never re-created.
            models.UniqueConstraint(
                fields=["manufacturer_normalized", "number_normalized"],
                name="part_number_unique",
            ),
            models.CheckConstraint(
                condition=Q(
                    category__in=[
                        "filters",
                        "engine",
                        "hydraulics",
                        "brakes",
                        "electrical",
                        "mast",
                        "tires",
                        "drivetrain",
                        "steering",
                        "safety",
                        "attachments",
                        "fluids",
                        "other",
                    ]
                ),
                name="part_category_valid",
            ),
            models.CheckConstraint(
                condition=Q(
                    unit_of_measure__in=[
                        "each",
                        "pair",
                        "set",
                        "kit",
                        "box",
                        "foot",
                        "quart",
                        "gallon",
                    ]
                ),
                name="part_unit_valid",
            ),
            models.CheckConstraint(
                condition=(Q(cost__isnull=True) | Q(cost__gte=0))
                & (Q(list_price__isnull=True) | Q(list_price__gte=0)),
                name="part_money_not_negative",
            ),
            models.CheckConstraint(
                condition=(Q(reorder_point__isnull=True) | Q(reorder_point__gte=0))
                & (Q(reorder_quantity__isnull=True) | Q(reorder_quantity__gt=0)),
                name="part_reorder_sane",
            ),
            models.CheckConstraint(
                condition=Q(superseded_by__isnull=True) | ~Q(superseded_by=F("id")),
                name="part_not_superseded_by_itself",
            ),
        ]
        indexes = [
            models.Index(fields=["number_normalized"], name="part_number_idx"),
            models.Index(fields=["category"], name="part_category_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.part_number} · {self.description}"

    def save(self, *args: object, **kwargs: object) -> None:
        self.number_normalized = normalize_number(self.part_number)
        self.manufacturer_normalized = normalize_number(self.manufacturer)
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = {
                *update_fields,  # type: ignore[misc]
                "number_normalized",
                "manufacturer_normalized",
            }
        super().save(*args, **kwargs)  # type: ignore[arg-type]

    def current(self, limit: int = 20) -> Part:
        """The part that replaces this one now (itself if not superseded)."""
        part: Part = self
        for _ in range(limit):
            nxt = part.superseded_by
            if nxt is None or nxt.is_deleted:
                return part
            part = nxt
        return part


class CrossReference(SoftDeleteModel):
    """Another brand's number for the same part, e.g. Donaldson P550084."""

    part = models.ForeignKey(Part, on_delete=models.PROTECT, related_name="cross_references")
    manufacturer = models.CharField(max_length=60, blank=True, default="")
    part_number = models.CharField(max_length=60)
    number_normalized = models.CharField(max_length=60, editable=False)
    note = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        ordering = ["manufacturer", "part_number"]
        constraints = [
            models.CheckConstraint(
                condition=~Q(number_normalized=""), name="cross_ref_number_given"
            ),
            models.UniqueConstraint(
                fields=["part", "number_normalized"], condition=ALIVE, name="cross_ref_once"
            ),
        ]
        indexes = [models.Index(fields=["number_normalized"], name="cross_ref_number_idx")]

    def __str__(self) -> str:
        return " ".join(x for x in [self.manufacturer, self.part_number] if x)

    def save(self, *args: object, **kwargs: object) -> None:
        self.number_normalized = normalize_number(self.part_number)
        super().save(*args, **kwargs)  # type: ignore[arg-type]


# --- Stock (Phase 10) ------------------------------------------------------------------------


class StockMovement(AuditedModel):
    """One line in the append-only stock ledger. On hand is the sum of a
    part's movements; nothing is ever edited or deleted (a mistake is put
    right with a reversing movement)."""

    class Kind(models.TextChoices):
        OPENING = "opening", "Opening count"
        RECEIVE = "receive", "Received"
        ISSUE = "issue", "Used on a work order"
        RETURN = "return", "Returned from a work order"
        ADJUST = "adjust", "Count adjustment"
        REVERSAL = "reversal", "Reversal"

    part = models.ForeignKey(Part, on_delete=models.PROTECT, related_name="movements")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    # Into stock is positive, out of stock negative.
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    occurred_at = models.DateTimeField(default=timezone.now)
    work_order = models.ForeignKey(
        "service.WorkOrder",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="part_movements",
    )
    # What one cost us, and (on a work order) what we charge for one.
    unit_cost = models.DecimalField(**MONEY, validators=[MinValueValidator(Decimal("0"))])  # type: ignore[arg-type]
    unit_price = models.DecimalField(**MONEY, validators=[MinValueValidator(Decimal("0"))])  # type: ignore[arg-type]
    reference = models.CharField(max_length=60, blank=True, default="")  # invoice #, count sheet
    note = models.CharField(max_length=200, blank=True, default="")
    reverses = models.OneToOneField(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="reversed_by"
    )
    # On hand after this movement, for the history list.
    balance_after = models.DecimalField(max_digits=12, decimal_places=2)

    COST_FIELDS: ClassVar[tuple[str, ...]] = ("unit_cost",)

    class Meta:
        ordering = ["-occurred_at", "-created_at"]
        constraints = [
            models.CheckConstraint(condition=~Q(quantity=0), name="movement_not_zero"),
            models.CheckConstraint(
                condition=Q(
                    kind__in=["opening", "receive", "issue", "return", "adjust", "reversal"]
                ),
                name="movement_kind_valid",
            ),
            # Which way each kind moves stock, and what it must point at.
            models.CheckConstraint(
                condition=Q(kind__in=["opening", "receive"], quantity__gt=0)
                | Q(kind="issue", quantity__lt=0, work_order__isnull=False)
                | Q(kind="return", quantity__gt=0, work_order__isnull=False)
                | Q(kind="adjust")
                | Q(kind="reversal", reverses__isnull=False),
                name="movement_kind_fits",
            ),
            models.CheckConstraint(
                condition=Q(work_order__isnull=True) | Q(kind__in=["issue", "return", "reversal"]),
                name="movement_work_order_only_when_used",
            ),
            models.CheckConstraint(
                condition=Q(balance_after__gte=0), name="movement_balance_not_negative"
            ),
            models.CheckConstraint(
                condition=(Q(unit_cost__isnull=True) | Q(unit_cost__gte=0))
                & (Q(unit_price__isnull=True) | Q(unit_price__gte=0)),
                name="movement_money_not_negative",
            ),
        ]
        indexes = [
            models.Index(fields=["part", "-occurred_at"], name="movement_part_idx"),
            models.Index(fields=["work_order"], name="movement_work_order_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} {self.quantity} x {self.part.part_number}"


class PartStock(models.Model):
    """How many of a part we have, kept in step with the ledger in the same
    transaction as each movement. The nightly check recomputes it from the
    ledger and alerts if they ever differ."""

    part = models.OneToOneField(
        Part, primary_key=True, on_delete=models.PROTECT, related_name="stock"
    )
    on_hand = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(on_hand__gte=0), name="stock_not_negative"),
        ]

    def __str__(self) -> str:
        return f"{self.part.part_number}: {self.on_hand}"


class StockCheck(models.Model):
    """One run of the nightly ledger check."""

    id = models.BigAutoField(primary_key=True)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    parts_checked = models.PositiveIntegerField(default=0)
    # [{part, part_number, ledger, stored}] for every part that differed.
    drift = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self) -> str:
        return f"Stock check {self.started_at:%Y-%m-%d}: {len(self.drift)} differences"

    @property
    def ok(self) -> bool:
        return self.finished_at is not None and not self.drift
