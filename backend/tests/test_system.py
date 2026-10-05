import json
import logging
from pathlib import Path
from typing import Any

import pytest
from django.test import Client
from rest_framework.test import APIClient

from apps.core import views
from apps.core.models import AuditLog, FeatureFlag, SiteSettings
from apps.search import registry


@pytest.mark.django_db
def test_read_only_mode_blocks_writes_but_not_sign_in_or_switching_it_off(
    admin_client: APIClient, make_user: Any
) -> None:
    res = admin_client.patch(
        "/api/v1/admin/site-settings",
        {"read_only_mode": True, "banner_message": "Database maintenance until 6 PM", "banner_level": "warning"},
        format="json",
    )
    assert res.status_code == 200
    status = APIClient().get("/api/v1/system/status").json()
    assert status["read_only_mode"] is True
    assert status["banner_message"] == "Database maintenance until 6 PM"

    blocked = admin_client.post(
        "/api/v1/admin/users", {"email": "x@example.com", "role": "parts", "password": "Long-Enough-Pass-77"}, format="json"
    )
    assert blocked.status_code == 503
    assert blocked.json()["code"] == "read_only"

    user = make_user()
    from .conftest import PASSWORD

    login = APIClient().post("/api/v1/auth/login", {"email": user.email, "password": PASSWORD}, format="json")
    assert login.status_code == 200

    off = admin_client.patch("/api/v1/admin/site-settings", {"read_only_mode": False}, format="json")
    assert off.status_code == 200
    assert not SiteSettings.is_read_only()
    assert AuditLog.objects.filter(action="update", changed_fields__contains=["read_only_mode"]).count() == 2


@pytest.mark.django_db
def test_feature_flags_endpoint(client_for: Any) -> None:
    FeatureFlag.objects.create(key="parts-ocr", enabled=True, roles=["parts"])
    FeatureFlag.objects.create(key="offline", enabled=False)
    assert client_for("parts").get("/api/v1/feature-flags").json()["flags"] == {
        "offline": False,
        "parts-ocr": True,
    }
    assert client_for("sales").get("/api/v1/feature-flags").json()["flags"]["parts-ocr"] is False


@pytest.mark.django_db
def test_audit_log_listing_and_filters(admin_client: APIClient) -> None:
    FeatureFlag.objects.create(key="units")
    res = admin_client.get("/api/v1/admin/audit-log?action=create&q=units")
    assert res.status_code == 200
    rows = res.json()["results"]
    assert rows and rows[0]["object_repr"] == "units"
    assert rows[0]["action_label"] == "Created"


@pytest.mark.django_db
def test_admin_health(admin_client: APIClient) -> None:
    body = admin_client.get("/api/v1/admin/health").json()
    assert body["database"] == "ok"
    assert body["last_backup"] is None


@pytest.mark.django_db
def test_search_is_empty_until_features_register(client_for: Any) -> None:
    client = client_for("service")
    assert client.get("/api/v1/search?q=a").json()["groups"] == {}
    body = client.get("/api/v1/search?q=35LN").json()
    assert body["query"] == "35LN"
    assert body["groups"] == {}


@pytest.mark.django_db
def test_search_registry_calls_providers(client_for: Any, monkeypatch: Any) -> None:
    def fake(user: Any, q: str, limit: int) -> list[registry.SearchResult]:
        return [registry.SearchResult("unit", "1", f"Unit {q}", "Hyundai 35LN-9A", "/units/1")]

    monkeypatch.setattr(registry, "_providers", {"unit": fake})
    body = client_for("sales").get("/api/v1/search?q=ABC123").json()
    assert body["groups"]["unit"][0]["title"] == "Unit ABC123"
    assert body["searchable"] == ["unit"]


@pytest.mark.django_db
def test_spa_index_has_security_headers_and_config(
    client: Client, tmp_path: Path, monkeypatch: Any
) -> None:
    index = tmp_path / "index.html"
    index.write_text('<html><head><meta name="mmh-config" content="{{ mmh_config }}"></head></html>')
    monkeypatch.setattr(views, "_INDEX", index)
    res = client.get("/units/123")
    assert res.status_code == 200
    assert "default-src &#x27;self&#x27;" not in res.content.decode()
    assert "&quot;env&quot;: &quot;test&quot;" in res.content.decode()
    assert "default-src 'self'" in res["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in res["Content-Security-Policy"]
    assert res["X-Frame-Options"] == "DENY"
    assert res["X-Content-Type-Options"] == "nosniff"
    assert "camera=(self)" in res["Permissions-Policy"]
    assert "mmh_csrftoken" in res.cookies


@pytest.mark.django_db
def test_spa_index_missing_build(client: Client, tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setattr(views, "_INDEX", tmp_path / "missing.html")
    assert client.get("/").status_code == 503


@pytest.mark.django_db
def test_api_responses_are_not_cached_and_carry_request_id(client: Client) -> None:
    res = client.get("/api/v1/system/status", HTTP_X_REQUEST_ID="abc12345-trace")
    assert res["Cache-Control"] == "no-store"
    assert res["X-Request-ID"] == "abc12345-trace"
    generated = client.get("/api/v1/system/status", HTTP_X_REQUEST_ID="bad id!")
    assert generated["X-Request-ID"] != "bad id!"
    assert len(generated["X-Request-ID"]) == 32


@pytest.mark.django_db
def test_json_log_line_per_request(client: Client, caplog: Any) -> None:
    from pythonjsonlogger.json import JsonFormatter

    from apps.core.logging import RequestContextFilter

    caplog.set_level(logging.INFO, logger="mmh.request")
    client.get("/api/v1/system/status", HTTP_X_REQUEST_ID="trace-0001-abcd")
    record = next(r for r in caplog.records if r.name == "mmh.request")
    RequestContextFilter().filter(record)
    line = json.loads(JsonFormatter("%(levelname)s %(name)s %(message)s").format(record))
    assert line["path"] == "/api/v1/system/status"
    assert line["status"] == 200
    assert line["request_id"] == "trace-0001-abcd"
    assert "duration_ms" in line
