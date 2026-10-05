from typing import Any

import pytest
from django_otp.plugins.otp_totp.models import TOTPDevice
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import Role
from apps.core.models import AuditLog

from .conftest import add_totp

URL = "/api/v1/admin/users"


@pytest.mark.django_db
def test_create_user_with_role(admin_client: APIClient) -> None:
    res = admin_client.post(
        URL,
        {
            "email": "mechanic@example.com",
            "first_name": "Sam",
            "last_name": "Wrench",
            "role": "service",
            "password": "Hydraulic-Pump-2026",
        },
        format="json",
    )
    assert res.status_code == 201, res.json()
    assert "password" not in res.json()
    user = User.objects.get(email="mechanic@example.com")
    assert user.role == Role.SERVICE
    assert user.check_password("Hydraulic-Pump-2026")
    entry = AuditLog.objects.get(action="create", object_id=str(user.pk))
    assert entry.actor is not None and entry.actor.email == "boss@example.com"


@pytest.mark.django_db
def test_create_user_validation(admin_client: APIClient, make_user: Any) -> None:
    make_user(email="taken@example.com")
    dup = admin_client.post(
        URL,
        {"email": "TAKEN@example.com", "role": "parts", "password": "Long-Enough-Pass-77"},
        format="json",
    )
    assert dup.status_code == 400
    assert "email" in dup.json()["fields"]
    weak = admin_client.post(
        URL, {"email": "a@example.com", "role": "parts", "password": "123"}, format="json"
    )
    assert "password" in weak.json()["fields"]
    no_pw = admin_client.post(URL, {"email": "b@example.com", "role": "parts"}, format="json")
    assert "password" in no_pw.json()["fields"]
    bad_role = admin_client.post(
        URL,
        {"email": "c@example.com", "role": "owner", "password": "Long-Enough-Pass-77"},
        format="json",
    )
    assert "role" in bad_role.json()["fields"]


@pytest.mark.django_db
def test_list_search_and_filter(admin_client: APIClient, make_user: Any) -> None:
    make_user(Role.PARTS, email="parts.person@example.com")
    make_user(Role.SALES, email="seller@example.com")
    assert admin_client.get(URL).json()["count"] == 3
    assert admin_client.get(URL + "?role=parts").json()["count"] == 1
    results = admin_client.get(URL + "?q=seller").json()["results"]
    assert [u["email"] for u in results] == ["seller@example.com"]


@pytest.mark.django_db
def test_change_role_is_audited(admin_client: APIClient, make_user: Any) -> None:
    user = make_user(Role.READ_ONLY)
    res = admin_client.patch(f"{URL}/{user.pk}", {"role": "sales"}, format="json")
    assert res.status_code == 200
    entry = AuditLog.objects.filter(action="update", object_id=str(user.pk)).latest("id")
    assert entry.before["role"] == "read_only"
    assert entry.after["role"] == "sales"


@pytest.mark.django_db
def test_admin_cannot_demote_or_remove_self(admin_client: APIClient, admin_user: User) -> None:
    res = admin_client.patch(f"{URL}/{admin_user.pk}", {"role": "sales"}, format="json")
    assert res.status_code == 400
    res = admin_client.patch(f"{URL}/{admin_user.pk}", {"is_active": False}, format="json")
    assert res.status_code == 400
    assert admin_client.delete(f"{URL}/{admin_user.pk}").status_code == 400


@pytest.mark.django_db
def test_removing_another_admin_is_allowed(admin_client: APIClient, make_user: Any) -> None:
    other = make_user(Role.ADMIN)
    # Two admins: removing one is fine.
    assert admin_client.delete(f"{URL}/{other.pk}").status_code == 204


@pytest.mark.django_db
def test_soft_delete_and_restore(admin_client: APIClient, make_user: Any) -> None:
    user = make_user(Role.PARTS)
    assert admin_client.delete(f"{URL}/{user.pk}").status_code == 204
    assert admin_client.get(URL).json()["count"] == 1
    listed = admin_client.get(URL + "?include_deleted=1").json()["results"]
    assert any(u["id"] == str(user.pk) and u["is_deleted"] for u in listed)
    res = admin_client.post(f"{URL}/{user.pk}/restore")
    assert res.status_code == 200
    assert res.json()["is_active"] is True
    assert User.objects.filter(pk=user.pk).exists()


@pytest.mark.django_db
def test_reset_two_factor(admin_client: APIClient, make_user: Any) -> None:
    user = make_user(Role.SALES)
    add_totp(user)
    res = admin_client.post(f"{URL}/{user.pk}/reset-2fa")
    assert res.status_code == 200
    assert res.json()["two_factor_enabled"] is False
    assert not TOTPDevice.objects.filter(user=user, confirmed=True).exists()


@pytest.mark.django_db
def test_admin_sets_new_password(admin_client: APIClient, make_user: Any) -> None:
    user = make_user()
    res = admin_client.patch(
        f"{URL}/{user.pk}", {"password": "Fresh-Password-For-You-1"}, format="json"
    )
    assert res.status_code == 200
    user.refresh_from_db()
    assert user.check_password("Fresh-Password-For-You-1")
    assert AuditLog.objects.filter(action="password_change", object_id=str(user.pk)).exists()
