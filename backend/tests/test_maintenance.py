from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.customers.models import Customer
from apps.service.maintenance import plan_status
from apps.service.models import MaintenancePlan, WorkOrder
from apps.units.models import HourMeterReading, OwnershipRecord, Unit

URL = "/api/v1/maintenance-plans"
TODAY = date(2026, 10, 5)


def plan(**kw: Any) -> MaintenancePlan:
    defaults: dict[str, Any] = {
        "name": "250-hour service",
        "last_done_on": TODAY - timedelta(days=10),
    }
    return MaintenancePlan(**{**defaults, **kw})


@pytest.mark.parametrize(
    ("kw", "hours", "state"),
    [
        ({"interval_days": 90}, None, "ok"),
        ({"interval_days": 30}, None, "due_soon"),  # 20 days left
        ({"interval_days": 9}, None, "overdue"),
        ({"interval_hours": 250, "last_done_hours": Decimal("1000")}, Decimal("1100"), "ok"),
        (
            {"interval_hours": 250, "last_done_hours": Decimal("1000")},
            Decimal("1210"),
            "due_soon",
        ),  # 40 h left
        ({"interval_hours": 250, "last_done_hours": Decimal("1000")}, Decimal("1250"), "overdue"),
        # Whichever comes first.
        (
            {"interval_hours": 250, "interval_days": 365, "last_done_hours": Decimal("1000")},
            Decimal("1300"),
            "overdue",
        ),
        (
            {"interval_hours": 250, "interval_days": 5, "last_done_hours": Decimal("1000")},
            Decimal("1001"),
            "overdue",
        ),
        # No hour reading yet: only the calendar counts.
        ({"interval_hours": 250, "last_done_hours": Decimal("1000")}, None, "ok"),
        ({"interval_days": 9, "active": False}, None, "paused"),
    ],
)
def test_plan_status(kw: dict[str, Any], hours: Decimal | None, state: str) -> None:
    assert plan_status(plan(**kw), hours, TODAY).state == state


def test_plan_status_numbers() -> None:
    st = plan_status(
        plan(interval_hours=250, interval_days=90, last_done_hours=Decimal("1000")),
        Decimal("1100"),
        TODAY,
    )
    assert st.next_due_on == TODAY + timedelta(days=80)
    assert st.next_due_hours == Decimal("1250")
    assert (st.days_left, st.hours_left) == (80, Decimal("150"))


@pytest.fixture
def unit(db: Any) -> Unit:
    unit = Unit.objects.create(make="Hyundai", model="70D-9", serial_number="HHKHFV30K00057")
    OwnershipRecord.objects.create(
        unit=unit, owner_kind="customer", customer=Customer.objects.create(name="Katahdin Lumber")
    )
    HourMeterReading.objects.create(
        unit=unit, hours=Decimal("9120"), reading_date=timezone.localdate(), source="card"
    )
    return unit


@pytest.mark.django_db
def test_database_rules(unit: Unit) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        MaintenancePlan.objects.create(unit=unit, name="No interval")
    with pytest.raises(IntegrityError), transaction.atomic():
        MaintenancePlan.objects.create(unit=unit, name="Hours without a start", interval_hours=250)


@pytest.mark.django_db
def test_create_plan_and_due_list(client_for: Any, unit: Unit) -> None:
    client = client_for("service")
    bad = client.post(URL, {"unit": str(unit.pk), "name": "Nothing"}, format="json")
    assert bad.status_code == 400
    assert "interval_hours" in bad.json()["fields"]

    # The starting hours default to the unit's latest reading.
    res = client.post(
        URL,
        {"unit": str(unit.pk), "name": "250-hour service", "interval_hours": 250},
        format="json",
    )
    assert res.status_code == 201, res.content
    assert res.json()["last_done_hours"] == "9120.0"

    old = timezone.localdate() - timedelta(days=400)
    client.post(
        URL,
        {
            "unit": str(unit.pk),
            "name": "Annual inspection",
            "interval_days": 365,
            "last_done_on": old.isoformat(),
        },
        format="json",
    )
    listed = client.get(URL, {"unit": str(unit.pk)}).json()
    assert {p["name"]: p["status"]["state"] for p in listed} == {
        "250-hour service": "ok",
        "Annual inspection": "overdue",
    }
    assert listed[0]["owner_name"] == "Katahdin Lumber"

    due = client.get(f"{URL}/due").json()
    assert due["counts"] == {"overdue": 1, "due_soon": 0}
    assert [p["name"] for p in due["results"]] == ["Annual inspection"]
    assert len(client.get(f"{URL}/due", {"all": "1"}).json()["results"]) == 2
    assert client.get(URL).status_code == 400  # list needs a unit


