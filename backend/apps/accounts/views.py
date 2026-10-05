"""Sign-in, two-factor and account endpoints (`/api/v1/auth/...`).

Sign-in is two steps when the user has two-factor turned on:

1. POST /login with email + password. If the user has a confirmed 2FA device
   the response is {"status": "otp_required"} and the session only remembers
   who passed step 1 (for five minutes). Nobody is signed in yet.
2. POST /login/verify with the 6-digit code (or a recovery code).

Admins without 2FA are signed in after step 1 but every other endpoint
answers 403 "two_factor_setup_required" until they finish setup.
"""

from __future__ import annotations

import base64
import io
import secrets
import time
from typing import Any

import qrcode
import qrcode.image.svg
from django.conf import settings
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.middleware.csrf import get_token
from django_otp import login as otp_login
from django_otp import user_has_device
from django_otp.plugins.otp_static.models import StaticDevice, StaticToken
from django_otp.plugins.otp_totp.models import TOTPDevice
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.core.models import AuditLog

from .models import User
from .permissions import is_verified

PENDING_USER = "mmh_pending_2fa_user"
PENDING_AT = "mmh_pending_2fa_at"
RECOVERY_CODE_COUNT = 10


LOCKED_OUT = {
    "code": "locked_out",
    "detail": "Too many failed sign-in attempts. Try again in 15 minutes "
    "or ask an admin to unlock your account.",
}


def lockout_response(request: HttpRequest, *args: Any, **kwargs: Any) -> JsonResponse:
    """Called by django-axes when an account is locked."""
    return JsonResponse(LOCKED_OUT, status=429)


def serialize_me(request: Request | HttpRequest) -> dict[str, Any]:
    user = request.user
    if not user.is_authenticated:
        return {"authenticated": False}
    assert isinstance(user, User)
    enabled = user_has_device(user, confirmed=True)
    return {
        "authenticated": True,
        "user": {
            "id": str(user.pk),
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "full_name": user.full_name,
            "role": user.role,
            "role_label": user.get_role_display(),
            "can_see_pricing": user.can_see_pricing,
        },
        "two_factor": {
            "enabled": enabled,
            "verified": is_verified(user),
            "required": user.requires_two_factor,
            "setup_needed": user.requires_two_factor and not is_verified(user),
            "recovery_codes_left": StaticToken.objects.filter(
                device__user=user, device__confirmed=True
            ).count(),
        },
    }


class LoginThrottle(ScopedRateThrottle):
    scope_attr = "throttle_scope"


# --- CSRF / me ---------------------------------------------------------------


class CsrfView(APIView):
    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        get_token(request._request)  # makes CsrfViewMiddleware set the cookie
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        return Response(serialize_me(request))


# --- Sign in / out -------------------------------------------------------------


