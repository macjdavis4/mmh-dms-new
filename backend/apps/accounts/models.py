from __future__ import annotations

from typing import Any, ClassVar

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.db.models.functions import Lower

from apps.core.models import SoftDeleteModel, SoftDeleteQuerySet

from .roles import PRICE_ROLES, TWO_FACTOR_REQUIRED_ROLES, Role


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
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, email: str, password: str | None = None, **extra: Any) -> User:
        extra["role"] = Role.ADMIN
        return self.create_user(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin, SoftDeleteModel):
    email = models.EmailField(max_length=254)
    first_name = models.CharField(max_length=80, blank=True, default="")
    last_name = models.CharField(max_length=80, blank=True, default="")
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

    # Django admin site access: admins only.
    @property
    def is_staff(self) -> bool:
        return self.is_active and self.role == Role.ADMIN

    @property
    def can_see_pricing(self) -> bool:
        return self.role in PRICE_ROLES

    @property
    def requires_two_factor(self) -> bool:
        return self.role in TWO_FACTOR_REQUIRED_ROLES

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.is_superuser = self.role == Role.ADMIN
        if self.deleted_at is not None:
            self.is_active = False
        update_fields = kwargs.get("update_fields")
        if update_fields is not None and ("role" in update_fields or "deleted_at" in update_fields):
            kwargs["update_fields"] = {*update_fields, "is_superuser", "is_active"}
        super().save(*args, **kwargs)
