"""Base model classes and system tables.

Rules enforced here (see CLAUDE.md, "Data rules"):
* Nothing is hard deleted. `SoftDeleteModel.delete()` sets `deleted_at`, and a
  Postgres trigger refuses real DELETEs on soft-delete tables.
* Every write to an audited model records who, what, when, before and after
  in `AuditLog`, inside the same transaction as the write.
* Bulk `QuerySet.update()` / `.delete()` would skip the audit trail, so they
  are blocked on audited models.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, ClassVar

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.fields import ArrayField
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models, transaction
from django.db.models.functions import Now
from django.utils import timezone

from .context import get_context


class AuditBypassError(RuntimeError):
    """Raised when code tries to bulk-update or bulk-delete audited rows."""


def _snapshot(instance: models.Model, exclude: set[str]) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for f in instance._meta.concrete_fields:
        if f.name in exclude or f.attname in exclude:
            continue
        data[f.attname] = f.value_from_object(instance)
    # Round-trip through JSON so dates, UUIDs and Decimals become plain values.
    return json.loads(json.dumps(data, cls=DjangoJSONEncoder))


# ---------------------------------------------------------------------------
# Abstract bases
# ---------------------------------------------------------------------------


class TimeStampedModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(default=timezone.now, db_default=Now(), editable=False)
    updated_at = models.DateTimeField(default=timezone.now, db_default=Now(), editable=False)

    class Meta:
        abstract = True


class AuditedQuerySet(models.QuerySet):  # type: ignore[type-arg]
    def update(self, **kwargs: Any) -> int:
        raise AuditBypassError(
            f"Bulk update on {self.model.__name__} would bypass the audit log; "
            "save each object instead."
        )

    def delete(self) -> tuple[int, dict[str, int]]:
        raise AuditBypassError(
            f"Bulk delete on {self.model.__name__} is not allowed; soft delete each object instead."
        )


class AuditedModel(TimeStampedModel):
    """Every create/update is written to the audit log."""

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        editable=False,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        editable=False,
    )

    # Fields never copied into the audit log (secrets, noise).
    audit_exclude: ClassVar[set[str]] = set()
    _ALWAYS_EXCLUDE: ClassVar[set[str]] = {"updated_at", "updated_by"}

    objects = AuditedQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args: Any, audit_action: str | None = None, **kwargs: Any) -> None:
        ctx = get_context()
        is_new = self._state.adding
        exclude = self._audit_excluded()
        update_fields = kwargs.get("update_fields")

        with transaction.atomic():
            before: dict[str, Any] | None = None
            if not is_new:
                previous = type(self)._base_manager.filter(pk=self.pk).first()
                if previous is None:
                    is_new = True
                else:
                    before = _snapshot(previous, exclude)

            self.updated_at = timezone.now()
            if ctx.user_id:
                self.updated_by_id = ctx.user_id  # type: ignore[attr-defined]
                if is_new and not self.created_by_id:  # type: ignore[attr-defined]
                    self.created_by_id = ctx.user_id  # type: ignore[attr-defined]
            if update_fields is not None:
                kwargs["update_fields"] = {*update_fields, "updated_at", "updated_by"}

            super().save(*args, **kwargs)

            after = _snapshot(self, exclude)
            if is_new:
                AuditLog.record(
                    audit_action or AuditLog.Action.CREATE, self, before=None, after=after
                )
                return
            changed = sorted(k for k in after if before is None or before.get(k) != after[k])
            if not changed and audit_action is None:
                return
            AuditLog.record(
                audit_action or AuditLog.Action.UPDATE,
                self,
                before={k: before.get(k) for k in changed} if before else None,
                after={k: after[k] for k in changed},
            )

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise AuditBypassError(f"{type(self).__name__} rows cannot be deleted.")

    def _audit_excluded(self) -> set[str]:
        return self._ALWAYS_EXCLUDE | set(self.audit_exclude)


class SoftDeleteQuerySet(AuditedQuerySet):
    def alive(self) -> SoftDeleteQuerySet:
        return self.filter(deleted_at__isnull=True)

    def dead(self) -> SoftDeleteQuerySet:
        return self.filter(deleted_at__isnull=False)


class SoftDeleteManager(models.Manager.from_queryset(SoftDeleteQuerySet)):  # type: ignore[misc]
    """Default manager: hides soft-deleted rows."""

    def get_queryset(self) -> SoftDeleteQuerySet:
        return super().get_queryset().filter(deleted_at__isnull=True)


class SoftDeleteModel(AuditedModel):
    """Rows are never removed. `delete()` marks them deleted; `restore()` undoes it.

    A database trigger (see `apps.core.migration_ops.PreventHardDelete`) refuses
    real DELETE statements on these tables, so nothing slips past the ORM.
    """

    deleted_at = models.DateTimeField(null=True, blank=True, editable=False, db_index=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        editable=False,
    )

    objects = SoftDeleteManager()  # type: ignore[misc]
    all_objects = SoftDeleteQuerySet.as_manager()

    class Meta:
        abstract = True

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:  # type: ignore[override]
        self.soft_delete()
        return (1, {self._meta.label: 1})

    def soft_delete(self) -> None:
        if self.deleted_at is not None:
            return
        self.deleted_at = timezone.now()
        self.deleted_by_id = get_context().user_id  # type: ignore[attr-defined]
        self.save(audit_action=AuditLog.Action.SOFT_DELETE)

    def restore(self) -> None:
        if self.deleted_at is None:
            return
        self.deleted_at = None
        self.deleted_by_id = None  # type: ignore[attr-defined]
        self.save(audit_action=AuditLog.Action.RESTORE)


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


class AuditAction(models.TextChoices):
    CREATE = "create", "Created"
    UPDATE = "update", "Updated"
    SOFT_DELETE = "soft_delete", "Deleted"
    RESTORE = "restore", "Restored"
    LOGIN = "login", "Signed in"
    LOGIN_FAILED = "login_failed", "Failed sign-in"
    LOGOUT = "logout", "Signed out"
    LOCKED_OUT = "locked_out", "Account locked"
    PASSWORD_CHANGE = "password_change", "Password changed"
    TWO_FACTOR_ENABLED = "2fa_enabled", "Two-factor enabled"
    TWO_FACTOR_DISABLED = "2fa_disabled", "Two-factor removed"
    RECOVERY_CODE_USED = "recovery_code_used", "Recovery code used"


class AuditLog(models.Model):
    """Append-only. A Postgres trigger rejects UPDATE and DELETE on this table."""

    Action = AuditAction

    id = models.BigAutoField(primary_key=True)
    at = models.DateTimeField(default=timezone.now, db_default=Now(), db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="audit_entries",
    )
    actor_role = models.CharField(max_length=20, blank=True, default="")
    source = models.CharField(max_length=20, blank=True, default="")
    action = models.CharField(max_length=30, choices=Action.choices)
    content_type = models.ForeignKey(ContentType, null=True, blank=True, on_delete=models.PROTECT)
    object_id = models.CharField(max_length=64, blank=True, default="")
    object_repr = models.CharField(max_length=200, blank=True, default="")
    before = models.JSONField(null=True, blank=True, encoder=DjangoJSONEncoder)
    after = models.JSONField(null=True, blank=True, encoder=DjangoJSONEncoder)
    changed_fields = ArrayField(models.CharField(max_length=100), default=list, blank=True)
    request_id = models.CharField(max_length=64, blank=True, default="")
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True, default="")

    class Meta:
        ordering = ["-at", "-id"]
        indexes = [
            models.Index(fields=["content_type", "object_id", "-at"], name="audit_object_idx"),
            models.Index(fields=["actor", "-at"], name="audit_actor_idx"),
            models.Index(fields=["action", "-at"], name="audit_action_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(action__in=AuditAction.values),
                name="auditlog_action_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.at:%Y-%m-%d %H:%M} {self.action} {self.object_repr}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            raise AuditBypassError("Audit log entries cannot be changed.")
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise AuditBypassError("Audit log entries cannot be deleted.")

    @classmethod
    def record(
        cls,
        action: str,
        obj: models.Model | None = None,
        *,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
        actor: Any = None,
        object_repr: str = "",
    ) -> AuditLog:
        ctx = get_context()
        actor_id = getattr(actor, "pk", None) or ctx.user_id
        keys = sorted(set(before or {}) | set(after or {}))
        return cls.objects.create(
            action=action,
            actor_id=actor_id,
            actor_role=getattr(actor, "role", "") or ctx.user_role,
            source=ctx.source,
            content_type=ContentType.objects.get_for_model(obj) if obj is not None else None,
            object_id=str(obj.pk) if obj is not None else "",
            object_repr=(object_repr or (str(obj) if obj is not None else ""))[:200],
            before=before,
            after=after,
            changed_fields=keys if action == cls.Action.UPDATE else [],
            request_id=ctx.request_id[:64],
            ip=ctx.ip or None,
            user_agent=ctx.user_agent[:300],
        )


# ---------------------------------------------------------------------------
# System settings
# ---------------------------------------------------------------------------


class SiteSettings(AuditedModel):
    """Singleton row (id is always 1). Read-only mode and the maintenance banner."""

    class BannerLevel(models.TextChoices):
        INFO = "info", "Information"
        WARNING = "warning", "Warning"
        CRITICAL = "critical", "Critical"

    SINGLETON_ID: ClassVar[uuid.UUID] = uuid.UUID(int=1)

    read_only_mode = models.BooleanField(default=False)
    banner_message = models.CharField(max_length=300, blank=True, default="")
    banner_level = models.CharField(
        max_length=10, choices=BannerLevel.choices, default=BannerLevel.INFO
    )

    class Meta:
        verbose_name = "site settings"
        verbose_name_plural = "site settings"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(id=uuid.UUID(int=1)), name="sitesettings_singleton"
            ),
            models.CheckConstraint(
                condition=models.Q(banner_level__in=["info", "warning", "critical"]),
                name="sitesettings_banner_level_valid",
            ),
        ]

    def __str__(self) -> str:
        return "Site settings"

    @classmethod
    def is_read_only(cls) -> bool:
        return bool(
            cls.objects.filter(pk=cls.SINGLETON_ID).values_list("read_only_mode", flat=True).first()
        )

    @classmethod
    def load(cls) -> SiteSettings:
        obj = cls.objects.filter(pk=cls.SINGLETON_ID).first()
        if obj is None:
            obj = cls(pk=cls.SINGLETON_ID)
            obj.save()
        return obj


class FeatureFlag(AuditedModel):
    """Turns large features on per environment, optionally for some roles only."""

    key = models.SlugField(max_length=60, unique=True)
    description = models.CharField(max_length=200, blank=True, default="")
    enabled = models.BooleanField(default=False)
    roles = ArrayField(
        models.CharField(max_length=20),
        default=list,
        blank=True,
        help_text="Leave empty to enable for every role.",
    )

    class Meta:
        ordering = ["key"]

    def __str__(self) -> str:
        return self.key

    def is_on_for(self, user: Any) -> bool:
        if not self.enabled:
            return False
        return not self.roles or getattr(user, "role", None) in self.roles
