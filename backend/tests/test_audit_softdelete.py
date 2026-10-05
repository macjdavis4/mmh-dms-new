from typing import Any

import pytest
from django.db import DatabaseError, connection, transaction

from apps.accounts.models import User
from apps.accounts.roles import Role
from apps.core.context import acting_as
from apps.core.models import AuditBypassError, AuditLog, FeatureFlag, SiteSettings


@pytest.mark.django_db
def test_create_and_update_are_audited_with_before_and_after(make_user: Any) -> None:
    actor = make_user(Role.ADMIN)
    with acting_as(actor, source="web", request_id="req-12345678"):
        flag = FeatureFlag.objects.create(key="units", description="Units module")
        flag.enabled = True
        flag.save()

    entries = list(AuditLog.objects.filter(object_id=str(flag.pk)).order_by("id"))
    assert [e.action for e in entries] == ["create", "update"]
    created, updated = entries
    assert created.actor == actor
    assert created.after["key"] == "units"
    assert created.request_id == "req-12345678"
    assert updated.before == {"enabled": False}
    assert updated.after == {"enabled": True}
    assert updated.changed_fields == ["enabled"]
    flag.refresh_from_db()
    assert flag.created_by == actor
    assert flag.updated_by == actor


@pytest.mark.django_db
def test_save_without_changes_writes_no_audit_row() -> None:
    flag = FeatureFlag.objects.create(key="x")
    before = AuditLog.objects.count()
    flag.save()
    assert AuditLog.objects.count() == before


@pytest.mark.django_db
def test_passwords_never_reach_the_audit_log(make_user: Any) -> None:
    user = make_user()
    user.set_password("Another-Long-Password-1")
    user.save()
    for entry in AuditLog.objects.filter(object_id=str(user.pk)):
        assert "password" not in (entry.after or {})
        assert "password" not in (entry.before or {})


@pytest.mark.django_db
def test_soft_delete_hides_row_and_restore_brings_it_back(make_user: Any) -> None:
    user = make_user(Role.SALES)
    user.delete()
    assert not User.objects.filter(pk=user.pk).exists()
    gone = User.all_objects.get(pk=user.pk)
    assert gone.is_deleted and not gone.is_active
    gone.restore()
    assert User.objects.filter(pk=user.pk).exists()
    actions = list(
        AuditLog.objects.filter(object_id=str(user.pk)).order_by("id").values_list("action", flat=True)
    )
    assert actions[-2:] == ["soft_delete", "restore"]


@pytest.mark.django_db
def test_bulk_update_and_delete_are_refused(make_user: Any) -> None:
    make_user()
    with pytest.raises(AuditBypassError):
        User.objects.all().update(first_name="x")
    with pytest.raises(AuditBypassError):
        User.objects.all().delete()
    with pytest.raises(AuditBypassError):
        FeatureFlag.objects.create(key="y").delete()


@pytest.mark.django_db
def test_database_refuses_hard_delete_of_soft_delete_tables(make_user: Any) -> None:
    make_user()
    with pytest.raises(DatabaseError, match="soft delete only"), transaction.atomic():
        with connection.cursor() as cur:
            cur.execute("DELETE FROM accounts_user")


@pytest.mark.django_db
def test_database_refuses_editing_or_deleting_audit_rows() -> None:
    FeatureFlag.objects.create(key="z")
    with pytest.raises(DatabaseError, match="append only"), transaction.atomic():
        with connection.cursor() as cur:
            cur.execute("UPDATE core_auditlog SET object_repr = 'tampered'")
    with pytest.raises(DatabaseError, match="append only"), transaction.atomic():
        with connection.cursor() as cur:
            cur.execute("DELETE FROM core_auditlog")
    entry = AuditLog.objects.first()
    assert entry is not None
    with pytest.raises(AuditBypassError):
        entry.save()
    with pytest.raises(AuditBypassError):
        entry.delete()


@pytest.mark.django_db
def test_site_settings_is_a_singleton() -> None:
    first = SiteSettings.load()
    second = SiteSettings.load()
    assert first.pk == second.pk == SiteSettings.SINGLETON_ID
    with pytest.raises(DatabaseError), transaction.atomic():
        import uuid

        SiteSettings.objects.create(id=uuid.uuid4())


@pytest.mark.django_db
def test_user_email_is_unique_regardless_of_case(make_user: Any) -> None:
    make_user(email="Pat@Example.com")
    with pytest.raises(DatabaseError), transaction.atomic():
        make_user(email="pat@example.com")


@pytest.mark.django_db
def test_invalid_role_rejected_by_database(make_user: Any) -> None:
    with pytest.raises(DatabaseError), transaction.atomic():
        make_user(role="owner")


@pytest.mark.django_db
def test_feature_flag_role_targeting(make_user: Any) -> None:
    flag = FeatureFlag.objects.create(key="beta", enabled=True, roles=["sales"])
    assert flag.is_on_for(make_user(Role.SALES))
    assert not flag.is_on_for(make_user(Role.PARTS))
    flag.enabled = False
    assert not flag.is_on_for(make_user(Role.SALES))
