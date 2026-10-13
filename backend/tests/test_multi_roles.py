"""People can hold several roles: any mix of sales, service and parts. Admin and
read-only stand alone. The database refuses anything else."""

from collections.abc import Callable
from itertools import combinations
from typing import Any

import pytest
from django.db import IntegrityError, connection, transaction
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import (
    COMBINABLE_ROLES,
    Role,
    has_any_role,
    normalize_roles,
    primary_role,
    role_labels,
    roles_problem,
)
from apps.core.models import AuditLog, FeatureFlag

from .conftest import signed_in_client

URL = "/api/v1/admin/users"


def _raw_set_roles(user: User, roles: list[str]) -> None:
    """Straight to the database, the way the previous version (or a person with a
    SQL prompt) would, skipping the app's own checks."""
    with connection.cursor() as cur:
        cur.execute(
            "UPDATE accounts_user SET roles = %s::varchar(20)[] WHERE id = %s", [roles, user.pk]
        )


COMBOS = [
    [Role.SALES, Role.SERVICE],
    [Role.SALES, Role.PARTS],
    [Role.SERVICE, Role.PARTS],
    [Role.SALES, Role.SERVICE, Role.PARTS],
]


# --- the rules --------------------------------------------------------------------


@pytest.mark.parametrize("roles", [[r] for r in Role.values] + COMBOS)
def test_allowed_combinations(roles: list[str]) -> None:
    assert roles_problem(roles) is None


@pytest.mark.parametrize(
    "roles",
    [
        [],
        ["owner"],
        [Role.ADMIN, Role.SALES],
        [Role.ADMIN, Role.READ_ONLY],
        [Role.READ_ONLY, Role.PARTS],
        [Role.SERVICE, Role.READ_ONLY, Role.SALES],
        [Role.ADMIN, Role.SALES, Role.SERVICE, Role.PARTS],
    ],
)
def test_refused_combinations(roles: list[str]) -> None:
    assert roles_problem(roles)


def test_helpers() -> None:
    assert normalize_roles(["parts", "sales", "parts"]) == ["sales", "parts"]
    assert primary_role(["parts", "service"]) == "service"
    assert primary_role([]) == "read_only"
    assert role_labels(["parts", "sales"]) == "Sales, Parts"
    assert {Role.SALES, Role.SERVICE, Role.PARTS} == COMBINABLE_ROLES


def test_has_any_role_accepts_single_role_objects() -> None:
    class Legacy:
        role = "sales"

    assert has_any_role(Legacy(), {"sales", "admin"})
    assert not has_any_role(Legacy(), {"parts"})
    assert not has_any_role(object(), {"parts"})


# --- the database refuses bad data on its own ---------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "roles",
    [
        [Role.ADMIN, Role.SALES],
        [Role.READ_ONLY, Role.PARTS],
        [Role.ADMIN, Role.READ_ONLY],
        ["owner"],
    ],
)
def test_database_refuses_bad_roles(make_user: Callable[..., User], roles: list[str]) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        make_user(Role.SALES, roles=roles)
    ok = make_user(Role.SALES)
    with pytest.raises(IntegrityError), transaction.atomic():
        _raw_set_roles(ok, roles)  # even bypassing save()


@pytest.mark.django_db
@pytest.mark.parametrize("roles", COMBOS)
def test_combined_user_is_stored_in_canonical_order(
    make_user: Callable[..., User], roles: list[str]
) -> None:
    user = make_user(Role.PARTS, roles=list(reversed(roles)))
    user.refresh_from_db()
    assert user.roles == normalize_roles(roles)
    assert user.role == primary_role(roles)  # kept for the previous version
    assert not user.requires_two_factor
    assert not user.is_staff
    assert not user.is_superuser


@pytest.mark.django_db
def test_single_role_users_still_work_and_old_rows_fall_back(
    make_user: Callable[..., User],
) -> None:
    sales = make_user(Role.SALES)
    assert sales.roles == ["sales"]
    # A row written by the previous version has no `roles`: it still works.
    _raw_set_roles(sales, [])
    sales.refresh_from_db()
    assert sales.effective_roles == ["sales"]
    assert has_any_role(sales, {"sales"})


@pytest.mark.django_db
def test_price_visibility_and_two_factor_follow_any_role(make_user: Callable[..., User]) -> None:
    assert make_user(Role.PARTS, roles=[Role.PARTS, Role.SALES]).can_see_pricing
    assert not make_user(Role.PARTS, roles=[Role.PARTS, Role.SERVICE]).can_see_pricing
    assert make_user(Role.ADMIN).requires_two_factor