class LoginSerializer(serializers.Serializer[Any]):
    email = serializers.CharField(max_length=254)
    password = serializers.CharField(max_length=200, trim_whitespace=False)


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [LoginThrottle]
    throttle_scope = "login"

    def post(self, request: Request) -> Response:
        data = LoginSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        email = data.validated_data["email"].strip()
        user = authenticate(
            request._request, username=email, password=data.validated_data["password"]
        )
        if getattr(request._request, "axes_locked_out", False):
            return Response(LOCKED_OUT, status=status.HTTP_429_TOO_MANY_REQUESTS)
        if user is None:
            return Response(
                {"code": "invalid_credentials", "detail": "Email or password is incorrect."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        assert isinstance(user, User)
        request.session.pop(PENDING_USER, None)
        if user_has_device(user, confirmed=True):
            request.session.cycle_key()
            request.session[PENDING_USER] = str(user.pk)
            request.session[PENDING_AT] = int(time.time())
            return Response({"status": "otp_required"})
        login(request._request, user)
        return Response({"status": "ok", **serialize_me(request._request)})


class VerifySerializer(serializers.Serializer[Any]):
    code = serializers.CharField(max_length=20)


class LoginVerifyView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [LoginThrottle]
    throttle_scope = "otp"

    def post(self, request: Request) -> Response:
        data = VerifySerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user_id = request.session.get(PENDING_USER)
        started = request.session.get(PENDING_AT, 0)
        if not user_id or time.time() - started > settings.LOGIN_OTP_WINDOW_SECONDS:
            request.session.pop(PENDING_USER, None)
            return Response(
                {"code": "otp_expired", "detail": "Your sign-in timed out. Please start again."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = User.objects.filter(pk=user_id, is_active=True).first()
        if user is None:
            return Response(
                {"code": "otp_expired", "detail": "Please sign in again."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        code = "".join(data.validated_data["code"].split()).lower()
        device, used_recovery = _verify_any_device(user, code)
        if device is None:
            AuditLog.record(
                AuditLog.Action.LOGIN_FAILED, user, actor=user, after={"reason": "bad 2FA code"}
            )
            return Response(
                {"code": "invalid_code", "detail": "That code is not valid. Try again."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        request.session.pop(PENDING_USER, None)
        request.session.pop(PENDING_AT, None)
        login(request._request, user, backend="django.contrib.auth.backends.ModelBackend")
        otp_login(request._request, device)
        if used_recovery:
            AuditLog.record(AuditLog.Action.RECOVERY_CODE_USED, user, actor=user)
        return Response({"status": "ok", **serialize_me(request._request)})


def _verify_any_device(user: User, code: str) -> tuple[Any, bool]:
    if code.isdigit():
        for totp in TOTPDevice.objects.filter(user=user, confirmed=True):
            if totp.verify_token(code):
                return totp, False
    for static in StaticDevice.objects.filter(user=user, confirmed=True):
        if static.verify_token(code):
            return static, True
    return None, False


class LogoutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        logout(request._request)
        return Response(status=status.HTTP_204_NO_CONTENT)


# --- Two-factor setup ------------------------------------------------------------


def _qr_data_uri(url: str) -> str:
    img = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=2)
    buf = io.BytesIO()
    img.save(buf)
    return "data:image/svg+xml;base64," + base64.b64encode(buf.getvalue()).decode()


def _new_recovery_codes(user: User) -> list[str]:
    device, _ = StaticDevice.objects.get_or_create(user=user, name="Recovery codes")
    device.confirmed = True
    device.save()
    device.token_set.all().delete()
    codes = []
    for _ in range(RECOVERY_CODE_COUNT):
        code = "-".join(secrets.token_hex(2) for _ in range(2))  # e.g. 3f9a-0c71
        device.token_set.create(token=code)
        codes.append(code)
    return codes


class TwoFactorSetupView(APIView):
    """Start (or restart) setup: returns a QR code and the secret for manual entry."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        user = request.user
        assert isinstance(user, User)
        if user_has_device(user, confirmed=True) and not is_verified(user):
            return Response(
                {"code": "not_verified", "detail": "Sign in with your current code first."},
                status=status.HTTP_403_FORBIDDEN,
            )
        device = TOTPDevice.objects.filter(user=user, confirmed=False).first()
        if device is None:
            device = TOTPDevice(user=user, name="Authenticator app", confirmed=False)
        else:
            device.key = TOTPDevice._meta.get_field("key").get_default()
        device.save()
        secret = base64.b32encode(device.bin_key).decode().rstrip("=")
        return Response(
            {
                "secret": secret,
                "otpauth_url": device.config_url,
                "qr_code": _qr_data_uri(device.config_url),
            }
        )


class TwoFactorConfirmView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [LoginThrottle]
    throttle_scope = "otp"

    def post(self, request: Request) -> Response:
        data = VerifySerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = request.user
        assert isinstance(user, User)
        device = TOTPDevice.objects.filter(user=user, confirmed=False).first()
        code = "".join(data.validated_data["code"].split())
        if device is None or not device.verify_token(code):
            return Response(
                {"code": "invalid_code", "detail": "That code is not valid. Try again."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        with transaction.atomic():
            # Only one active authenticator per person.
            for old in TOTPDevice.objects.filter(user=user, confirmed=True).exclude(pk=device.pk):
                old.confirmed = False
                old.save()
            device.confirmed = True
            device.save()
            codes = _new_recovery_codes(user)
            AuditLog.record(AuditLog.Action.TWO_FACTOR_ENABLED, user, actor=user)
        otp_login(request._request, device)
        return Response({"recovery_codes": codes, **serialize_me(request._request)})


class PasswordCheckSerializer(serializers.Serializer[Any]):
    password = serializers.CharField(max_length=200, trim_whitespace=False)


def _check_password(request: Request) -> Response | None:
    data = PasswordCheckSerializer(data=request.data)
    data.is_valid(raise_exception=True)
    if not request.user.check_password(data.validated_data["password"]):
        return Response(
            {"code": "invalid_password", "detail": "Your password is incorrect."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return None


class TwoFactorDisableView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        user = request.user
        assert isinstance(user, User)
        if user.requires_two_factor:
            return Response(
                {"code": "two_factor_required", "detail": "Admins must keep two-factor on."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if error := _check_password(request):
            return error
        with transaction.atomic():
            for model in (TOTPDevice, StaticDevice):
                for device in model.objects.filter(user=user, confirmed=True):
                    device.confirmed = False
                    device.save()
            AuditLog.record(AuditLog.Action.TWO_FACTOR_DISABLED, user, actor=user)
        return Response(serialize_me(request))


class RecoveryCodesView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        user = request.user
        assert isinstance(user, User)
        if not user_has_device(user, confirmed=True) or not is_verified(user):
            return Response(
                {"code": "two_factor_off", "detail": "Turn on two-factor first."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if error := _check_password(request):
            return error
        return Response({"recovery_codes": _new_recovery_codes(user)})


# --- Password --------------------------------------------------------------------


class PasswordChangeSerializer(serializers.Serializer[Any]):
    current_password = serializers.CharField(max_length=200, trim_whitespace=False)
    new_password = serializers.CharField(max_length=200, trim_whitespace=False)


class PasswordChangeView(APIView):
    def post(self, request: Request) -> Response:
        data = PasswordChangeSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = request.user
        assert isinstance(user, User)
        if not user.check_password(data.validated_data["current_password"]):
            return Response(
                {
                    "code": "invalid",
                    "detail": "Please fix the highlighted fields.",
                    "fields": {"current_password": ["Your current password is incorrect."]},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            validate_password(data.validated_data["new_password"], user)
        except DjangoValidationError as exc:
            return Response(
                {
                    "code": "invalid",
                    "detail": "Please fix the highlighted fields.",
                    "fields": {"new_password": list(exc.messages)},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        with transaction.atomic():
            user.set_password(data.validated_data["new_password"])
            user.save(update_fields=["password"])
            AuditLog.record(AuditLog.Action.PASSWORD_CHANGE, user, actor=user)
        update_session_auth_hash(request._request, user)
        return Response(status=status.HTTP_204_NO_CONTENT)
