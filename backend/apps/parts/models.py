"""Parts catalog: part numbers, bins, reorder points, supersessions and
cross references. Quantities come later from the stock ledger (Phase 10);
nothing here stores an on-hand count.

Part numbers are kept exactly as written. A normalized copy (no case,
spaces or punctuation) finds duplicates and matches searches, so
"HY-31N4-01050" and "31n401050" are the same part."""

from __future__ import annotations

import re
import uuid
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
    # The supplier invoice line a receipt (or its reversal) came in on.
    invoice_line = models.ForeignKey(
        "InvoiceLine",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="movements",
        db_index=False,  # few rows per line; a later migration can add one concurrently
    )

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
                condition=Q(invoice_line__isnull=True) | Q(kind__in=["receive", "reversal"]),
                name="movement_invoice_only_on_receipts",
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


# --- Supplier invoices (Phase 11) ---------------------------------------------------------


def invoice_file_path(instance: Invoice, filename: str) -> str:
    ext = (filename.rsplit(".", 1)[-1] if "." in filename else "bin").lower()[:5]
    return f"parts-invoices/{timezone.now():%Y/%m}/{uuid.uuid4().hex}.{ext}"


class Invoice(SoftDeleteModel):
    """A supplier's invoice or packing slip for parts. The file is read on
    the server (PDF text, or Tesseract for scans and photos) into suggested
    lines; a person checks them, then receives what arrived into stock."""

    class Status(models.TextChoices):
        READING = "reading", "Reading"
        REVIEW = "review", "To check"
        PARTIAL = "partial", "Partly received"
        RECEIVED = "received", "Received"
        CANCELLED = "cancelled", "Cancelled"

    supplier = models.CharField(max_length=120, blank=True, default="")
    invoice_number = models.CharField(max_length=60, blank=True, default="")
    invoice_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REVIEW)
    file = models.FileField(upload_to=invoice_file_path, max_length=300, blank=True, default="")
    original_name = models.CharField(max_length=255, blank=True, default="")
    content_type = models.CharField(max_length=100, blank=True, default="")
    size_bytes = models.PositiveBigIntegerField(null=True, blank=True)
    # What the reader found, kept as read; the lines below are its suggestions.
    extracted_text = models.TextField(blank=True, default="")
    read_method = models.CharField(max_length=20, blank=True, default="")  # pdf-text / ocr
    read_error = models.CharField(max_length=300, blank=True, default="")
    read_at = models.DateTimeField(null=True, blank=True)
    # Totals as printed on the invoice, to check the lines against.
    freight = models.DecimalField(**MONEY, validators=[MinValueValidator(Decimal("0"))])  # type: ignore[arg-type]
    tax = models.DecimalField(**MONEY, validators=[MinValueValidator(Decimal("0"))])  # type: ignore[arg-type]
    total = models.DecimalField(**MONEY, validators=[MinValueValidator(Decimal("0"))])  # type: ignore[arg-type]
    note = models.TextField(blank=True, default="")
    cancel_reason = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=["reading", "review", "partial", "received", "cancelled"]),
                name="invoice_status_valid",
            ),
            # The same supplier invoice can't be entered twice (and received twice).
            models.UniqueConstraint(
                Upper("supplier"),
                Upper("invoice_number"),
                condition=ALIVE & ~Q(invoice_number="") & ~Q(status="cancelled"),
                name="invoice_unique_per_supplier",
            ),
            models.CheckConstraint(
                condition=(Q(freight__isnull=True) | Q(freight__gte=0))
                & (Q(tax__isnull=True) | Q(tax__gte=0))
                & (Q(total__isnull=True) | Q(total__gte=0)),
                name="invoice_money_not_negative",
            ),
            models.CheckConstraint(
                condition=~Q(status="cancelled") | ~Q(cancel_reason=""),
                name="invoice_cancel_has_reason",
            ),
        ]

    def __str__(self) -> str:
        label = " ".join(x for x in (self.supplier, self.invoice_number) if x)
        return label or f"Invoice uploaded {self.created_at:%Y-%m-%d}"


class InvoiceLine(SoftDeleteModel):
    """One line of a supplier invoice. Shipped is what this invoice says is
    in the box; backordered is what the supplier says comes later. What has
    actually been received is the sum of the stock movements on the line."""

    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="lines")
    position = models.PositiveIntegerField(default=0)
    # The line exactly as read from the file (blank when typed in).
    raw_text = models.CharField(max_length=500, blank=True, default="")
    part = models.ForeignKey(
        Part, null=True, blank=True, on_delete=models.PROTECT, related_name="invoice_lines"
    )
    # As printed on the invoice; may be the supplier's own number.
    part_number = models.CharField(max_length=60, blank=True, default="")
    description = models.CharField(max_length=200, blank=True, default="")
    quantity_shipped = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    quantity_backordered = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0")
    )
    unit_cost = models.DecimalField(**MONEY, validators=[MinValueValidator(Decimal("0"))])  # type: ignore[arg-type]
    # Freight, core charges, fees: on the invoice but not stock.
    not_stocked = models.BooleanField(default=False)
    # Why the reader wasn't sure (quantity x price doesn't match, part unknown...).
    check_reason = models.CharField(max_length=200, blank=True, default="")
    # The rest won't come (supplier cancelled the backorder).
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_reason = models.CharField(max_length=200, blank=True, default="")

    COST_FIELDS: ClassVar[tuple[str, ...]] = ("unit_cost",)

    class Meta:
        ordering = ["position", "created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity_shipped__gte=0) & Q(quantity_backordered__gte=0),
                name="invoice_line_quantities_not_negative",
            ),
            models.CheckConstraint(
                condition=Q(not_stocked=True)
                | Q(quantity_shipped__gt=0)
                | Q(quantity_backordered__gt=0),
                name="invoice_line_has_quantity",
            ),
            models.CheckConstraint(
                condition=Q(unit_cost__isnull=True) | Q(unit_cost__gte=0),
                name="invoice_line_cost_not_negative",
            ),
            models.CheckConstraint(
                condition=Q(closed_at__isnull=True) | ~Q(closed_reason=""),
                name="invoice_line_closed_has_reason",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.invoice}: {self.part_number or self.description}"