@pytest.mark.django_db
def test_feature_flag_targeting_uses_any_role(make_user: Callable[..., User]) -> None:
    flag = FeatureFlag.objects.create(key="beta-multi", enabled=True, roles=["service"])
    assert flag.is_on_for(make_user(Role.PARTS, roles=[Role.PARTS, Role.SERVICE]))
    assert not flag.is_on_for(make_user(Role.PARTS, roles=[Role.PARTS, Role.SALES]))


@pytest.mark.django_db
def test_audit_log_records_all_roles(make_user: Callable[..., User]) -> None:
    from apps.core.context import acting_as

    actor = make_user(Role.SALES, roles=[Role.SALES, Role.PARTS])
    with acting_as(user=actor, source="api"):
        user = make_user(Role.SERVICE)
    entry = AuditLog.objects.filter(object_id=str(user.pk), action="create").first()
    assert entry is not None
    assert entry.actor_role == "sales,parts"


# --- a combined user can do what each of their roles can do ---------------------------

ENDPOINTS: list[tuple[str, str, dict[str, Any] | None]] = [
    ("get", "/api/v1/units", None),
    ("post", "/api/v1/units", {}),
    ("get", "/api/v1/customers", None),
    ("post", "/api/v1/customers", {}),
    ("get", "/api/v1/parts", None),
    ("post", "/api/v1/parts", {}),
    ("get", "/api/v1/parts-invoices", None),
    ("post", "/api/v1/parts-invoices", {}),
    ("get", "/api/v1/stock-movements", None),
    ("get", "/api/v1/work-orders", None),
    ("post", "/api/v1/work-orders", {}),
    ("get", "/api/v1/maintenance-plans", None),
    ("get", "/api/v1/quotes", None),
    ("post", "/api/v1/quotes", {}),
    ("get", "/api/v1/sales", None),
    ("get", "/api/v1/unit-changes", None),
    ("get", "/api/v1/imports/batches", None),
    ("get", "/api/v1/admin/api-keys", None),
    ("get", "/api/v1/admin/users", None),
    ("get", "/api/v1/reports", None),
    ("get", "/api/v1/dashboard", None),
]


def _open_endpoints(client: APIClient) -> set[tuple[str, str]]:
    """Endpoints this person gets past the permission check on (anything but 401/403)."""
    allowed = set()
    for method, path, body in ENDPOINTS:
        res = getattr(client, method)(path, body, format="json")
        if res.status_code not in (401, 403):
            allowed.add((method, path))
    return allowed


@pytest.mark.django_db
def test_combined_user_gets_the_union_of_their_roles(make_user: Callable[..., User]) -> None:
    single = {
        r: _open_endpoints(signed_in_client(make_user(r)))
        for r in (Role.SALES, Role.SERVICE, Role.PARTS)
    }
    # The roles really do differ, or this test would prove nothing.
    assert len({frozenset(v) for v in single.values()}) == 3
    for combo in COMBOS:
        got = _open_endpoints(signed_in_client(make_user(combo[0], roles=combo)))
        expected = set().union(*(single[r] for r in combo))
        assert got == expected, combo


@pytest.mark.django_db
def test_combined_user_is_still_not_an_admin(make_user: Callable[..., User]) -> None:
    client = signed_in_client(make_user(Role.SALES, roles=[Role.SALES, Role.SERVICE, Role.PARTS]))
    assert client.get("/api/v1/admin/users").status_code == 403
    assert client.get("/api/v1/admin/audit-log").status_code == 403
    assert client.get("/django-admin/").status_code in (302, 403)


@pytest.mark.django_db
def test_me_reports_all_roles(make_user: Callable[..., User]) -> None:
    user = make_user(Role.PARTS, roles=[Role.PARTS, Role.SALES])
    me = signed_in_client(user).get("/api/v1/auth/me").json()["user"]
    assert me["roles"] == ["sales", "parts"]
    assert me["role_label"] == "Sales, Parts"
    assert me["role"] == "sales"
    assert me["can_see_pricing"] is True


# --- managing roles as an admin ---------------------------------------------------------


def _new_user(**extra: Any) -> dict[str, Any]:
    return {
        "email": "multi@example.com",
        "first_name": "Pat",
        "last_name": "Multi",
        "password": "Hydraulic-Pump-2026",
        **extra,
    }


@pytest.mark.django_db
@pytest.mark.parametrize("roles", COMBOS)
def test_admin_creates_user_with_several_roles(admin_client: APIClient, roles: list[str]) -> None:
    res = admin_client.post(URL, _new_user(roles=list(reversed(roles))), format="json")
    assert res.status_code == 201, res.json()
    body = res.json()
    assert body["roles"] == normalize_roles(roles)
    assert body["role_label"] == role_labels(roles)
    assert User.objects.get(email="multi@example.com").roles == normalize_roles(roles)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "roles",
    [
        [Role.ADMIN, Role.SALES],
        [Role.READ_ONLY, Role.SERVICE],
        [Role.ADMIN, Role.READ_ONLY],
        [],
        ["owner"],
    ],
)
def test_admin_cannot_save_a_bad_combination(admin_client: APIClient, roles: list[str]) -> None:
    res = admin_client.post(URL, _new_user(roles=roles), format="json")
    assert res.status_code == 400
    assert "roles" in res.json()["fields"]
    assert not User.objects.filter(email="multi@example.com").exists()