@pytest.mark.django_db
def test_work_order_from_plan_marks_it_done(client_for: Any, unit: Unit) -> None:
    client = client_for("service")
    old = timezone.localdate() - timedelta(days=100)
    created = client.post(
        URL,
        {
            "unit": str(unit.pk),
            "name": "250-hour service",
            "tasks": "Oil and filter",
            "interval_hours": 250,
            "interval_days": 90,
            "last_done_on": old.isoformat(),
            "last_done_hours": "8800",
        },
        format="json",
    ).json()
    res = client.post(f"{URL}/{created['id']}/work-order")
    assert res.status_code == 201, res.content
    wo = res.json()
    assert wo["kind"] == "maintenance"
    assert wo["complaint"] == "250-hour service:\nOil and filter"
    assert wo["maintenance_plan_name"] == "250-hour service"
    assert wo["customer_name"] == "Katahdin Lumber"
    assert client.post(f"{URL}/{created['id']}/work-order").status_code == 400  # one open at a time
    due = client.get(f"{URL}/due").json()["results"][0]
    assert due["status"]["open_work_order"]["number"] == wo["number"]

    client.patch(
        f"/api/v1/work-orders/{wo['id']}", {"correction": "Done", "hours": "9130"}, format="json"
    )
    client.post(f"/api/v1/work-orders/{wo['id']}/status", {"status": "completed"}, format="json")
    done = MaintenancePlan.objects.get(pk=created["id"])
    assert done.last_done_on == timezone.localdate()
    assert done.last_done_hours == Decimal("9130.0")
    assert client.get(f"{URL}/due").json()["counts"] == {"overdue": 0, "due_soon": 0}

    # Reopening puts the plan back.
    client.post(f"/api/v1/work-orders/{wo['id']}/status", {"status": "in_progress"}, format="json")
    back = MaintenancePlan.objects.get(pk=created["id"])
    assert (back.last_done_on, back.last_done_hours) == (old, Decimal("8800.0"))
    assert WorkOrder.objects.get(pk=wo["id"]).plan_prev_done_on is None


@pytest.mark.django_db
def test_paused_and_removed_plans(client_for: Any, unit: Unit) -> None:
    client = client_for("admin")
    created = client.post(
        URL,
        {
            "unit": str(unit.pk),
            "name": "Weekly check",
            "interval_days": 7,
            "last_done_on": "2020-01-01",
        },
        format="json",
    ).json()
    assert client.get(f"{URL}/due").json()["counts"]["overdue"] == 1
    client.patch(f"{URL}/{created['id']}", {"active": False}, format="json")
    assert client.get(f"{URL}/due").json()["counts"]["overdue"] == 0
    assert client.post(f"{URL}/{created['id']}/work-order").status_code == 400
    assert client.delete(f"{URL}/{created['id']}").status_code == 204
    assert MaintenancePlan.all_objects.get(pk=created["id"]).is_deleted
    assert client.post(f"{URL}/{created['id']}/restore").status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("role", "can_edit"),
    [("admin", True), ("service", True), ("sales", False), ("parts", False), ("read_only", False)],
)
def test_role_matrix(client_for: Any, unit: Unit, role: str, can_edit: bool) -> None:
    existing = (
        client_for("admin")
        .post(URL, {"unit": str(unit.pk), "name": "Annual", "interval_days": 365}, format="json")
        .json()
    )
    client = client_for(role)
    assert client.get(URL, {"unit": str(unit.pk)}).status_code == 200
    assert client.get(f"{URL}/due").status_code == 200
    created = client.post(
        URL, {"unit": str(unit.pk), "name": "x", "interval_days": 30}, format="json"
    )
    assert (created.status_code == 201) is can_edit
    assert (
        client.patch(f"{URL}/{existing['id']}", {"tasks": "y"}, format="json").status_code == 200
    ) is can_edit
    assert (client.post(f"{URL}/{existing['id']}/work-order").status_code == 201) is can_edit
    assert (client.delete(f"{URL}/{existing['id']}").status_code == 204) is can_edit


@pytest.mark.django_db
def test_demo_plans(make_user: Any) -> None:
    from apps.service.demo import load_demo_plans
    from apps.units.demo import load_demo_data

    load_demo_data(with_files=False)
    load_demo_plans()
    load_demo_plans()
    assert MaintenancePlan.objects.count() == 4
