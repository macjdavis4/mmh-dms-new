from typing import Any

import pytest
from django.test import Client

from apps.core import health


@pytest.mark.django_db
def test_healthz_is_always_ok(client: Client) -> None:
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
    assert res["Cache-Control"].startswith("max-age=0")


@pytest.mark.django_db
def test_health_checks_ignore_the_host_header(client: Client) -> None:
    # Container probes use the container address, not the public hostname.
    assert client.get("/healthz", HTTP_HOST="app-green:8000").status_code == 200
    assert client.get("/readyz", HTTP_HOST="127.0.0.1:8000").status_code == 200
    assert client.get("/api/v1/system/status", HTTP_HOST="evil.example").status_code == 400


@pytest.mark.django_db
def test_readyz_ok_when_db_and_migrations_current(client: Client) -> None:
    health._migrations_current = False
    res = client.get("/readyz")
    assert res.status_code == 200
    assert res.json()["checks"] == {"database": "ok", "migrations": "ok"}


@pytest.mark.django_db
def test_readyz_fails_when_migrations_pending(client: Client, monkeypatch: Any) -> None:
    health._migrations_current = False
    monkeypatch.setattr(
        "django.db.migrations.executor.MigrationExecutor.migration_plan",
        lambda self, targets: [("fake", False)],
    )
    res = client.get("/readyz")
    assert res.status_code == 503
    assert res.json()["checks"]["migrations"] == "1 pending"


@pytest.mark.django_db
def test_readyz_fails_when_database_unreachable(client: Client, monkeypatch: Any) -> None:
    def boom() -> tuple[bool, str]:
        return False, "unreachable"

    monkeypatch.setattr(health, "_check_database", boom)
    res = client.get("/readyz")
    assert res.status_code == 503
    assert res.json()["checks"] == {"database": "unreachable", "migrations": "skipped"}


@pytest.mark.django_db
def test_database_check_reports_failure_and_closes_connection(monkeypatch: Any) -> None:
    from django.db import connection

    def broken_cursor(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("connection refused")

    closed = {}
    monkeypatch.setattr(connection, "cursor", broken_cursor)
    monkeypatch.setattr(connection, "close", lambda: closed.setdefault("yes", True))
    assert health._check_database() == (False, "unreachable")
    assert closed == {"yes": True}