@pytest.mark.django_db
def test_message_explains_why_admin_cannot_combine(admin_client: APIClient) -> None:
    res = admin_client.post(URL, _new_user(roles=["admin", "parts"]), format="json")
    assert "cannot be combined" in res.json()["fields"]["roles"][0]


@pytest.mark.django_db
def test_old_clients_can_still_send_a_single_role(admin_client: APIClient) -> None:
    res = admin_client.post(URL, _new_user(role="service"), format="json")
    assert res.status_code == 201, res.json()
    assert res.json()["roles"] == ["service"]


@pytest.mark.django_db
def test_admin_changes_a_users_roles(admin_client: APIClient, make_user: Any) -> None:
    user = make_user(Role.SALES)
    res = admin_client.patch(f"{URL}/{user.pk}", {"roles": ["sales", "parts"]}, format="json")
    assert res.status_code == 200, res.json()
    user.refresh_from_db()
    assert user.roles == ["sales", "parts"]
    bad = admin_client.patch(f"{URL}/{user.pk}", {"roles": ["admin", "parts"]}, format="json")
    assert bad.status_code == 400
    user.refresh_from_db()
    assert user.roles == ["sales", "parts"]
    # Changing other details leaves the roles alone.
    admin_client.patch(f"{URL}/{user.pk}", {"first_name": "Renamed"}, format="json")
    user.refresh_from_db()
    assert user.roles == ["sales", "parts"]
    entry = AuditLog.objects.filter(object_id=str(user.pk), action="update").first()
    assert entry is not None


@pytest.mark.django_db
def test_promoting_to_admin_replaces_the_other_roles(
    admin_client: APIClient, make_user: Any
) -> None:
    user = make_user(Role.SALES, roles=[Role.SALES, Role.PARTS])
    res = admin_client.patch(f"{URL}/{user.pk}", {"roles": ["admin"]}, format="json")
    assert res.status_code == 200
    user.refresh_from_db()
    assert user.roles == ["admin"]
    assert user.requires_two_factor
    assert user.is_superuser


@pytest.mark.django_db
def test_cannot_remove_your_own_admin_role(admin_client: APIClient, admin_user: User) -> None:
    res = admin_client.patch(f"{URL}/{admin_user.pk}", {"roles": ["sales", "parts"]}, format="json")
    assert res.status_code == 400
    assert "roles" in res.json()["fields"]


@pytest.mark.django_db
def test_demoting_another_admin_keeps_one_admin(
    admin_client: APIClient, admin_user: User, make_user: Any
) -> None:
    other = make_user(Role.ADMIN, email="second@example.com")
    ok = admin_client.patch(f"{URL}/{other.pk}", {"roles": ["parts", "service"]}, format="json")
    assert ok.status_code == 200, ok.json()
    other.refresh_from_db()
    assert other.roles == ["service", "parts"]
    assert not other.is_superuser
    # `role` stays in step, so "who are the admins?" is still answered correctly.
    assert list(User.objects.filter(role=Role.ADMIN)) == [admin_user]
    # And the remaining admin cannot step down.
    own = admin_client.patch(f"{URL}/{admin_user.pk}", {"roles": ["sales"]}, format="json")
    assert own.status_code == 400


@pytest.mark.django_db
def test_filter_by_role_finds_people_holding_it_among_others(
    admin_client: APIClient, make_user: Any
) -> None:
    both = make_user(Role.SALES, roles=[Role.SALES, Role.PARTS], email="both@example.com")
    only_parts = make_user(Role.PARTS, email="parts@example.com")
    sales_only = make_user(Role.SALES, email="sales@example.com")
    parts = {u["email"] for u in admin_client.get(URL, {"role": "parts"}).json()["results"]}
    assert {both.email, only_parts.email} <= parts
    assert sales_only.email not in parts
    # A row from the previous version (no `roles`) is still found.
    _raw_set_roles(sales_only, [])
    sales = {u["email"] for u in admin_client.get(URL, {"role": "sales"}).json()["results"]}
    assert {both.email, sales_only.email} <= sales


@pytest.mark.django_db
def test_combinations_of_three_pairs_are_exhaustive() -> None:
    # Guards the COMBOS list above: every non-empty mix of the three combinable roles.
    expected = [
        list(c) for n in (2, 3) for c in combinations([Role.SALES, Role.SERVICE, Role.PARTS], n)
    ]
    assert sorted(map(tuple, COMBOS)) == sorted(map(tuple, expected))
