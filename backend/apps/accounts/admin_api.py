"""Admin-only user management (`/api/v1/admin/users`)."""

from __future__ import annotations

from typing import Any

from axes.utils import reset as axes_reset
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.db.models import Q, QuerySet
from django_otp import user_has_device
from django_otp.plugins.otp_static.models import StaticDevice
from django_otp.plugins.otp_totp.models import TOTPDevice
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.core.models import AuditLog

from .models import User
from .permissions import IsAdmin
from .roles import Role


class UserSerializer(serializers.ModelSerializer[User]):
    full_name = serializers.CharField(read_only=True)
    role_label = serializers.CharField(source="get_role_display", read_only=True)
    two_factor_enabled = serializers.SerializerMethodField()
    is_deleted = serializers.BooleanField(read_only=True)
    password = serializers.CharField(
        write_only=True, required=False, trim_whitespace=False, max_length=200
    )

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "phone",
            "role",
            "role_label",
            "is_active",
            "is_deleted",
            "two_factor_enabled",
            "last_login",
            "created_at",
            "password",
        ]
        read_only_fields = ["id", "last_login", "created_at"]

    def get_two_factor_enabled(self, obj: User) -> bool:
        return user_has_device(obj, confirmed=True)

    def validate_email(self, value: str) -> str:
        value = value.strip()
        qs = User.all_objects.filter(email__iexact=value)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if self.instance is None and not attrs.get("password"):
            raise serializers.ValidationError({"password": ["Set a starting password."]})
        if attrs.get("password"):
            probe = self.instance or User(
                email=attrs.get("email", ""),
                first_name=attrs.get("first_name", ""),
                last_name=attrs.get("last_name", ""),
            )
            try:
                validate_password(attrs["password"], probe)
            except Exception as exc:
                raise serializers.ValidationError(
                    {"password": list(getattr(exc, "messages", [str(exc)]))}
                ) from exc
        request = self.context["request"]
        if self.instance is not None and self.instance.pk == request.user.pk:
            if attrs.get("role", self.instance.role) != Role.ADMIN:
                raise serializers.ValidationError(
                    {"role": ["You cannot remove your own admin role."]}
                )
            if attrs.get("is_active") is False:
                raise serializers.ValidationError(
                    {"is_active": ["You cannot deactivate yourself."]}
                )
        return attrs

    def create(self, validated_data: dict[str, Any]) -> User:
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user

    def update(self, instance: User, validated_data: dict[str, Any]) -> User:
        password = validated_data.pop("password", None)
        for key, value in validated_data.items():
            setattr(instance, key, value)
        with transaction.atomic():
            if password:
                instance.set_password(password)
                AuditLog.record(AuditLog.Action.PASSWORD_CHANGE, instance)
            instance.save()
        return instance


def _other_active_admins(user: User) -> bool:
    return User.objects.filter(role=Role.ADMIN, is_active=True).exclude(pk=user.pk).exists()


class UserAdminViewSet(viewsets.ModelViewSet[User]):
    permission_classes = [IsAdmin]
    serializer_class = UserSerializer
    http_method_names = ["get", "post", "patch", "delete", "options"]

    def get_queryset(self) -> QuerySet[User]:
        params = self.request.query_params
        qs: QuerySet[User] = (
            User.all_objects.all() if params.get("include_deleted") == "1" else User.objects.all()
        )
        if role := params.get("role"):
            qs = qs.filter(role=role)
        if q := params.get("q", "").strip():
            qs = qs.filter(
                Q(email__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q)
            )
        return qs.order_by("first_name", "last_name", "email")

    def perform_update(self, serializer: Any) -> None:
        user: User = serializer.instance
        demoting = (
            user.role == Role.ADMIN
            and serializer.validated_data.get("role", Role.ADMIN) != Role.ADMIN
        )
        deactivating = serializer.validated_data.get("is_active") is False
        if (demoting or deactivating) and not _other_active_admins(user):
            raise serializers.ValidationError({"role": ["At least one active admin is required."]})
        serializer.save()

    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        user = self.get_object()
        if user.pk == request.user.pk:
            return Response(
                {"code": "not_allowed", "detail": "You cannot remove your own account."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if user.role == Role.ADMIN and not _other_active_admins(user):
            return Response(
                {"code": "not_allowed", "detail": "At least one active admin is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def restore(self, request: Request, pk: str | None = None) -> Response:
        user = User.all_objects.get(pk=self.kwargs["pk"])
        with transaction.atomic():
            user.restore()
            user.is_active = True
            user.save()
        return Response(self.get_serializer(user).data)

    @action(detail=True, methods=["post"], url_path="reset-2fa")
    def reset_two_factor(self, request: Request, pk: str | None = None) -> Response:
        """For a lost phone. The person sets 2FA up again at next sign-in."""
        user = self.get_object()
        with transaction.atomic():
            for model in (TOTPDevice, StaticDevice):
                for device in model.objects.filter(user=user, confirmed=True):
                    device.confirmed = False
                    device.save()
            AuditLog.record(AuditLog.Action.TWO_FACTOR_DISABLED, user, after={"by_admin": True})
        return Response(self.get_serializer(user).data)

    @action(detail=True, methods=["post"])
    def unlock(self, request: Request, pk: str | None = None) -> Response:
        user = self.get_object()
        axes_reset(username=user.email.lower())
        return Response(self.get_serializer(user).data)
