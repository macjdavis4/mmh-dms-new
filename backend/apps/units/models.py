"""Forklift units: everything on the paper "Eagle 1-84" unit card, plus stock,
pricing, photos, hour-meter readings and ownership history.

Values typed or imported from a card are stored exactly as written. A
separate parsed field is filled only when the value parses cleanly
(e.g. fork "1.75 x 4 x 48 STD" -> thickness/width/length).
"""

from __future__ import annotations

import re
import uuid
from decimal import Decimal
from typing import ClassVar

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from apps.core.models import SoftDeleteModel
from apps.customers.models import Customer

ALIVE = Q(deleted_at__isnull=True)
MONEY = {"max_digits": 12, "decimal_places": 2, "null": True, "blank": True}


def normalize_serial(value: str) -> str:
    """Serials compare without case, spaces or punctuation: 'ab-123 4' == 'AB1234'."""
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


def text(max_length: int = 100) -> models.CharField:  # type: ignore[type-arg]
    return models.CharField(max_length=max_length, blank=True, default="")


class Condition(models.TextChoices):
    NEW = "new", "New"
    USED = "used", "Used"


class StockStatus(models.TextChoices):
    """Blank means the unit isn't our inventory (for example a customer's
    truck we only service)."""

    AVAILABLE = "available", "Available"
    ON_HOLD = "on_hold", "On hold"
    IN_PREP = "in_prep", "In prep"
    SOLD = "sold", "Sold"


IN_STOCK = (StockStatus.AVAILABLE, StockStatus.ON_HOLD, StockStatus.IN_PREP)


class FuelType(models.TextChoices):
    LPG = "lpg", "LPG"
    GASOLINE = "gasoline", "Gasoline"
    DIESEL = "diesel", "Diesel"
    DUAL = "dual", "Dual fuel (LPG/gas)"
    ELECTRIC = "electric", "Electric"
    OTHER = "other", "Other"


