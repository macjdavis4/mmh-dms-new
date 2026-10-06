from __future__ import annotations

from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel


class BackupRun(TimeStampedModel):
    """One nightly backup attempt (database dump or media copy)."""

    class Kind(models.TextChoices):
        DATABASE = "database", "Database dump"
        MEDIA = "media", "Media copy"
        PAPER = "paper", "Paper backup"

    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    kind = models.CharField(max_length=20, choices=Kind.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RUNNING)
    run_date = models.DateField(default=timezone.localdate)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    object_key = models.CharField(max_length=300, blank=True, default="")
    size_bytes = models.BigIntegerField(null=True, blank=True)
    objects_copied = models.IntegerField(null=True, blank=True)
    row_counts = models.JSONField(null=True, blank=True)
    error = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-started_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(kind__in=["database", "media", "paper"]),
                name="backuprun_kind_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=["running", "succeeded", "failed", "skipped"]),
                name="backuprun_status_valid",
            ),
            # At most one successful backup of each kind per day (keeps retries idempotent).
            models.UniqueConstraint(
                fields=["kind", "run_date"],
                condition=models.Q(status="succeeded"),
                name="backuprun_one_success_per_day",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.kind} {self.run_date} {self.status}"
