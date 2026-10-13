"""Regression tests for the October 2026 security audit (docs/SECURITY_AUDIT.md).

Each test names the attack it proves is closed."""

from __future__ import annotations

import io
from decimal import Decimal
from typing import Any

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django_otp.oath import totp
from django_otp.plugins.otp_static.models import StaticDevice
from django_otp.plugins.otp_totp.models import TOTPDevice
from PIL import Image
from rest_framework.test import APIClient

from apps.accounts.roles import Role
from apps.core.models import AuditLog, FeatureFlag
from apps.customers.models import Customer
from apps.imports.models import ImportBatch
from apps.ops.paper import _safe
from apps.units.models import Unit

from .conftest import PASSWORD, signed_in_client
from .test_imports import ROW, make_csv, upload

BATCHES = "/api/v1/imports/batches"


def _code(device: TOTPDevice) -> str:
    return f"{totp(device.bin_key, device.step, device.t0, device.digits, device.drift):06d}"


# --- 2FA --------------------------------------------------------------------------------------


@pytest.mark.django_db
def test_reset_2fa_deletes_devices_so_old_phone_cannot_sign_in_to_django_admin(
    admin_client: APIClient, make_user: Any
) -> None:
    victim = make_user(Role.ADMIN)
    old = TOTPDevice.objects.create(user=victim, name="old phone", confirmed=True)
    codes = StaticDevice.objects.create(user=victim, name="Recovery codes", confirmed=True)
    codes.token_set.create(token="aaaa-bbbb")
    assert admin_client.post(f"/api/v1/admin/users/{victim.pk}/reset-2fa").status_code == 200
    assert not TOTPDevice.objects.filter(user=victim).exists()
    assert not StaticDevice.objects.filter(user=victim).exists()

    # The attacker holds the old phone and the password.
    browser = Client()
    browser.post(
        "/django-admin/login/?next=/django-admin/",
        {
            "username": victim.email,
            "password": PASSWORD,
            "otp_device": old.persistent_id,
            "otp_token": _code(old),
        },
    )
    assert browser.get("/api/v1/admin/users").status_code in (401, 403)


@pytest.mark.django_db
def test_django_admin_refuses_an_unconfirmed_device(make_user: Any) -> None:
    admin = make_user(Role.ADMIN)
    TOTPDevice.objects.create(user=admin, name="current", confirmed=True)
    pending = TOTPDevice.objects.create(user=admin, name="half set up", confirmed=False)
    browser = Client()
    browser.post(
        "/django-admin/login/?next=/django-admin/",
        {
            "username": admin.email,
            "password": PASSWORD,
            "otp_device": pending.persistent_id,
            "otp_token": _code(pending),
        },
    )
    assert browser.get("/api/v1/admin/users").status_code in (401, 403)


@pytest.mark.django_db
def test_reset_2fa_signs_the_person_out_everywhere(admin_client: APIClient, make_user: Any) -> None:
    victim = make_user(Role.ADMIN)
    stolen_laptop = signed_in_client(victim)
    assert stolen_laptop.get("/api/v1/admin/users").status_code == 200
    assert admin_client.post(f"/api/v1/admin/users/{victim.pk}/reset-2fa").status_code == 200
    me = stolen_laptop.get("/api/v1/auth/me").json()
    assert me["authenticated"] is False
    # The admin who did the reset stays signed in.
    assert admin_client.get("/api/v1/admin/users").status_code == 200


@pytest.mark.django_db
def test_turning_2fa_off_deletes_devices(make_user: Any) -> None:
    user = make_user(Role.SALES)
    client = signed_in_client(user, verified=True)
    StaticDevice.objects.create(user=user, name="Recovery codes", confirmed=True)
    res = client.post("/api/v1/auth/2fa/disable", {"password": PASSWORD}, format="json")
    assert res.status_code == 200, res.content
    assert not TOTPDevice.objects.filter(user=user).exists()
    assert not StaticDevice.objects.filter(user=user).exists()


# --- Rate limits ------------------------------------------------------------------------------


@pytest.mark.django_db
def test_made_up_forwarded_for_header_does_not_reset_the_login_limit() -> None:
    client = APIClient()
    codes = [
        client.post(
            "/api/v1/auth/login",
            {"email": f"nobody{i}@example.com", "password": "wrong-password-123"},
            format="json",
            HTTP_X_FORWARDED_FOR=f"10.0.0.{i}",
            HTTP_X_REAL_IP="203.0.113.7",
        ).status_code
        for i in range(12)
    ]
    assert 429 in codes


@pytest.mark.django_db
def test_password_checks_inside_the_app_are_rate_limited(make_user: Any) -> None:
    client = signed_in_client(make_user(Role.SERVICE))
    codes = [
        client.post(
            "/api/v1/auth/password",
            {"current_password": "guess-123456", "new_password": "Another-Long-Pass-2026"},
            format="json",
        ).status_code
        for _ in range(12)
    ]
    assert 429 in codes


# --- Imports ----------------------------------------------------------------------------------