class Unit(SoftDeleteModel):
    # --- The unit itself (make / model / serial) ---------------------------------
    make = text(60)
    model = text(80)
    serial_number = text(80)
    # Normalized copy for duplicate detection. Unique across ALL rows, removed
    # ones included: a removed unit is restored, never re-created.
    serial_normalized = models.CharField(max_length=80, blank=True, default="", editable=False)
    year = models.PositiveSmallIntegerField(null=True, blank=True)
    stock_number = text(40)

    # --- Card header -------------------------------------------------------------------
    card_date = models.DateField(null=True, blank=True)
    card_customer_name = text(200)  # as written on the card
    mechanic = text(100)  # as written on the card
    work_order_number = text(40)
    condition = models.CharField(max_length=10, choices=Condition.choices, default=Condition.USED)

    # --- Specs used for inventory filters ----------------------------------------------
    fuel_type = models.CharField(max_length=20, choices=FuelType.choices, blank=True, default="")
    capacity_lbs = models.PositiveIntegerField(null=True, blank=True)

    # --- Mast -------------------------------------------------------------------------
    mast_make = text(60)
    mast_type = text(60)
    mast_size = text(60)
    mast_lift_height_in = models.PositiveIntegerField(
        null=True, blank=True, help_text="Maximum fork height, inches"
    )
    mast_lowered_height_in = models.PositiveIntegerField(null=True, blank=True)
    lift_cylinder_number = text(100)

    # --- Carriage, backrest, tilt ----------------------------------------------------------
    carriage = text(100)
    backrest_height = text(40)
    backrest_width = text(40)
    tilt_forward_deg = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    tilt_back_deg = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    tilt_reference = text(60)

    # --- Tires -----------------------------------------------------------------------
    tire_type = text(40)  # e.g. solid, pneumatic, cushion
    tire_drive_size = text(40)
    tire_steer_size = text(40)
    tire_notes = text(200)  # free text extras, e.g. rim size

    # --- Electrics: battery and charger -----------------------------------------------------
    battery_make = text(60)
    battery_model = text(60)
    battery_serial = text(60)
    battery_volts = models.PositiveSmallIntegerField(null=True, blank=True)
    battery_amp_hours = models.PositiveIntegerField(null=True, blank=True)
    battery_size = text(60)  # W x L x H as written
    battery_weight_lbs = models.PositiveIntegerField(null=True, blank=True)
    charger_make = text(60)
    charger_model = text(60)
    charger_serial = text(60)

    # --- Free text from the card -----------------------------------------------------------
    special_equipment = models.TextField(blank=True, default="")
    field_modifications = models.TextField(blank=True, default="")
    notes = models.TextField(blank=True, default="")

    # --- Stock and money (cost and prices: admin and sales only) ---------------------------------
    stock_status = models.CharField(
        max_length=20, choices=StockStatus.choices, blank=True, default=""
    )
    cost = models.DecimalField(**MONEY, validators=[MinValueValidator(Decimal("0"))])  # type: ignore[arg-type]
    asking_price = models.DecimalField(**MONEY, validators=[MinValueValidator(Decimal("0"))])  # type: ignore[arg-type]
    sale_price = models.DecimalField(**MONEY, validators=[MinValueValidator(Decimal("0"))])  # type: ignore[arg-type]

    # --- Data quality ---------------------------------------------------------------------
    needs_review = models.BooleanField(default=False)
    review_note = text(300)

    PRICE_FIELDS: ClassVar[tuple[str, ...]] = ("cost", "asking_price", "sale_price")

    class Meta:
        ordering = ["make", "model", "serial_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["serial_normalized"],
                condition=~Q(serial_normalized=""),
                name="unit_serial_unique",
            ),
            models.UniqueConstraint(
                fields=["stock_number"],
                condition=ALIVE & ~Q(stock_number=""),
                name="unit_stock_number_unique",
            ),
            models.CheckConstraint(
                condition=Q(condition__in=["new", "used"]), name="unit_condition_valid"
            ),
            models.CheckConstraint(
                condition=Q(stock_status__in=["", "available", "on_hold", "in_prep", "sold"]),
                name="unit_stock_status_valid",
            ),
            models.CheckConstraint(
                condition=Q(
                    fuel_type__in=["", "lpg", "gasoline", "diesel", "dual", "electric", "other"]
                ),
                name="unit_fuel_type_valid",
            ),
            models.CheckConstraint(
                condition=(Q(cost__isnull=True) | Q(cost__gte=0))
                & (Q(asking_price__isnull=True) | Q(asking_price__gte=0))
                & (Q(sale_price__isnull=True) | Q(sale_price__gte=0)),
                name="unit_money_not_negative",
            ),
            models.CheckConstraint(
                condition=Q(year__isnull=True) | Q(year__gte=1940, year__lte=2100),
                name="unit_year_sane",
            ),
            # A unit must be identifiable by at least a serial, model or stock number.
            models.CheckConstraint(
                condition=~Q(serial_number="") | ~Q(model="") | ~Q(stock_number=""),
                name="unit_identifiable",
            ),
        ]
        indexes = [
            models.Index(fields=["stock_status", "condition"], name="unit_stock_idx"),
            models.Index(fields=["make", "model"], name="unit_make_model_idx"),
            models.Index(
                fields=["needs_review"], name="unit_review_idx", condition=Q(needs_review=True)
            ),
        ]

    def __str__(self) -> str:
        title = " ".join(p for p in [self.make, self.model] if p) or "Unit"
        return f"{title} · {self.serial_number}" if self.serial_number else title

    def save(self, *args: object, **kwargs: object) -> None:
        self.serial_normalized = normalize_serial(self.serial_number)
        update_fields = kwargs.get("update_fields")
        if update_fields is not None and "serial_number" in update_fields:  # type: ignore[operator]
            kwargs["update_fields"] = {*update_fields, "serial_normalized"}  # type: ignore[misc]
        super().save(*args, **kwargs)  # type: ignore[arg-type]

    @property
    def in_stock(self) -> bool:
        return self.stock_status in IN_STOCK


