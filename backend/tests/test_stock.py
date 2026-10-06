"""Phase 10: the parts stock ledger, parts on work orders, the nightly check
and the low-stock list."""

from decimal import Decimal
from typing import Any

import pytest
from django.core.management import call_command
from django.db import DatabaseError, connection, transaction
from rest_framework.test import APIClient

from apps.core.models import FeatureFlag
from apps.parts import stock
from apps.parts.models import Part, PartStock, StockCheck, StockMovement
from apps.service.models import WorkOrder
from apps.units.models import Unit

MOVES = "/api/v1/stock-movements"
PARTS = "/api/v1/parts"


@pytest.fixture
def part(db: Any) -> Part:
    return Part.objects.create(
        manufacturer="Hyundai",
        part_number="31N4-01050",
        description="Engine oil filter",
        cost=Decimal("9.80"),
        list_price=Decimal("18.50"),
        reorder_point=Decimal("6"),
        reorder_quantity=Decimal("12"),
    )


@pytest.fixture
def work_order(db: Any) -> WorkOrder:
    unit = Unit.objects.create(make="Hyundai", model="35LN-9A", serial_number="HHKHHN04L0094")
    return WorkOrder.objects.create(unit=unit, complaint="250-hour service")


def post(client: APIClient, path: str, body: dict[str, Any]) -> Any:
    return client.post(f"{MOVES}/{path}", body, format="json")


def on_hand(client: APIClient, part: Part) -> str:
    return client.get(f"{PARTS}/{part.pk}").json()["on_hand"]  # type: ignore[no-any-return]


@pytest.mark.django_db
def test_count_receive_and_history(client_for: Any, part: Part) -> None:
    parts = client_for("parts")
    assert on_hand(parts, part) == "0.00"
    first = post(parts, "count", {"part": str(part.pk), "counted": "8"})
    assert first.status_code == 201, first.json()
    assert first.json()["kind"] == "opening"
    got = post(
        parts,
        "receive",
        {"part": str(part.pk), "quantity": "12", "unit_cost": "9.50", "reference": "INV 55120"},
    )
    assert got.status_code == 201, got.json()
    assert got.json()["balance_after"] == "20.00"
    assert got.json()["unit_cost"] == "9.50"
    # A later count records the difference as an adjustment.
    recount = post(parts, "count", {"part": str(part.pk), "counted": "18", "note": "Shelf count"})
    assert recount.json()["kind"] == "adjust"
    assert recount.json()["quantity"] == "-2.00"
    same = post(parts, "count", {"part": str(part.pk), "counted": "18"})
    assert same.status_code == 400
    assert "matches" in same.json()["fields"]["counted"][0]
    assert on_hand(parts, part) == "18.00"
    history = parts.get(f"{MOVES}?part={part.pk}").json()["results"]
    assert [m["kind"] for m in history] == ["adjust", "receive", "opening"]
    assert history[0]["by"]  # who did it


@pytest.mark.django_db
def test_never_below_zero(client_for: Any, part: Part, work_order: WorkOrder) -> None:
    parts = client_for("parts")
    post(parts, "count", {"part": str(part.pk), "counted": "2"})
    res = post(
        parts, "issue", {"part": str(part.pk), "work_order": str(work_order.pk), "quantity": "3"}
    )
    assert res.status_code == 400
    assert "Only 2 of 31N4-01050 on hand" in res.json()["fields"]["quantity"][0]
    assert post(parts, "count", {"part": str(part.pk), "counted": "-1"}).status_code == 400
    assert post(parts, "receive", {"part": str(part.pk), "quantity": "0"}).status_code == 400
    # The database refuses too.
    with pytest.raises(DatabaseError), transaction.atomic():
        PartStock.objects.filter(part=part).update(on_hand=Decimal("-1"))


