from typing import Any

import pytest
from django_otp.oath import totp
from django_otp.plugins.otp_static.models import StaticDevice
from django_otp.plugins.otp_totp.models import TOTPDevice
from rest_framework.test import APIClient

from apps.accounts.roles import Role
from apps.core.models import AuditLog

from .conftest import PASSWORD, add_totp, signed_in_client


def code_for(device: TOTPDevice) -> str:
    return f"{totp(device.bin_key, step=device.step, t0=device.t0, digits=device.digits):06d}"


def login(client: APIClient, email: str, password: str = PASSWORD) -> Any:
    return client.post("/api/v1/auth/login", {"email": email, "password": password}, format="json")


@pytest.mark.django_db
def test_me_when_signed_out(anon_client: APIClient) -> None:
    assert anon_client.get("/api/v1/auth/me").json() == {"authenticated": False}


@pytest.mark.django_db
def test_login_without_2fa_signs_in_and_is_audited(make_user: Any, anon_client: APIClient) -> None:
    user = make_user(Role.SALES)
    res = login(anon_client, user.email.upper())  # email is case-insensitive
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["user"]["role"] == "sales"
    assert body["user"]["can_see_pricing"] is True
    assert anon_client.get("/api/v1/auth/me").json()["authenticated"] is True
    assert AuditLog.objects.filter(action="login", actor=user).exists()


@pytest.mark.django_db
def test_wrong_password_is_rejected_and_audited(make_user: Any, anon_client: APIClient) -> None:
    user = make_user()
    res = login(anon_client, user.email, "nope")
    assert res.status_code == 400
    assert res.json()["code"] == "invalid_credentials"
    assert AuditLog.objects.filter(action="login_failed", object_repr=user.email).exists()


@pytest.mark.django_db
def test_unknown_and_inactive_users_cannot_sign_in(make_user: Any, anon_client: APIClient) -> None:
    assert login(anon_client, "ghost@example.com").status_code == 400
    user = make_user(is_active=False)
    assert login(anon_client, user.email).status_code == 400
    deleted = make_user()
    deleted.soft_delete()
    assert login(anon_client, deleted.email).status_code == 400


@pytest.mark.django_db
def test_account_locks_after_five_failures(make_user: Any, anon_client: APIClient) -> None:
    user = make_user()
    for _ in range(5):
        login(anon_client, user.email, "wrong")
    res = login(anon_client, user.email)  # even the right password is refused now
    assert res.status_code == 429
    assert res.json()["code"] == "locked_out"
    assert AuditLog.objects.filter(action="locked_out").exists()


@pytest.mark.django_db
def test_admin_can_unlock_a_locked_account(
    make_user: Any, anon_client: APIClient, admin_client: APIClient
) -> None:
    user = make_user()
    for _ in range(5):
        login(anon_client, user.email, "wrong")
    assert admin_client.post(f"/api/v1/admin/users/{user.pk}/unlock").status_code == 200
    assert login(APIClient(), user.email).status_code == 200


@pytest.mark.django_db
def test_two_step_login_with_authenticator_code(
    make_user: Any, anon_client: APIClient, time_machine: Any
) -> None:
    time_machine.move_to("2026-03-02 09:00:00", tick=False)
    user = make_user(Role.ADMIN)
    device = add_totp(user)
    res = login(anon_client, user.email)
    assert res.json() == {"status": "otp_required"}
    # Not signed in until the code is entered.
    assert anon_client.get("/api/v1/auth/me").json()["authenticated"] is False
    assert anon_client.get("/api/v1/admin/users").status_code == 401

    bad = anon_client.post("/api/v1/auth/login/verify", {"code": "000000"}, format="json")
    assert bad.status_code == 400
    time_machine.shift(5)  # django-otp backs off for a moment after a wrong code

    ok = anon_client.post("/api/v1/auth/login/verify", {"code": code_for(device)}, format="json")
    assert ok.status_code == 200
    assert ok.json()["two_factor"]["verified"] is True
    assert anon_client.get("/api/v1/admin/users").status_code == 200


@pytest.mark.django_db
def test_recovery_code_works_once(make_user: Any) -> None:
    user = make_user(Role.PARTS)
    add_totp(user)
    static = StaticDevice.objects.create(user=user, name="Recovery codes", confirmed=True)
    static.token_set.create(token="abcd-1234")

    client = APIClient()
    login(client, user.email)
    res = client.post("/api/v1/auth/login/verify", {"code": "ABCD-1234"}, format="json")
    assert res.status_code == 200
    assert AuditLog.objects.filter(action="recovery_code_used", actor=user).exists()

    again = APIClient()
    login(again, user.email)
    assert (
        again.post("/api/v1/auth/login/verify", {"code": "abcd-1234"}, format="json").status_code
        == 400
    )


@pytest.mark.django_db
def test_verify_without_password_step_is_rejected(anon_client: APIClient) -> None:
    res = anon_client.post("/api/v1/auth/login/verify", {"code": "123456"}, format="json")
    assert res.status_code == 400
    assert res.json()["code"] == "otp_expired"