class UnitComponent(SoftDeleteModel):
    """Make / model / serial of each major component from the card."""

    class Kind(models.TextChoices):
        ENGINE = "engine", "Engine"
        ALTERNATOR = "alternator", "Generator / alternator"
        CONTROLLER = "controller", "Electrical controller"
        IGNITION = "ignition", "Ignition system"
        FUEL_SYSTEM = "fuel_system", "Fuel system"
        HYDRAULIC_PUMP = "hydraulic_pump", "Hydraulic pump"
        CONTROL_VALVE = "control_valve", "Control valve"
        TRANSMISSION = "transmission", "Transmission"

    class Spools(models.TextChoices):
        TWO = "2SP", "2 spool"
        THREE = "3SP", "3 spool"
        FOUR = "4SP", "4 spool"

    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name="components")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    make = text(60)
    model = text(80)
    serial_number = text(80)
    spools = models.CharField(max_length=3, choices=Spools.choices, blank=True, default="")

    ORDER: ClassVar[list[str]] = [k.value for k in Kind]

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["unit", "kind"], condition=ALIVE, name="component_one_per_kind"
            ),
            models.CheckConstraint(
                condition=Q(
                    kind__in=[
                        "engine",
                        "alternator",
                        "controller",
                        "ignition",
                        "fuel_system",
                        "hydraulic_pump",
                        "control_valve",
                        "transmission",
                    ]
                ),
                name="component_kind_valid",
            ),
            # Spools only describe a control valve.
            models.CheckConstraint(
                condition=Q(spools="") | Q(kind="control_valve", spools__in=["2SP", "3SP", "4SP"]),
                name="component_spools_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_kind_display()}: {self.make} {self.model}".strip()


# "1.75 x 4 x 48", also with "X" or the multiplication sign (U+00D7).
FORK_RE = re.compile(
    r"^\s*(?P<t>\d+(?:\.\d+)?)\s*[xX\u00d7]\s*(?P<w>\d+(?:\.\d+)?)\s*[xX\u00d7]\s*(?P<l>\d+(?:\.\d+)?)\b"
)


def parse_fork(dimensions: str) -> tuple[Decimal, Decimal, Decimal] | None:
    """'1.75 x 4 x 48 STD' -> (1.75, 4, 48) inches. None if it doesn't parse cleanly."""
    m = FORK_RE.match(dimensions or "")
    if not m:
        return None
    return Decimal(m["t"]), Decimal(m["w"]), Decimal(m["l"])


class UnitFork(SoftDeleteModel):
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name="forks")
    dimensions = models.CharField(max_length=80)  # as written, e.g. "1.75 x 4 x 48 STD"
    quantity = models.PositiveSmallIntegerField(default=2)
    # Filled only when `dimensions` parses cleanly.
    thickness_in = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True, editable=False
    )
    width_in = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True, editable=False
    )
    length_in = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True, editable=False
    )

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.CheckConstraint(condition=~Q(dimensions=""), name="fork_dimensions_not_blank"),
            models.CheckConstraint(
                condition=Q(quantity__gte=1, quantity__lte=8), name="fork_quantity_sane"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.quantity} x {self.dimensions}"

    def save(self, *args: object, **kwargs: object) -> None:
        parsed = parse_fork(self.dimensions)
        self.thickness_in, self.width_in, self.length_in = parsed if parsed else (None, None, None)
        super().save(*args, **kwargs)  # type: ignore[arg-type]


class UnitAttachment(SoftDeleteModel):
    class Side(models.TextChoices):
        LH = "LH", "Left (LH)"
        RH = "RH", "Right (RH)"

    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name="attachments")
    manufacturer = text(60)
    type = text(80)  # e.g. side shifter, fork positioner
    model = text(80)
    serial_number = text(80)
    date_code = text(40)
    hose_reel = models.BooleanField(default=False)
    internal_hose = models.BooleanField(default=False)
    reel_number = text(60)
    side = models.CharField(max_length=2, choices=Side.choices, blank=True, default="")

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(side__in=["", "LH", "RH"]), name="attachment_side_valid"
            ),
            models.CheckConstraint(
                condition=~Q(manufacturer="") | ~Q(type="") | ~Q(model=""),
                name="attachment_described",
            ),
        ]

    def __str__(self) -> str:
        return " ".join(p for p in [self.manufacturer, self.type, self.model] if p)


