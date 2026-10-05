from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.models import FeatureFlag
from apps.customers.models import Customer
from apps.service.models import WorkOrder
from apps.units.models import HourMeterReading, OwnershipRecord, Unit

URL = "/api/v1/work-orders"


@pytest.fixture
def unit(db: Any) -> Unit:
    unit = Unit.objects.create(
        make="Hyundai", model="70D-9", serial_number="HHKHFV30K00057", work_order_number="WO-4471"
    )
    customer = Customer.objects.create(name="Katahdin Lumber")
    OwnershipRecord.objects.create(unit=unit, owner_kind="customer", customer=customer)
    HourMeterReading.objects.create(
        unit=unit,
        hours=Decimal("9000"),
        reading_date=timezone.localdate() - timedelta(days=30),
        source="card",
    )
    return unit


def create(client: APIClient, unit: Unit, **extra: Any) -> dict[str, Any]:
    res = client.post(
        URL, {"unit": str(unit.pk), "complaint": "Mast chatters", **extra}, format="json"
    )
    assert res.status_code == 201, res.content
    return res.json()


def me(client: APIClient) -> str:
    return client.get("/api/v1/auth/me").json()["user"]["id"]


@pytest.mark.django_db
def test_create_defaults_and_numbering(client_for: Any, unit: Unit) -> None:
    client = client_for("service")
    first = create(client, unit, hours="9120.5")
    second = create(client, unit)
    assert first["number"].startswith("WO-") and int(first["number"][3:]) >= 20001
    assert int(second["number"][3:]) == int(first["number"][3:]) + 1
    assert first["customer_name"] == "Katahdin Lumber"  # from the unit's current owner
    assert first["status"] == "open"
    assert first["hour_meter"]["hours"] == "9120.5"
    reading = HourMeterReading.objects.get(hours=Decimal("9120.5"))
    assert reading.source == "service"
    assert first["number"] in reading.note
    assert first["warning"] is None

    lower = create(client, unit, hours="100")
    assert "lower than" in lower["warning"]


@pytest.mark.django_db
def test_correcting_hours_replaces_the_reading(client_for: Any, unit: Unit) -> None:
    client = client_for("admin")
    wo = create(client, unit, hours="9100")
    client.patch(f"{URL}/{wo['id']}", {"hours": "9150"}, format="json")
    assert list(unit.hour_readings.values_list("hours", flat=True)) == [
        Decimal("9150.0"),
        Decimal("9000.0"),
    ]
    client.patch(f"{URL}/{wo['id']}", {"hours": None}, format="json")
    assert list(unit.hour_readings.values_list("hours", flat=True)) == [Decimal("9000.0")]


@pytest.mark.django_db
def test_status_flow(client_for: Any, unit: Unit) -> None:
    client = client_for("service")
    wo = create(client, unit)
    path = f"{URL}/{wo['id']}/status"
    assert (
        client.post(path, {"status": "on_hold"}, format="json").status_code == 400
    )  # needs a reason
    held = client.post(
        path, {"status": "on_hold", "reason": "Waiting for rollers"}, format="json"
    ).json()
    assert held["hold_reason"] == "Waiting for rollers"
    started = client.post(path, {"status": "in_progress"}, format="json").json()
    assert started["hold_reason"] == ""
    refused = client.post(path, {"status": "completed"}, format="json")
    assert refused.status_code == 400
    assert "correction" in refused.json()["fields"]
    client.patch(f"{URL}/{wo['id']}", {"correction": "Replaced mast rollers"}, format="json")
    done = client.post(path, {"status": "completed"}, format="json").json()
    assert done["status"] == "completed" and done["completed_at"]
    assert client.post(path, {"status": "on_hold", "reason": "x"}, format="json").status_code == 400
    reopened = client.post(path, {"status": "in_progress"}, format="json").json()
    assert reopened["completed_at"] is None
    client.post(path, {"status": "cancelled"}, format="json")
    assert client.patch(f"{URL}/{wo['id']}", {"cause": "x"}, format="json").status_code == 400
    assert client.post(path, {"status": "open"}, format="json").json()["status"] == "open"


@pytest.mark.django_db
def test_database_refuses_completed_without_correction(unit: Unit) -> None:
    wo = WorkOrder(unit=unit, status="completed", completed_at=timezone.now())
    with pytest.raises(IntegrityError), transaction.atomic():
        wo.save()


@pytest.mark.django_db
def test_labor(client_for: Any, make_user: Any, unit: Unit) -> None:
    client = client_for("service")
    wo = create(client, unit)
    mechanic = me(client)
    today = timezone.localdate().isoformat()
    res = client.post(
        f"{URL}/{wo['id']}/labor",
        {"mechanic": mechanic, "work_date": today, "hours": "2.5", "description": "Diagnosed"},
        format="json",
    )
    assert res.status_code == 201, res.content
    line = res.json()
    client.post(
        f"{URL}/{wo['id']}/labor",
        {"mechanic": mechanic, "work_date": today, "hours": "1"},
        format="json",
    )
    assert client.get(f"{URL}/{wo['id']}").json()["labor_hours"] == "3.50"

    parts_person = make_user("parts")
    bad = client.post(
        f"{URL}/{wo['id']}/labor",
        {"mechanic": str(parts_person.pk), "work_date": today, "hours": "1"},
        format="json",
    )
    assert "mechanic" in bad.json()["fields"]
    tomorrow = (timezone.localdate() + timedelta(days=1)).isoformat()
    assert (
        client.post(
            f"{URL}/{wo['id']}/labor",
            {"mechanic": mechanic, "work_date": tomorrow, "hours": "1"},
            format="json",
        ).status_code
        == 400
    )
    assert (
        client.post(
            f"{URL}/{wo['id']}/labor",
            {"mechanic": mechanic, "work_date": today, "hours": "25"},
            format="json",
        ).status_code
        == 400
    )

    assert (
        client.patch(f"/api/v1/labor/{line['id']}", {"hours": "3"}, format="json").status_code
        == 200
    )
    assert client.delete(f"/api/v1/labor/{line['id']}").status_code == 204
    assert client.get(f"{URL}/{wo['id']}").json()["labor_hours"] == "1.00"
    assert client.post(f"/api/v1/labor/{line['id']}/restore").status_code == 200