@pytest.mark.django_db
def test_a_price_that_is_not_an_amount_never_lands_in_notes(client_for: Any) -> None:
    sales = client_for(Role.SALES)
    res = upload(sales, make_csv([{**ROW, "asking_price": "$41,750 OBO"}]))
    assert res.status_code == 201, res.content
    batch_id = res.json()["id"]
    rows = sales.get(f"{BATCHES}/{batch_id}/rows").json()["results"]
    assert rows[0]["status"] == "error"
    assert "41,750" not in str(rows[0])
    sales.post(f"{BATCHES}/{batch_id}/apply", {"skip_invalid": True}, format="json")
    assert not Unit.objects.filter(notes__contains="41,750").exists()


@pytest.mark.django_db
def test_service_cannot_download_or_change_someone_elses_import(client_for: Any) -> None:
    sales = client_for(Role.SALES)
    batch_id = upload(sales, make_csv([{**ROW, "asking_price": "38900"}])).json()["id"]
    service = client_for(Role.SERVICE)
    assert service.get(f"{BATCHES}/{batch_id}/original").status_code == 403
    for verb in ("validate", "apply", "discard"):
        assert service.post(f"{BATCHES}/{batch_id}/{verb}", {}, format="json").status_code == 403
    assert ImportBatch.objects.get(pk=batch_id).status == ImportBatch.Status.DRAFT
    # The person who uploaded it can still download it.
    res = sales.get(f"{BATCHES}/{batch_id}/original")
    assert res.status_code == 200
    assert res["Content-Disposition"].startswith("attachment")


# --- Removed records --------------------------------------------------------------------------


@pytest.mark.django_db
def test_removed_unit_cannot_be_edited_with_include_deleted(client_for: Any) -> None:
    unit = Unit.objects.create(model="G25N-7", serial_number="GONE-1")
    unit.soft_delete()
    service = client_for(Role.SERVICE)
    res = service.patch(
        f"/api/v1/units/{unit.pk}?include_deleted=1", {"notes": "edited"}, format="json"
    )
    assert res.status_code == 404
    unit.refresh_from_db()
    assert unit.notes == ""


# --- What each role sees ----------------------------------------------------------------------


@pytest.mark.django_db
def test_unit_history_hides_staff_ip_addresses_from_non_admins(
    client_for: Any, admin_client: APIClient
) -> None:
    unit = Unit.objects.create(model="35LN-9A", serial_number="HIST-1")
    AuditLog.objects.create(
        action=AuditLog.Action.UPDATE,
        content_type=ContentType.objects.get_for_model(Unit),
        object_id=str(unit.pk),
        ip="198.51.100.20",
    )
    rows = client_for(Role.READ_ONLY).get(f"/api/v1/units/{unit.pk}/history").json()
    assert rows and "198.51.100.20" not in str(rows)
    rows = admin_client.get(f"/api/v1/units/{unit.pk}/history").json()
    assert "198.51.100.20" in str(rows)


@pytest.mark.django_db
def test_search_respects_feature_flags_limited_to_some_roles(client_for: Any) -> None:
    Customer.objects.create(name="Katahdin Lumber")
    flag = FeatureFlag.objects.get(key="customers-units")
    flag.roles = [Role.ADMIN]
    flag.save()
    res = client_for(Role.PARTS).get("/api/v1/search", {"q": "Katahdin"})
    assert res.status_code == 200
    assert "Katahdin" not in str(res.json()["groups"])
    admin = client_for(Role.ADMIN).get("/api/v1/search", {"q": "Katahdin"})
    assert "Katahdin" in str(admin.json()["groups"])


@pytest.mark.django_db
def test_sales_cannot_put_someone_elses_name_on_a_quote(client_for: Any, make_user: Any) -> None:
    from .test_sales import QUOTES, quote_body

    customer = Customer.objects.create(name="Katahdin Lumber")
    other = make_user(Role.SALES)
    sales = client_for(Role.SALES)
    res = sales.post(QUOTES, {**quote_body(customer), "salesperson": str(other.pk)}, format="json")
    assert res.status_code == 400
    assert "salesperson" in res.json().get("fields", res.json())


# --- Files ------------------------------------------------------------------------------------


@pytest.mark.django_db
def test_tiny_file_claiming_a_huge_picture_is_refused(client_for: Any) -> None:
    buf = io.BytesIO()
    Image.new("1", (10_000, 10_000)).save(buf, "PNG")  # ~12 KB, 100 megapixels
    unit = Unit.objects.create(model="35LN-9A", serial_number="BOMB-1")
    res = client_for(Role.SERVICE).post(
        f"/api/v1/units/{unit.pk}/files",
        {"file": SimpleUploadedFile("x.png", buf.getvalue(), "image/png"), "kind": "photo"},
        format="multipart",
    )
    assert res.status_code == 400
    assert "too large" in res.content.decode()


def test_paper_backup_csv_neutralises_every_formula_start() -> None:
    for text in ("=HYPERLINK(1)", "+1+1", "-cmd", "@SUM(1)", "\t=1", "\r=1"):
        assert _safe(text).startswith("'")
    assert _safe("-12.50") == "-12.50"
    assert _safe(Decimal("3")) == "3"
