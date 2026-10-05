"""Batch imports of unit cards (CSV upload or the JSON API).

A batch is validated first (nothing changes), then applied, and can later be
undone as a whole. Every row keeps the values exactly as they arrived, what
the import did, and what it needs to undo that.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from typing import Any, ClassVar

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.models import SoftDeleteModel, TimeStampedModel


def batch_file_path(instance: ImportBatch, filename: str) -> str:
    return f"imports/{instance.pk}/source-{uuid.uuid4().hex}.csv"


def scan_file_path(instance: ImportFile, filename: str) -> str:
    ext = (filename.rsplit(".", 1)[-1] if "." in filename else "bin").lower()[:5]
    return f"imports/{instance.batch_id}/scans/{uuid.uuid4().hex}.{ext}"


class ImportBatch(SoftDeleteModel):
    class Source(models.TextChoices):
        CSV = "csv", "CSV upload"
        API = "api", "Import API"

    class Status(models.TextChoices):
        DRAFT = "draft", "Checked, not imported yet"
        QUEUED = "queued", "Waiting to import"
        IMPORTING = "importing", "Importing"
        IMPORTED = "imported", "Imported"
        FAILED = "failed", "Import failed"
        UNDOING = "undoing", "Undoing"
        UNDONE = "undone", "Undone"
        DISCARDED = "discarded", "Discarded"

    class OnExisting(models.TextChoices):
        UPDATE = "update", "Fill in and update the existing unit"
        SKIP = "skip", "Leave the existing unit alone"

    source = models.CharField(max_length=10, choices=Source.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    filename = models.CharField(max_length=255, blank=True, default="")
    reference = models.CharField(max_length=100, blank=True, default="")  # API callers' own id
    original = models.FileField(upload_to=batch_file_path, blank=True, max_length=300)
    on_existing = models.CharField(
        max_length=10, choices=OnExisting.choices, default=OnExisting.UPDATE
    )
    skip_invalid = models.BooleanField(default=False)
    api_key = models.ForeignKey(
        "ApiKey", null=True, blank=True, on_delete=models.PROTECT, related_name="batches"
    )
    # Problems with the file as a whole (unknown columns, unused scans...).
    file_messages = models.JSONField(default=list, blank=True)
    # Row counts by outcome, refreshed after validate / apply / undo.
    counts = models.JSONField(default=dict, blank=True)
    row_count = models.PositiveIntegerField(default=0)
    validated_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    undone_at = models.DateTimeField(null=True, blank=True)
    undone_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    error = models.TextField(blank=True, default="")  # set when the import job itself failed

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(source__in=["csv", "api"]), name="batch_source_valid"
            ),
            models.CheckConstraint(
                condition=Q(
                    status__in=[
                        "draft",
                        "queued",
                        "importing",
                        "imported",
                        "failed",
                        "undoing",
                        "undone",
                        "discarded",
                    ]
                ),
                name="batch_status_valid",
            ),
            models.CheckConstraint(
                condition=Q(on_existing__in=["update", "skip"]), name="batch_on_existing_valid"
            ),
        ]

    def __str__(self) -> str:
        return f"Import {self.filename or self.reference or self.pk} ({self.get_status_display()})"

    @property
    def audit_tag(self) -> str:
        """request_id written on every audit entry the import makes."""
        return f"import-{self.pk}"


class ImportRow(TimeStampedModel):
    """One unit card. Not audited itself (the batch and the units are); a
    database trigger stops rows from being deleted."""

    class Check(models.TextChoices):
        OK = "ok", "Ready"
        WARNING = "warning", "Ready, with warnings"
        ERROR = "error", "Has errors"

    class Plan(models.TextChoices):
        CREATE = "create", "Add a new unit"
        UPDATE = "update", "Update an existing unit"
        UNCHANGED = "unchanged", "Already up to date"
        SKIP = "skip", "Skip"

    class Result(models.TextChoices):
        PENDING = "", "Not imported"
        CREATED = "created", "Added"
        UPDATED = "updated", "Updated"
        UNCHANGED = "unchanged", "No changes needed"
        SKIPPED = "skipped", "Skipped"
        FAILED = "failed", "Failed"

    batch = models.ForeignKey(ImportBatch, on_delete=models.PROTECT, related_name="rows")
    row_number = models.PositiveIntegerField()  # spreadsheet row (header is row 1) or list position
    raw = models.JSONField()  # exactly as received
    status = models.CharField(max_length=10, choices=Check.choices, default=Check.OK)
    plan = models.CharField(max_length=10, choices=Plan.choices, blank=True, default="")
    errors = models.JSONField(default=list, blank=True)  # [{"column": ..., "message": ...}]
    warnings = models.JSONField(default=list, blank=True)
    changes = models.JSONField(default=list, blank=True)  # columns that would change (preview)
    serial = models.CharField(max_length=80, blank=True, default="")  # for display and search
    label = models.CharField(max_length=200, blank=True, default="")  # "Hyundai 35LN-9A"
    customer_name = models.CharField(max_length=200, blank=True, default="")
    unit = models.ForeignKey(
        "units.Unit", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    result = models.CharField(max_length=10, choices=Result.choices, blank=True, default="")
    applied_at = models.DateTimeField(null=True, blank=True)
    undo = models.JSONField(default=dict, blank=True)  # what to reverse; see services.apply_row
    undo_result = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        ordering = ["row_number"]
        constraints = [
            models.UniqueConstraint(fields=["batch", "row_number"], name="import_row_unique"),
            models.CheckConstraint(
                condition=Q(status__in=["ok", "warning", "error"]), name="import_row_status_valid"
            ),
            models.CheckConstraint(
                condition=Q(plan__in=["", "create", "update", "unchanged", "skip"]),
                name="import_row_plan_valid",
            ),
            models.CheckConstraint(
                condition=Q(
                    result__in=["", "created", "updated", "unchanged", "skipped", "failed"]
                ),
                name="import_row_result_valid",
            ),
        ]
        indexes = [models.Index(fields=["batch", "status"], name="import_row_status_idx")]

    def __str__(self) -> str:
        return f"Row {self.row_number} of {self.batch_id}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.updated_at = timezone.now()
        if kwargs.get("update_fields") is not None:
            kwargs["update_fields"] = {*kwargs["update_fields"], "updated_at"}
        super().save(*args, **kwargs)


class ImportFile(TimeStampedModel):
    """A scanned card uploaded with a batch, matched to rows by
    `source_image_filename`. Kept after the import (the unit gets its own copy)."""

    batch = models.ForeignKey(ImportBatch, on_delete=models.PROTECT, related_name="files")
    file = models.FileField(upload_to=scan_file_path, max_length=300)
    original_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    size_bytes = models.PositiveIntegerField()
    sha256 = models.CharField(max_length=64)

    class Meta:
        ordering = ["original_name"]
        constraints = [
            models.UniqueConstraint(
                models.functions.Lower("original_name"),
                "batch",
                name="import_file_name_unique",
            )
        ]

    def __str__(self) -> str:
        return self.original_name


KEY_PREFIX = "mmh_"


def hash_key(raw: str) -> str:
    # Keys are 256-bit random values, so a plain SHA-256 is enough (no stretching needed).
    return hashlib.sha256(raw.encode()).hexdigest()


class ApiKey(SoftDeleteModel):
    """For the scanning app and other tools that call the import API. The key
    is shown once when created; only its hash is stored. Imports made with a
    key are recorded as the admin who created it."""

    name = models.CharField(max_length=100)
    prefix = models.CharField(max_length=12, unique=True)  # first characters, to recognise a key
    key_hash = models.CharField(max_length=64, unique=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    audit_exclude: ClassVar[set[str]] = {"key_hash", "last_used_at"}

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.CheckConstraint(condition=~Q(name=""), name="api_key_name_not_blank")]

    def __str__(self) -> str:
        return f"{self.name} ({self.prefix}…)"

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None and self.deleted_at is None

    @classmethod
    def generate(cls, name: str) -> tuple[ApiKey, str]:
        raw = KEY_PREFIX + secrets.token_urlsafe(32)
        key = cls(name=name, prefix=raw[: len(KEY_PREFIX) + 6], key_hash=hash_key(raw))
        key.save()
        return key, raw