@pytest.mark.django_db
def test_rules_on_edit(client_for: Any, make_user: Any, unit: Unit) -> None:
    client = client_for("admin")
    wo = create(client, unit)
    other = Unit.objects.create(make="Doosan", model="G25N-7", serial_number="FGA25-1")
    assert (
        client.patch(f"{URL}/{wo['id']}", {"unit": str(other.pk)}, format="json").status_code == 400
    )
    sales = make_user("sales")
    assert (
        client.patch(f"{URL}/{wo['id']}", {"assigned_to": str(sales.pk)}, format="json").status_code
        == 400
    )
    mechanic = make_user("service")
    assert client.patch(
        f"{URL}/{wo['id']}", {"assigned_to": str(mechanic.pk)}, format="json"
    ).json()["assigned_to_name"]
    past = (timezone.localdate() - timedelta(days=3)).isoformat()
    assert client.patch(f"{URL}/{wo['id']}", {"due_on": past}, format="json").status_code == 400


@pytest.mark.django_db
def test_list_filters_and_counts(client_for: Any, unit: Unit) -> None:
    client = client_for("service")
    mine = create(client, unit, assigned_to=me(client))
    other = create(client, unit, complaint="Brake squeal")
    client.patch(f"{URL}/{other['id']}", {"correction": "Adjusted brakes"}, format="json")
    client.post(f"{URL}/{other['id']}/status", {"status": "completed"}, format="json")

    def numbers(**params: str) -> list[str]:
        return [w["number"] for w in client.get(URL, params).json()["results"]]

    assert numbers() == [mine["number"]]
    assert set(numbers(scope="all")) == {mine["number"], other["number"]}
    assert numbers(scope="completed") == [other["number"]]
    assert numbers(assigned="me") == [mine["number"]]
    assert numbers(scope="all", q="brake") == [other["number"]]
    assert set(numbers(scope="all", unit=str(unit.pk))) == {mine["number"], other["number"]}
    assert client.get(f"{URL}/counts").json() == {"open": 1, "mine": 1, "on_hold": 0}
    names = [m["name"] for m in client.get(f"{URL}/mechanics").json()]
    assert names  # the service user at least


@pytest.mark.django_db
def test_search_by_number_and_old_card_number(client_for: Any, unit: Unit) -> None:
    client = client_for("parts")
    wo = create(client_for("service"), unit)
    groups = client.get("/api/v1/search", {"q": wo["number"][3:]}).json()["groups"]
    assert groups["work_order"][0]["url"] == f"/service/{wo['id']}"
    old = client.get("/api/v1/search", {"q": "WO-4471"}).json()["groups"]
    assert old["unit"][0]["id"] == str(unit.pk)


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("role", "can_read", "can_edit", "can_remove"),
    [
        ("admin", True, True, True),
        ("service", True, True, False),
        ("sales", True, False, False),
        ("parts", True, False, False),
        ("read_only", True, False, False),
    ],
)
def test_role_matrix(
    client_for: Any, unit: Unit, role: str, can_read: bool, can_edit: bool, can_remove: bool
) -> None:
    wo = create(client_for("admin"), unit)
    client = client_for(role)
    assert (client.get(URL).status_code == 200) is can_read
    assert (client.get(f"{URL}/{wo['id']}").status_code == 200) is can_read
    created = client.post(URL, {"unit": str(unit.pk), "complaint": "x"}, format="json")
    assert (created.status_code == 201) is can_edit
    assert (
        client.patch(f"{URL}/{wo['id']}", {"cause": "y"}, format="json").status_code == 200
    ) is can_edit
    assert (
        client.post(
            f"{URL}/{wo['id']}/status", {"status": "in_progress"}, format="json"
        ).status_code
        == 200
    ) is can_edit
    assert (client.delete(f"{URL}/{wo['id']}").status_code == 204) is can_remove


@pytest.mark.django_db
def test_flag_off_and_anonymous(client_for: Any, anon_client: APIClient) -> None:
    assert anon_client.get(URL).status_code in (401, 403)
    flag = FeatureFlag.objects.get(key="service")
    flag.enabled = False
    flag.save()
    assert client_for("admin").get(URL).status_code == 404


@pytest.mark.django_db
def test_demo_work_orders_load_once(make_user: Any) -> None:
    from apps.service.demo import load_demo_work_orders
    from apps.units.demo import load_demo_data

    make_user("service", email="service@mmh.test")
    load_demo_data(with_files=False)
    load_demo_work_orders()
    load_demo_work_orders()
    assert WorkOrder.objects.count() == 4
    assert set(WorkOrder.objects.values_list("status", flat=True)) == {
        "open",
        "in_progress",
        "on_hold",
        "completed",
    }