class HourMeterReading(SoftDeleteModel):
    class Source(models.TextChoices):
        CARD = "card", "Unit card"
        SERVICE = "service", "Service"
        SALE = "sale", "Sale / trade-in"
        MANUAL = "manual", "Entered by hand"

    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name="hour_readings")
    reading_date = models.DateField(default=timezone.localdate)
    hours = models.DecimalField(
        max_digits=9, decimal_places=1, validators=[MinValueValidator(Decimal("0"))]
    )
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.MANUAL)
    note = text(200)

    class Meta:
        ordering = ["-reading_date", "-created_at"]
        constraints = [
            models.CheckConstraint(condition=Q(hours__gte=0), name="hours_not_negative"),
            models.CheckConstraint(
                condition=Q(source__in=["card", "service", "sale", "manual"]),
                name="hours_source_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.hours} h on {self.reading_date}"


class OwnershipReason(models.TextChoices):
    """Why a unit changed hands. Blank: the first owner on record, or a change
    recorded before reasons were kept."""

    SOLD = "sold", "Sold"
    PRIVATE_SALE = "private_sale", "Sold between customers"
    TRADE_IN = "trade_in", "Trade-in"
    REPOSSESSION = "repossession", "Repossession"
    BUY_BACK = "buy_back", "Bought back"
    LEASE_RETURN = "lease_return", "Lease return"
    BOUGHT_USED = "bought_used", "Bought used"
    OTHER = "other", "Other"


# Which reasons fit which new owner.
TO_CUSTOMER_REASONS = ("sold", "private_sale", "other")
TO_STOCK_REASONS = ("trade_in", "repossession", "buy_back", "lease_return", "bought_used", "other")


class OwnershipRecord(SoftDeleteModel):
    """Who owned the unit when. Exactly one open record (no end date) per unit.
    owner_kind 'dealer' means Maine Material Handling's own stock.

    Each record is also the deal that started it: a sale out of our stock
    keeps its own sale price and the unit's cost at the time; a unit coming
    back keeps what we paid. Selling the same unit again never overwrites an
    earlier deal."""

    class OwnerKind(models.TextChoices):
        CUSTOMER = "customer", "Customer"
        DEALER = "dealer", "Maine Material Handling stock"

    Reason = OwnershipReason

    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name="ownerships")
    owner_kind = models.CharField(max_length=10, choices=OwnerKind.choices)
    customer = models.ForeignKey(
        Customer, null=True, blank=True, on_delete=models.PROTECT, related_name="ownerships"
    )
    start_date = models.DateField(default=timezone.localdate)
    end_date = models.DateField(null=True, blank=True)
    note = text(200)

    # --- The deal (price and cost: admin and sales only) ----------------------------------
    reason = models.CharField(
        max_length=20, choices=OwnershipReason.choices, blank=True, default="", db_default=""
    )
    # Sale price when we sell it; what we paid (trade allowance, buy-back price,
    # payoff) when it comes back to our stock.
    price = models.DecimalField(**MONEY, validators=[MinValueValidator(Decimal("0"))])  # type: ignore[arg-type]
    # On a sale out of our stock: the unit's cost at the time, so each sale
    # keeps its own margin.
    cost = models.DecimalField(**MONEY, validators=[MinValueValidator(Decimal("0"))])  # type: ignore[arg-type]
    reference = models.CharField(max_length=60, blank=True, default="", db_default="")
    # The hour meter reading taken at handover. Only ever read from this side,
    # so no index (and none to build on a live table).
    hour_reading = models.ForeignKey(
        HourMeterReading,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        db_index=False,
    )
    # What the change did to the unit, {field: [before, after]}, so the latest
    # change can be undone without losing edits made since.
    unit_changes = models.JSONField(null=True, blank=True, editable=False)

    PRICE_FIELDS: ClassVar[tuple[str, ...]] = ("price", "cost")

    class Meta:
        ordering = ["-start_date", "-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(owner_kind="customer", customer__isnull=False)
                | Q(owner_kind="dealer", customer__isnull=True),
                name="ownership_owner_consistent",
            ),
            models.CheckConstraint(
                condition=Q(end_date__isnull=True) | Q(end_date__gte=F("start_date")),
                name="ownership_dates_in_order",
            ),
            models.UniqueConstraint(
                fields=["unit"],
                condition=ALIVE & Q(end_date__isnull=True),
                name="ownership_one_open",
            ),
            models.CheckConstraint(
                condition=Q(reason__in=["", *OwnershipReason.values]),
                name="ownership_reason_valid",
            ),
            models.CheckConstraint(
                condition=Q(reason="")
                | Q(owner_kind="customer", reason__in=TO_CUSTOMER_REASONS)
                | Q(owner_kind="dealer", reason__in=TO_STOCK_REASONS),
                name="ownership_reason_fits_owner",
            ),
            models.CheckConstraint(
                condition=(Q(price__isnull=True) | Q(price__gte=0))
                & (Q(cost__isnull=True) | Q(cost__gte=0)),
                name="ownership_money_not_negative",
            ),
        ]

    def __str__(self) -> str:
        owner = self.customer.name if self.customer else "MMH stock"
        return f"{owner} from {self.start_date}"


def unit_file_path(instance: UnitFile, filename: str) -> str:
    ext = (filename.rsplit(".", 1)[-1] if "." in filename else "bin").lower()[:5]
    return f"units/{instance.unit_id}/{instance.kind}/{uuid.uuid4().hex}.{ext}"


class UnitFile(SoftDeleteModel):
    """Photos, the scanned original card, and other documents. Stored in
    Spaces (MinIO locally), served through the app with permission checks."""

    class Kind(models.TextChoices):
        PHOTO = "photo", "Photo"
        SCANNED_CARD = "scanned_card", "Scanned unit card"
        DOCUMENT = "document", "Document"

    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name="files")
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.PHOTO)
    file = models.FileField(upload_to=unit_file_path, max_length=300)
    thumbnail = models.FileField(upload_to=unit_file_path, max_length=300, blank=True, default="")
    original_name = models.CharField(max_length=255, blank=True, default="")
    content_type = models.CharField(max_length=100)
    size_bytes = models.PositiveBigIntegerField()
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    caption = text(200)
    is_primary = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-is_primary", "sort_order", "created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(kind__in=["photo", "scanned_card", "document"]),
                name="unitfile_kind_valid",
            ),
            models.UniqueConstraint(
                fields=["unit"], condition=ALIVE & Q(is_primary=True), name="unitfile_one_primary"
            ),
        ]

    def __str__(self) -> str:
        return self.caption or self.original_name or self.get_kind_display()