@pytest.mark.django_db
def test_verify_window_expires(make_user: Any, anon_client: APIClient, time_machine: Any) -> None:
    user = make_user(Role.ADMIN)
    device = add_totp(user)
    time_machine.move_to("2026-01-01 12:00:00", tick=False)
    login(anon_client, user.email)
    time_machine.move_to("2026-01-01 12:06:00", tick=False)
    res = anon_client.post("/api/v1/auth/login/verify", {"code": code_for(device)}, format="json")
    assert res.json()["code"] == "otp_expired"


@pytest.mark.django_db
def test_admin_without_2fa_must_set_it_up_before_anything_else(
    make_user: Any, time_machine: Any
) -> None:
    time_machine.move_to("2026-03-02 09:00:00", tick=False)
    admin = make_user(Role.ADMIN)
    client = APIClient()
    res = login(client, admin.email)
    assert res.status_code == 200
    assert res.json()["two_factor"]["setup_needed"] is True

    blocked = client.get("/api/v1/admin/users")
    assert blocked.status_code == 403
    assert blocked.json()["code"] == "two_factor_setup_required"
    assert client.get("/api/v1/search?q=abc").status_code == 403

    setup = client.post("/api/v1/auth/2fa/setup")
    assert setup.status_code == 200
    body = setup.json()
    assert body["otpauth_url"].startswith("otpauth://totp/")
    assert body["qr_code"].startswith("data:image/svg+xml;base64,")

    device = TOTPDevice.objects.get(user=admin, confirmed=False)
    wrong = client.post("/api/v1/auth/2fa/confirm", {"code": "000000"}, format="json")
    assert wrong.status_code == 400
    time_machine.shift(5)
    done = client.post("/api/v1/auth/2fa/confirm", {"code": code_for(device)}, format="json")
    assert done.status_code == 200
    assert len(done.json()["recovery_codes"]) == 10
    assert done.json()["two_factor"]["verified"] is True
    assert client.get("/api/v1/admin/users").status_code == 200
    assert AuditLog.objects.filter(action="2fa_enabled", object_id=str(admin.pk)).exists()


@pytest.mark.django_db
def test_admin_cannot_turn_off_2fa(admin_user: Any, admin_client: APIClient) -> None:
    res = admin_client.post("/api/v1/auth/2fa/disable", {"password": PASSWORD}, format="json")
    assert res.status_code == 403


@pytest.mark.django_db
def test_other_roles_can_turn_2fa_on_and_off(make_user: Any) -> None:
    user = make_user(Role.SERVICE)
    client = signed_in_client(user)
    assert client.get("/api/v1/auth/me").json()["two_factor"]["required"] is False
    client.post("/api/v1/auth/2fa/setup")
    device = TOTPDevice.objects.get(user=user, confirmed=False)
    assert (
        client.post(
            "/api/v1/auth/2fa/confirm", {"code": code_for(device)}, format="json"
        ).status_code
        == 200
    )
    wrong = client.post("/api/v1/auth/2fa/disable", {"password": "bad"}, format="json")
    assert wrong.status_code == 400
    ok = client.post("/api/v1/auth/2fa/disable", {"password": PASSWORD}, format="json")
    assert ok.status_code == 200
    assert ok.json()["two_factor"]["enabled"] is False


@pytest.mark.django_db
def test_recovery_codes_can_be_regenerated(make_user: Any) -> None:
    user = make_user(Role.ADMIN)
    client = signed_in_client(user)
    res = client.post("/api/v1/auth/2fa/recovery-codes", {"password": PASSWORD}, format="json")
    assert res.status_code == 200
    assert len(set(res.json()["recovery_codes"])) == 10


@pytest.mark.django_db
def test_password_change(make_user: Any) -> None:
    user = make_user(Role.SALES)
    client = signed_in_client(user)
    bad = client.post(
        "/api/v1/auth/password",
        {"current_password": "wrong", "new_password": "Brand-New-Password-9"},
        format="json",
    )
    assert bad.status_code == 400
    weak = client.post(
        "/api/v1/auth/password",
        {"current_password": PASSWORD, "new_password": "short"},
        format="json",
    )
    assert weak.status_code == 400
    assert "new_password" in weak.json()["fields"]
    ok = client.post(
        "/api/v1/auth/password",
        {"current_password": PASSWORD, "new_password": "Brand-New-Password-9"},
        format="json",
    )
    assert ok.status_code == 204
    # Still signed in after the change.
    assert client.get("/api/v1/auth/me").json()["authenticated"] is True
    assert AuditLog.objects.filter(action="password_change", object_id=str(user.pk)).exists()


@pytest.mark.django_db
def test_logout(make_user: Any) -> None:
    client = signed_in_client(make_user())
    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.get("/api/v1/auth/me").json()["authenticated"] is False


@pytest.mark.django_db
def test_csrf_is_enforced_for_signed_in_writes(make_user: Any) -> None:
    user = make_user(Role.ADMIN)
    add_totp(user)
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(user)
    res = client.post("/api/v1/auth/password", {}, format="json")
    assert res.status_code == 403
    assert "CSRF" in res.json()["detail"]


@pytest.mark.django_db
def test_csrf_endpoint_sets_cookie(anon_client: APIClient) -> None:
    res = anon_client.get("/api/v1/auth/csrf")
    assert res.status_code == 204
    assert "mmh_csrftoken" in res.cookies