@pytest.mark.django_db
def test_parts_on_a_work_order(client_for: Any, part: Part, work_order: WorkOrder) -> None:
    stock.count(part, Decimal("10"))
    mechanic = client_for("service")
    body = {"part": str(part.pk), "work_order": str(work_order.pk)}
    used = post(mechanic, "issue", {**body, "quantity": "3"})
    assert used.status_code == 201, used.json()
    assert used.json()["quantity"] == "-3.00"
    assert used.json()["unit_price"] == "18.50"  # priced as issued
    assert "unit_cost" not in used.json()  # mechanics don't see our cost
    # The list price changes later; the work order keeps the price it was issued at.
    part.list_price = Decimal("20.00")
    part.save()
    back = post(mechanic, "return", {**body, "quantity": "1"})
    assert back.status_code == 201, back.json()
    assert post(mechanic, "return", {**body, "quantity": "5"}).status_code == 400
    wo = mechanic.get(f"/api/v1/work-orders/{work_order.pk}").json()
    assert wo["parts_used"] == [
        {
            "part": {
                "id": str(part.pk),
                "manufacturer": "Hyundai",
                "part_number": "31N4-01050",
                "description": "Engine oil filter",
                "is_deleted": False,
            },
            "quantity": "2.00",
            "unit_price": "18.50",
            "amount": "37.00",
        }
    ]
    assert on_hand(mechanic, part) == "8.00"
    # The printout lists them.
    pdf = mechanic.get(f"/api/v1/work-orders/{work_order.pk}/pdf")
    assert b"31N4-01050" in pdf.content and b"$37.00" in pdf.content
    # Can't cancel with parts on it; can once they're back.
    cancel = mechanic.post(
        f"/api/v1/work-orders/{work_order.pk}/status", {"status": "cancelled"}, format="json"
    )
    assert cancel.status_code == 400
    assert "Return them to stock" in cancel.json()["fields"]["status"][0]
    post(mechanic, "return", {**body, "quantity": "2"})
    assert mechanic.get(f"/api/v1/work-orders/{work_order.pk}").json()["parts_used"] == []
    cancel = mechanic.post(
        f"/api/v1/work-orders/{work_order.pk}/status", {"status": "cancelled"}, format="json"
    )
    assert cancel.status_code == 200, cancel.json()
    # Nothing goes on or off a closed work order.
    again = post(mechanic, "issue", {**body, "quantity": "1"})
    assert again.status_code == 400
    assert "cancelled" in again.json()["fields"]["work_order"][0]


@pytest.mark.django_db
def test_reverse_a_mistake(client_for: Any, part: Part) -> None:
    parts = client_for("parts")
    post(parts, "count", {"part": str(part.pk), "counted": "5"})
    wrong = post(parts, "receive", {"part": str(part.pk), "quantity": "50"}).json()
    assert wrong["can_reverse"] is True
    undo = parts.post(f"{MOVES}/{wrong['id']}/reverse", {}, format="json")
    assert undo.status_code == 201, undo.json()
    assert undo.json()["quantity"] == "-50.00"
    assert undo.json()["reverses"] == wrong["id"]
    assert undo.json()["can_reverse"] is False
    assert on_hand(parts, part) == "5.00"
    assert parts.post(f"{MOVES}/{wrong['id']}/reverse", {}, format="json").status_code == 400
    assert parts.post(f"{MOVES}/{undo.json()['id']}/reverse", {}, format="json").status_code == 400
    listed = {m["id"]: m for m in parts.get(f"{MOVES}?part={part.pk}").json()["results"]}
    assert listed[wrong["id"]]["reversed"] is True
    # Reversing can't take stock below zero either.
    extra = post(parts, "receive", {"part": str(part.pk), "quantity": "2"}).json()
    post(parts, "count", {"part": str(part.pk), "counted": "0"})
    refused = parts.post(f"{MOVES}/{extra['id']}/reverse", {}, format="json")
    assert refused.status_code == 400
    assert "Only 0 of" in refused.json()["fields"]["quantity"][0]


@pytest.mark.django_db
def test_ledger_is_append_only(part: Part) -> None:
    movement = stock.count(part, Decimal("4"))
    # Straight SQL, past the ORM: the database itself refuses.
    for sql in (
        "UPDATE parts_stockmovement SET quantity = 40 WHERE id = %s",
        "DELETE FROM parts_stockmovement WHERE id = %s",
    ):
        with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cur:
            cur.execute(sql, [movement.pk])
    movement.note = "edited"
    with pytest.raises(DatabaseError), transaction.atomic():
        movement.save()
    with pytest.raises(DatabaseError), transaction.atomic():
        StockMovement.objects.create(
            part=part, kind="issue", quantity=Decimal("-1"), balance_after=Decimal("3")
        )  # an issue must name a work order


@pytest.mark.django_db
def test_nightly_check_finds_drift(client_for: Any, part: Part) -> None:
    stock.count(part, Decimal("4"))
    run = stock.check_drift()
    assert run.ok and run.parts_checked == 1
    # Someone changes the stored count behind the ledger's back.
    with connection.cursor() as cur:
        cur.execute("UPDATE parts_partstock SET on_hand = 7 WHERE part_id = %s", [part.pk])
    with pytest.raises(SystemExit):
        call_command("check_stock")
    last = StockCheck.objects.first()
    assert last is not None and not last.ok
    assert last.drift == [
        {"part": str(part.pk), "part_number": "31N4-01050", "ledger": "4.00", "stored": "7.00"}
    ]
    admin = client_for("admin")
    assert admin.get(f"{MOVES}/check").json()["ok"] is False
    assert admin.post(f"{MOVES}/check").status_code == 200
    assert client_for("parts").post(f"{MOVES}/check").status_code == 403


@pytest.mark.django_db
def test_nightly_task_runs(part: Part) -> None:
    from apps.parts.tasks import nightly_stock_check

    stock.count(part, Decimal("2"))
    nightly_stock_check(timestamp=0)
    nightly_stock_check(timestamp=0)  # safe to run twice
    assert StockCheck.objects.count() == 2
    assert all(c.ok for c in StockCheck.objects.all())


