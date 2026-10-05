from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from django_otp.plugins.otp_totp.models import TOTPDevice
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import Role

PASSWORD = "Forklift-Test-Pass-2026"


@pytest.fixture(autouse=True)
def _reset_axes(db: Any) -> None:
    from axes.utils import reset
    from django.core.cache import cache

    reset()
    cache.clear()  # login rate-limit counters


@pytest.fixture
def make_user(db: Any) -> Callable[..., User]:
    counter = {"n": 0}

    def _make(role: str = Role.READ_ONLY, email: str | None = None, **extra: Any) -> User:
        counter["n"] += 1
        return User.objects.create_user(
            email or f"{role}{counter['n']}@example.com",
            PASSWORD,
            first_name=role.title(),
            last_name="Tester",
            role=role,
            **extra,
        )

    return _make


def add_totp(user: User) -> TOTPDevice:
    return TOTPDevice.objects.create(user=user, name="test", confirmed=True)


def signed_in_client(user: User, *, verified: bool | None = None) -> APIClient:
    """A client with a real session. Admins get a verified 2FA session by default."""
    client = APIClient()
    client.force_login(user)
    if verified is None:
        verified = user.requires_two_factor
    if verified:
        device = TOTPDevice.objects.filter(user=user, confirmed=True).first() or add_totp(user)
        session = client.session
        session["otp_device_id"] = device.persistent_id
        session.save()
    return client


@pytest.fixture
def client_for(make_user: Callable[..., User]) -> Callable[[str], APIClient]:
    def _client(role: str) -> APIClient:
        return signed_in_client(make_user(role))

    return _client


@pytest.fixture
def admin_user(make_user: Callable[..., User]) -> User:
    return make_user(Role.ADMIN, email="boss@example.com")


@pytest.fixture
def admin_client(admin_user: User) -> APIClient:
    return signed_in_client(admin_user)


@pytest.fixture
def anon_client() -> APIClient:
    return APIClient()
