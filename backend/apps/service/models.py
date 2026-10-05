"""Service work orders: what was wrong, why, what was done, and who spent
how long on it. Parts used arrive with the parts stock ledger (Phase 10)."""

from __future__ import annotations

from typing import ClassVar

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import connection, models
from django.db.models import Q
from django.utils import timezone

from apps.core.models import SoftDeleteModel
from apps.customers.models import Customer
from apps.units.models import HourMeterReading, Unit

NUMBER_SEQUENCE = "service_work_order_number_seq"


def next_number() -> str:
    """WO-20001, WO-20002, … from a database sequence (no gaps from races).
    Five digits and up, so they never clash with the 4-digit numbers on old cards."""
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT nextval('{NUMBER_SEQUENCE}')")
        (value,) = cursor.fetchone()  # type: ignore[misc]
    return f"WO-{value}"


class MaintenancePlan(SoftDeleteModel):
    """Planned maintenance for one unit: every N hours and/or every N days,
    whichever comes first, counted from when it was last done."""

    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name="maintenance_plans")
    name = models.CharField(max_length=100)  # e.g. "250-hour service"
    tasks = models.TextField(
        blank=True, default=""
    )  # what to do; becomes the work order's complaint
    interval_hours = models.PositiveIntegerField(null=True, blank=True)
    interval_days = models.PositiveIntegerField(null=True, blank=True)
    last_done_on = models.DateField(default=timezone.localdate)
    last_done_hours = models.DecimalField(
        max_digits=9, decimal_places=1, null=True, blank=True, validators=[MinValueValidator(0)]
    )
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(condition=~Q(name=""), name="plan_name_not_blank"),
            models.CheckConstraint(
                # Spelled out with isnull: a comparison with NULL is never false in SQL.
                condition=Q(interval_hours__isnull=False, interval_hours__gt=0)
                | Q(interval_days__isnull=False, interval_days__gt=0),
                name="plan_has_an_interval",
            ),
            # Counting by hours needs a starting hour meter reading.
            models.CheckConstraint(
                condition=Q(interval_hours__isnull=True) | Q(last_done_hours__isnull=False),
                name="plan_hours_need_a_start",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} · {self.unit}"


class WorkOrder(SoftDeleteModel):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In progress"
        ON_HOLD = "on_hold", "On hold"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    class Kind(models.TextChoices):
        REPAIR = "repair", "Repair"
        MAINTENANCE = "maintenance", "Planned maintenance"
        INSPECTION = "inspection", "Inspection"
        PREP = "prep", "Prep for sale"
        WARRANTY = "warranty", "Warranty"

    class Location(models.TextChoices):
        SHOP = "shop", "In the shop"
        FIELD = "field", "On site (field)"

    OPEN_STATUSES: ClassVar[tuple[str, ...]] = ("open", "in_progress", "on_hold")

    number = models.CharField(max_length=20, unique=True, editable=False)
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name="work_orders")
    # Who the work is for. Blank means our own stock (e.g. prep for sale).
    customer = models.ForeignKey(
        Customer, null=True, blank=True, on_delete=models.PROTECT, related_name="work_orders"
    )
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.REPAIR)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    location = models.CharField(max_length=10, choices=Location.choices, default=Location.SHOP)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="assigned_work_orders",
    )
    complaint = models.TextField(blank=True, default="")
    cause = models.TextField(blank=True, default="")
    correction = models.TextField(blank=True, default="")
    hold_reason = models.CharField(max_length=200, blank=True, default="")
    customer_po = models.CharField(max_length=60, blank=True, default="")
    contact = models.CharField(max_length=120, blank=True, default="")  # who to call on site
    opened_on = models.DateField(default=timezone.localdate)
    due_on = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    hour_reading = models.OneToOneField(
        HourMeterReading, null=True, blank=True, on_delete=models.PROTECT, related_name="work_order"
    )
    notes = models.TextField(blank=True, default="")
    # Set when the work order was made for a maintenance plan. Completing it
    # marks the plan done; the plan's previous "last done" is kept here so
    # reopening the work order can put it back.
    maintenance_plan = models.ForeignKey(
        MaintenancePlan, null=True, blank=True, on_delete=models.PROTECT, related_name="work_orders"
    )
    plan_prev_done_on = models.DateField(null=True, blank=True, editable=False)
    plan_prev_done_hours = models.DecimalField(
        max_digits=9, decimal_places=1, null=True, blank=True, editable=False
    )

    class Meta:
        ordering = ["-opened_on", "-number"]
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    status__in=["open", "in_progress", "on_hold", "completed", "cancelled"]
                ),
                name="work_order_status_valid",
            ),
            models.CheckConstraint(
                condition=Q(kind__in=["repair", "maintenance", "inspection", "prep", "warranty"]),
                name="work_order_kind_valid",
            ),
            models.CheckConstraint(
                condition=Q(location__in=["shop", "field"]), name="work_order_location_valid"
            ),
            # Completed means done: when, and what was done, are recorded.
            models.CheckConstraint(
                condition=~Q(status="completed")
                | (Q(completed_at__isnull=False) & ~Q(correction="")),
                name="work_order_completed_has_correction",
            ),
            models.CheckConstraint(
                condition=Q(due_on__isnull=True) | Q(due_on__gte=models.F("opened_on")),
                name="work_order_due_after_opened",
            ),
        ]
        indexes = [models.Index(fields=["status", "-opened_on"], name="work_order_status_idx")]

    def __str__(self) -> str:
        return f"{self.number} · {self.unit}"

    def save(self, *args: object, **kwargs: object) -> None:
        if not self.number:
            self.number = next_number()
        super().save(*args, **kwargs)  # type: ignore[arg-type]

    @property
    def is_open(self) -> bool:
        return self.status in self.OPEN_STATUSES


class LaborLine(SoftDeleteModel):
    """Time a mechanic spent on a work order."""

    work_order = models.ForeignKey(WorkOrder, on_delete=models.PROTECT, related_name="labor")
    mechanic = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="labor_lines"
    )
    work_date = models.DateField(default=timezone.localdate)
    hours = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0)])
    description = models.CharField(max_length=300, blank=True, default="")

    class Meta:
        ordering = ["work_date", "created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(hours__gt=0, hours__lte=24), name="labor_hours_sane"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.hours} h on {self.work_date}"