@pytest.mark.django_db
def test_low_stock_list_and_filter(client_for: Any, part: Part) -> None:
    plenty = Part.objects.create(
        part_number="LED-1280-W",
        description="LED work light",
        reorder_point=Decimal("2"),
        reorder_quantity=Decimal("4"),
    )
    Part.objects.create(part_number="NO-POINT", description="Not tracked")
    stock.count(part, Decimal("6"))  # at the reorder point counts as low
    stock.count(plenty, Decimal("10"))
    viewer = client_for("read_only")
    low = viewer.get(f"{PARTS}/low-stock").json()
    assert [p["part_number"] for p in low["results"]] == ["31N4-01050"]
    assert low["results"][0]["low"] is True
    assert low["last_check"] is None
    listed = viewer.get(f"{PARTS}?stock=low").json()["results"]
    assert [p["part_number"] for p in listed] == ["31N4-01050"]
    assert viewer.get(f"{PARTS}?stock=out").json()["results"][0]["part_number"] == "NO-POINT"
    assert viewer.get(f"{PARTS}?stock=in").json()["count"] == 2


@pytest.mark.django_db
def test_part_in_stock_cant_be_removed(client_for: Any, part: Part) -> None:
    parts = client_for("parts")
    stock.count(part, Decimal("1"))
    res = parts.delete(f"{PARTS}/{part.pk}")
    assert res.status_code == 400
    assert "Count it to zero" in res.json()["fields"]["on_hand"][0]
    post(parts, "count", {"part": str(part.pk), "counted": "0"})
    assert parts.delete(f"{PARTS}/{part.pk}").status_code == 204
    # A removed part can't be stocked.
    assert post(parts, "receive", {"part": str(part.pk), "quantity": "1"}).status_code == 400


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("role", "keeps_stock", "uses_parts", "sees_cost"),
    [
        ("admin", True, True, True),
        ("parts", True, True, True),
        ("sales", False, False, True),
        ("service", False, True, False),
        ("read_only", False, False, False),
    ],
)
def test_stock_role_matrix(
    client_for: Any,
    part: Part,
    work_order: WorkOrder,
    role: str,
    keeps_stock: bool,
    uses_parts: bool,
    sees_cost: bool,
) -> None:
    opening = stock.count(part, Decimal("10"))
    client = client_for(role)
    listed = client.get(f"{MOVES}?part={part.pk}")
    assert listed.status_code == 200
    assert ("unit_cost" in listed.json()["results"][0]) is sees_cost
    assert client.get(f"{PARTS}/low-stock").status_code == 200
    assert client.get(f"{MOVES}/check").status_code == 200
    keep = 201 if keeps_stock else 403
    assert post(client, "receive", {"part": str(part.pk), "quantity": "1"}).status_code == keep
    assert post(client, "count", {"part": str(part.pk), "counted": "3"}).status_code == keep
    assert client.post(f"{MOVES}/{opening.pk}/reverse", {}, format="json").status_code in (
        (201, 400) if keeps_stock else (403,)
    )
    use = 201 if uses_parts else 403
    body = {"part": str(part.pk), "work_order": str(work_order.pk), "quantity": "1"}
    assert post(client, "issue", body).status_code == use
    assert post(client, "return", body).status_code == use
    assert client.post(f"{MOVES}/check").status_code == (200 if role == "admin" else 403)


@pytest.mark.django_db
def test_receive_ignores_cost_from_roles_that_cant_see_it(
    client_for: Any, make_user: Any, part: Part
) -> None:
    """Only cost roles can receive today, but cost from anyone else is dropped."""
    from apps.parts.serializers import StockMovementSerializer

    movement = stock.receive(part, Decimal("1"), unit_cost=Decimal("3"))

    class Request:
        user = make_user("service")

    data = StockMovementSerializer(movement, context={"request": Request()}).data
    assert "unit_cost" not in data


@pytest.mark.django_db
def test_flag_off(
    client_for: Any, anon_client: APIClient, part: Part, work_order: WorkOrder
) -> None:
    assert anon_client.get(MOVES).status_code == 401
    flag = FeatureFlag.objects.get(key="parts-stock")
    flag.enabled = False
    flag.save()
    admin = client_for("admin")
    assert admin.get(MOVES).status_code == 404
    assert admin.get(f"{PARTS}/low-stock").status_code == 404
    assert admin.get(PARTS).status_code == 200  # the catalog still works
    assert admin.get(f"/api/v1/work-orders/{work_order.pk}").json()["parts_used"] is None


@pytest.mark.django_db
def test_demo_stock_loads_once() -> None:
    from apps.parts.demo import load_demo_parts, load_demo_stock

    load_demo_parts()
    load_demo_stock()
    load_demo_stock()
    oil = Part.objects.get(part_number="31N4-01050")
    assert stock.on_hand(oil) == Decimal("20")
    assert stock.check_drift().ok
