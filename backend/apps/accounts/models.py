from __future__ import annotations

from typing import Any, ClassVar

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models.functions import Lower

from apps.core.models import SoftDeleteModel, SoftDeleteQuerySet

from .roles import (
    PRICE_ROLES,
    TWO_FACTOR_REQUIRED_ROLES,
    Role,
    has_any_role,
    normalize_roles,
    primary_role,
    role_labels,
)


class UserManager(BaseUserManager.from_queryset(SoftDeleteQuerySet)):  # type: ignore[misc]
    use_in_migrations = True

    def get_queryset(self) -> SoftDeleteQuerySet:
        return super().get_queryset().filter(deleted_at__isnull=True)

    def get_by_natural_key(self, username: str | None) -> User:
        return self.get(email__iexact=(username or "").strip())

    def create_user(self, email: str, password: str | None = None, **extra: Any) -> User:
        if not email:
            raise ValueError("Email is required")
        user = self.model(email=self.normalize_email(email).strip(), **extra)
        if not user.roles and "role" in extra:
            user.roles = [extra["role"]]
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, email: str, password: str | None = None, **extra: Any) -> User:
        extra["role"] = Role.ADMIN
        extra["roles"] = [Role.ADMIN]
        return self.create_user(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin, SoftDeleteModel):
    email = models.EmailField(max_length=254)
    first_name = models.CharField(max_length=80, blank=True, default="")
    last_name = models.CharField(max_length=80, blank=True, default="")
    # `roles` is the source of truth. `role` is kept in step with it (the first
    # role by priority) so the version running during a deploy keeps working; it
    # is removed in a later release.
    roles = ArrayField(
        models.CharField(max_length=20, choices=Role.choices),
        default=list,
        # A database default, so the previous version (which does not know this
        # column) can still add users while a deploy is in progress.
        db_default=[],
        blank=True,
        help_text="Admin and read-only stand alone; sales, service and parts combine freely.",
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.READ_ONLY)
    is_active = models.BooleanField(default=True)
    phone = models.CharField(max_length=30, blank=True, default="")

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS: ClassVar[list[str]] = ["first_name", "last_name"]

    audit_exclude: ClassVar[set[str]] = {"password", "last_login"}

    objects = UserManager()  # type: ignore[assignment,misc]
    all_objects = SoftDeleteQuerySet.as_manager()  # type: ignore[misc]

    class Meta:
        ordering = ["first_name", "last_name", "email"]
        constraints = [
            models.UniqueConstraint(Lower("email"), name="user_email_unique_ci"),
            models.CheckConstraint(
                condition=models.Q(role__in=[r.value for r in Role]), name="user_role_valid"
            ),
            # Only real roles.
            models.CheckConstraint(
                condition=models.Q(roles__contained_by=[r.value for r in Role]),
                name="user_roles_valid",
            ),
            # Admin and read-only can never be combined with anything else.
            models.CheckConstraint(
                condition=~models.Q(roles__overlap=[Role.ADMIN.value, Role.READ_ONLY.value])
                | models.Q(roles__len=1),
                name="user_roles_admin_readonly_alone",
            ),
            models.CheckConstraint(condition=~models.Q(email=""), name="user_email_not_blank"),
            # A deleted user can never be active.
            models.CheckConstraint(
                condition=models.Q(deleted_at__isnull=True) | models.Q(is_active=False),
                name="user_deleted_is_inactive",
            ),
        ]

    def __str__(self) -> str:
        return self.full_name or self.email

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def effective_roles(self) -> list[str]:
        """All roles. Falls back to the legacy single role for a row written by
        the previous version during a deploy."""
        return normalize_roles(self.roles) or [self.role]

    @property
    def role_label(self) -> str:
        return role_labels(self.effective_roles)

    @property
    def roles_text(self) -> str:
        """Compact form for the audit log, e.g. "sales,service"."""
        return ",".join(self.effective_roles)

    def has_role(self, *roles: str) -> bool:
        return has_any_role(self, roles)

    # Django admin site access: admins only.
    @property
    def is_staff(self) -> bool:
        return self.is_active and self.has_role(Role.ADMIN)

    @property
    def can_see_pricing(self) -> bool:
        return has_any_role(self, PRICE_ROLES)

    @property
    def requires_two_factor(self) -> bool:
        return has_any_role(self, TWO_FACTOR_REQUIRED_ROLES)

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.roles = normalize_roles(self.roles) or [self.role]
        self.role = primary_role(self.roles)
        self.is_superuser = Role.ADMIN in self.roles
        if self.deleted_at is not None:
            self.is_active = False
        update_fields = kwargs.get("update_fields")
        if update_fields is not None and ({"role", "roles", "deleted_at"} & set(update_fields)):
            kwargs["update_fields"] = {*update_fields, "role", "roles", "is_superuser", "is_active"}
        super().save(*args, **kwargs)
