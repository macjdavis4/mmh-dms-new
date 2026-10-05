"""Every endpoint x every role. CLAUDE.md: each role can do only what it should."""

from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.accounts.roles import Role

ALL = [Role.ADMIN, Role.SALES, Role.SERVICE, Role.PARTS, Role.READ_ONLY]

# (method, path, body, roles allowed). Everyone else gets 403; anonymous gets 401.
ENDPOINTS: list[tuple[str, str, dict[str, Any] | None, set[str]]] = [
    ("get", "/api/v1/admin/users", None, {Role.ADMIN}),
    (
        "post",
        "/api/v1/admin/users",
        {"email": "new@example.com", "password": "Long-Enough-Pass-77", "role": "parts"},
        {Role.ADMIN},
    ),
    ("get", "/api/v1/admin/site-settings", None, {Role.ADMIN}),
    ("patch", "/api/v1/admin/site-settings", {"banner_message": "Hi"}, {Role.ADMIN}),
    ("get", "/api/v1/admin/audit-log", None, {Role.ADMIN}),
    ("get", "/api/v1/admin/health", None, {Role.ADMIN}),
    ("get", "/api/v1/search?q=35LN", None, set(ALL)),
    ("get", "/api/v1/feature-flags", None, set(ALL)),
    ("post", "/api/v1/auth/password", {}, set(ALL)),  # 400 (validation) for signed-in users
]


@pytest.mark.django_db
@pytest.mark.parametrize(("method", "path", "body", "allowed"), ENDPOINTS)
@pytest.mark.parametrize("role", ALL)
def test_role_matrix(
    client_for: Any, method: str, path: str, body: Any, allowed: set[str], role: str
) -> None:
    client: APIClient = client_for(role)
    res = getattr(client, method)(path, body, format="json")
    if role in allowed:
        assert res.status_code in (200, 201, 400), (role, path, res.status_code)
    else:
        assert res.status_code == 403, (role, path, res.status_code)


@pytest.mark.django_db
@pytest.mark.parametrize(("method", "path", "body", "allowed"), ENDPOINTS)
def test_anonymous_gets_401(
    anon_client: APIClient, method: str, path: str, body: Any, allowed: set[str]
) -> None:
    res = getattr(anon_client, method)(path, body, format="json")
    assert res.status_code == 401, (path, res.status_code)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "path", ["/api/v1/system/status", "/api/v1/auth/me", "/api/v1/auth/csrf", "/healthz", "/readyz"]
)
def test_public_endpoints(anon_client: APIClient, path: str) -> None:
    assert anon_client.get(path).status_code in (200, 204)


@pytest.mark.django_db
def test_django_admin_requires_verified_admin(make_user: Any) -> None:
    from .conftest import signed_in_client

    sales = signed_in_client(make_user(Role.SALES))
    assert sales.get("/django-admin/").status_code == 302  # to the admin login page
    unverified_admin = signed_in_client(make_user(Role.ADMIN), verified=False)
    assert unverified_admin.get("/django-admin/").status_code == 403
    admin = signed_in_client(make_user(Role.ADMIN))
    assert admin.get("/django-admin/").status_code == 200
