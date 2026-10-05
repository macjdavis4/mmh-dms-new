"""Phase 7: units changing hands. A unit is sold, comes back (trade-in,
repossession, buy-back, lease return) and is sold again, as one unit record
whose ownership history is the timeline. Each deal keeps its own numbers."""

from decimal import Decimal
from typing import Any

import pytest
from django.db import DatabaseError, transaction
from rest_framework.test import APIClient

from apps.core.models import AuditLog, FeatureFlag
from apps.customers.models import Customer
from apps.units.models import HourMeterReading, OwnershipRecord, Unit

URL = "/api/v1/units"
CHANGES = "/api/v1/unit-changes"
RECORDS = "/api/v1/ownership-records"


def new_stock_unit(client: APIClient, **fields: Any) -> dict[str, Any]:
    body = {
        "make": "Hyundai",
        "model": "25LC-7A",
        "serial_number": "HHKHHC52C00999",
        "condition": "new",
        "card_date": "2024-01-10",
        "stock_status": "available",
        "cost": "21000",
        "asking_price": "29900",
        **fields,
    }
    res = client.post(URL, body, format="json")
    assert res.status_code == 201, res.json()
    return res.json()  # type: ignore[no-any-return]


def change(client: APIClient, unit_id: str, **body: Any) -> Any:
    return client.post(f"{URL}/{unit_id}/transfer", body, format="json")


def unit(client: APIClient, unit_id: str) -> dict[str, Any]:
    return client.get(f"{URL}/{unit_id}").json()  # type: ignore[no-any-return]


@pytest.fixture
def buyers(db: Any) -> tuple[Customer, Customer]:
    return Customer.objects.create(name="Katahdin Lumber"), Customer.objects.create(
        name="Bangor Building Supply"
    )


@pytest.mark.django_db
def test_sell_trade_in_and_sell_again_keeps_every_deal(
    client_for: Any, buyers: tuple[Customer, Customer]
) -> None:
    first, second = buyers
    sales = client_for("sales")
    u = new_stock_unit(sales)

    # 1. Sold out of our stock.
    sold = change(
        sales,
        u["id"],
        owner_kind="customer",
        customer=str(first.pk),
        reason="sold",
        start_date="2024-03-01",
        price="28500",
        reference="INV-10422",
        hours="12",
    )
    assert sold.status_code == 201, sold.json()
    assert sold.json()["reason_label"] == "Sold"
    assert sold.json()["price"] == "28500.00"
    assert sold.json()["cost"] == "21000.00"  # the unit's cost at the time
    assert sold.json()["hours"] == "12.0"
    after_sale = unit(sales, u["id"])
    assert after_sale["stock_status"] == "sold"
    assert after_sale["sale_price"] == "28500.00"
    assert after_sale["condition"] == "new"  # a sale doesn't make it used

    # 2. Traded back in two years later.
    back = change(
        sales,
        u["id"],
        owner_kind="dealer",
        reason="trade_in",
        start_date="2026-02-02",
        price="9000",
        hours="6100",
    )
    assert back.status_code == 201, back.json()
    in_stock = unit(sales, u["id"])
    assert in_stock["stock_status"] == "in_prep"
    assert in_stock["condition"] == "used"
    assert in_stock["cost"] == "9000.00"  # what we paid, this time in stock
    assert in_stock["asking_price"] is None
    assert in_stock["sale_price"] is None
    assert in_stock["owner_kind"] == "dealer"

    # 3. Priced and sold again to someone else.
    priced = sales.patch(f"{URL}/{u['id']}", {"asking_price": "15900"}, format="json")
    assert priced.status_code == 200
    again = change(
        sales,
        u["id"],
        owner_kind="customer",
        customer=str(second.pk),
        reason="sold",
        start_date="2026-04-15",
        price="15000",
    )
    assert again.status_code == 201, again.json()

    history = sales.get(f"{URL}/{u['id']}/ownership").json()
    assert [(h["owner_label"], h["reason"], h["price"], h["cost"]) for h in history] == [
        ("Bangor Building Supply", "sold", "15000.00", "9000.00"),
        ("Maine Material Handling stock", "trade_in", "9000.00", None),
        ("Katahdin Lumber", "sold", "28500.00", "21000.00"),  # untouched by the second sale
        ("Maine Material Handling stock", "", None, None),
    ]
    assert unit(sales, u["id"])["sale_price"] == "15000.00"
    # Still one unit (one serial).
    assert Unit.objects.filter(serial_number="HHKHHC52C00999").count() == 1
    readings = HourMeterReading.objects.filter(unit_id=u["id"], source="sale")
    assert sorted(r.hours for r in readings) == [Decimal("12"), Decimal("6100")]


@pytest.mark.django_db
@pytest.mark.parametrize("reason", ["repossession", "buy_back", "lease_return", "bought_used"])
def test_every_way_back_into_stock(
    client_for: Any, buyers: tuple[Customer, Customer], reason: str
) -> None:
    admin = client_for("admin")
    u = new_stock_unit(admin)
    change(
        admin,
        u["id"],
        owner_kind="customer",
        customer=str(buyers[0].pk),
        reason="sold",
        start_date="2025-01-01",
    )
    res = change(admin, u["id"], owner_kind="dealer", reason=reason, start_date="2026-01-01")
    assert res.status_code == 201, res.json()
    assert res.json()["reason"] == reason
    now = unit(admin, u["id"])
    assert (now["stock_status"], now["condition"], now["cost"]) == ("in_prep", "used", None)


@pytest.mark.django_db
def test_sale_price_typed_on_the_unit_is_kept_with_the_sale(
    client_for: Any, buyers: tuple[Customer, Customer]
) -> None:
    """Older sales (and sales whose price was typed on the unit card) keep
    their numbers when the unit comes back."""
    sales = client_for("sales")
    u = new_stock_unit(sales, cost="7200", asking_price="11900")
    typed = sales.patch(f"{URL}/{u['id']}", {"sale_price": "11400"}, format="json")
    assert typed.status_code == 200
    sold = change(
        sales,
        u["id"],
        owner_kind="customer",
        customer=str(buyers[0].pk),
        reason="sold",
        start_date="2025-03-03",
    )
    assert sold.json()["price"] == "11400.00"  # taken from the unit
    # A sale recorded before Phase 7 has no price on its record.
    record = OwnershipRecord.objects.get(pk=sold.json()["id"])
    record.price = None
    record.cost = None
    record.save()
    change(sales, u["id"], owner_kind="dealer", reason="repossession", start_date="2026-01-05")
    record.refresh_from_db()
    assert (record.price, record.cost) == (Decimal("11400.00"), Decimal("7200.00"))


@pytest.mark.django_db
def test_between_customers_changes_only_the_owner(
    client_for: Any, buyers: tuple[Customer, Customer]
) -> None:
    admin = client_for("admin")
    u = new_stock_unit(admin, initial_owner_customer=str(buyers[0].pk), stock_status="")
    before = unit(admin, u["id"])
    sold_privately = change(
        admin,
        u["id"],
        owner_kind="customer",
        customer=str(buyers[1].pk),
        reason="private_sale",
        start_date="2026-01-01",
    )
    assert sold_privately.status_code == 201, sold_privately.json()
    after = unit(admin, u["id"])
    for field in ("stock_status", "condition", "cost", "asking_price", "sale_price"):
        assert after[field] == before[field]
    assert sold_privately.json()["can_undo"] is True
    # A price is only kept for deals we're part of.
    priced = change(
        admin,
        u["id"],
        owner_kind="customer",
        customer=str(buyers[0].pk),
        reason="private_sale",
        start_date="2026-02-01",
        price="5000",
    )
    assert priced.status_code == 400
    assert "price" in priced.json()["fields"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("owner", "reason", "field"),
    [
        ("customer", "trade_in", "reason"),  # trade-ins come to us
        ("dealer", "sold", "reason"),  # we don't sell to ourselves
        ("customer", "private_sale", "reason"),  # it's ours, so it's a sale
        ("customer", "", "reason"),  # a reason is required
    ],
)
def test_reason_must_fit(
    client_for: Any, buyers: tuple[Customer, Customer], owner: str, reason: str, field: str
) -> None:
    sales = client_for("sales")
    u = new_stock_unit(sales)
    body: dict[str, Any] = {"owner_kind": owner, "reason": reason, "start_date": "2026-01-01"}
    if owner == "customer":
        body["customer"] = str(buyers[0].pk)
    res = change(sales, u["id"], **body)
    assert res.status_code == 400
    assert field in res.json()["fields"]


@pytest.mark.django_db
def test_sold_between_customers_needs_a_customer_owner(
    client_for: Any, buyers: tuple[Customer, Customer]
) -> None:
    sales = client_for("sales")
    u = new_stock_unit(sales, initial_owner_customer=str(buyers[0].pk), stock_status="")
    res = change(
        sales,
        u["id"],
        owner_kind="customer",
        customer=str(buyers[1].pk),
        reason="sold",
        start_date="2026-01-01",
    )
    assert res.status_code == 400
    assert "Sold between customers" in res.json()["fields"]["reason"][0]


@pytest.mark.django_db
def test_no_future_dates_and_hours_warning(
    client_for: Any, buyers: tuple[Customer, Customer]
) -> None:
    sales = client_for("sales")
    u = new_stock_unit(sales, initial_hours="4000")
    future = change(
        sales,
        u["id"],
        owner_kind="customer",
        customer=str(buyers[0].pk),
        reason="sold",
        start_date="2099-01-01",
    )
    assert future.status_code == 400
    assert "start_date" in future.json()["fields"]
    lower = change(
        sales,
        u["id"],
        owner_kind="customer",
        customer=str(buyers[0].pk),
        reason="sold",
        start_date="2026-01-01",
        hours="3500",
    )
    assert lower.status_code == 201
    assert "lower than" in lower.json()["hours_warning"]


@pytest.mark.django_db
def test_database_refuses_mismatched_reasons_and_negative_money(client_for: Any) -> None:
    u = new_stock_unit(client_for("admin"))
    record = OwnershipRecord.objects.get(unit_id=u["id"])
    record.reason = "trade_in"
    record.owner_kind = "customer"
    record.customer = Customer.objects.create(name="Pat Murphy")
    with pytest.raises(DatabaseError), transaction.atomic():
        record.save()
    record.refresh_from_db()
    record.price = Decimal("-1")
    with pytest.raises(DatabaseError), transaction.atomic():
        record.save()
    record.refresh_from_db()
    record.reason = "stolen"
    with pytest.raises(DatabaseError), transaction.atomic():
        record.save()


# --- Undo -----------------------------------------------------------------------------------


@pytest.mark.django_db
def test_admin_can_undo_the_latest_change(
    client_for: Any, buyers: tuple[Customer, Customer]
) -> None:
    admin = client_for("admin")
    u = new_stock_unit(admin)
    sold = change(
        admin,
        u["id"],
        owner_kind="customer",
        customer=str(buyers[0].pk),
        reason="sold",
        start_date="2025-06-01",
        price="27000",
        hours="40",
    ).json()
    assert sold["can_undo"] is True
    res = admin.post(f"{URL}/{u['id']}/undo-change", {"record": sold["id"]}, format="json")
    assert res.status_code == 200, res.json()
    assert res.json()["kept"] == []
    back = unit(admin, u["id"])
    assert (back["stock_status"], back["sale_price"], back["owner_kind"]) == (
        "available",
        None,
        "dealer",
    )
    history = admin.get(f"{URL}/{u['id']}/ownership").json()
    assert len(history) == 1 and history[0]["end_date"] is None
    assert not HourMeterReading.objects.filter(unit_id=u["id"], source="sale").exists()
    # Undone, not erased: the record is soft-deleted and in the audit log.
    assert OwnershipRecord.all_objects.get(pk=sold["id"]).is_deleted
    assert AuditLog.objects.filter(object_id=sold["id"], action="soft_delete").exists()


@pytest.mark.django_db
def test_undo_keeps_edits_made_since(client_for: Any, buyers: tuple[Customer, Customer]) -> None:
    admin = client_for("admin")
    u = new_stock_unit(admin)
    change(
        admin,
        u["id"],
        owner_kind="customer",
        customer=str(buyers[0].pk),
        reason="sold",
        start_date="2025-06-01",
    )
    back = change(
        admin,
        u["id"],
        owner_kind="dealer",
        reason="trade_in",
        start_date="2026-01-01",
        price="8000",
    ).json()
    admin.patch(f"{URL}/{u['id']}", {"stock_status": "available"}, format="json")
    res = admin.post(f"{URL}/{u['id']}/undo-change", {"record": back["id"]}, format="json")
    assert res.json()["kept"] == ["stock_status"]
    now = unit(admin, u["id"])
    assert now["stock_status"] == "available"  # edited since: kept
    assert now["condition"] == "new"  # put back
    assert now["cost"] == "21000.00"  # put back
    assert now["owner_name"] == "Katahdin Lumber"


@pytest.mark.django_db
def test_undo_only_the_latest_and_only_admins(
    client_for: Any, buyers: tuple[Customer, Customer]
) -> None:
    admin = client_for("admin")
    u = new_stock_unit(admin)
    first = change(
        admin,
        u["id"],
        owner_kind="customer",
        customer=str(buyers[0].pk),
        reason="sold",
        start_date="2025-06-01",
    ).json()
    latest = change(
        admin, u["id"], owner_kind="dealer", reason="trade_in", start_date="2026-01-01"
    ).json()
    stale = admin.post(f"{URL}/{u['id']}/undo-change", {"record": first["id"]}, format="json")
    assert stale.status_code == 400
    sales = client_for("sales")
    denied = sales.post(f"{URL}/{u['id']}/undo-change", {"record": latest["id"]}, format="json")
    assert denied.status_code == 403
    # The first owner on record can't be "undone".
    original = OwnershipRecord.objects.get(unit_id=u["id"], reason="")
    assert original.unit_changes is None


# --- Correcting a deal --------------------------------------------------------------------


@pytest.mark.django_db
def test_correct_a_deal_and_the_unit_follows(
    client_for: Any, buyers: tuple[Customer, Customer]
) -> None:
    sales = client_for("sales")
    u = new_stock_unit(sales)
    sold = change(
        sales,
        u["id"],
        owner_kind="customer",
        customer=str(buyers[0].pk),
        reason="sold",
        start_date="2025-06-01",
        price="2750",  # typo
    ).json()
    res = sales.patch(
        f"{RECORDS}/{sold['id']}",
        {"price": "27500", "reference": "INV-10500", "note": "Delivered"},
        format="json",
    )
    assert res.status_code == 200, res.json()
    assert (res.json()["price"], res.json()["reference"]) == ("27500.00", "INV-10500")
    assert unit(sales, u["id"])["sale_price"] == "27500.00"
    # A reason that doesn't fit is refused.
    bad = sales.patch(f"{RECORDS}/{sold['id']}", {"reason": "trade_in"}, format="json")
    assert bad.status_code == 400
    # Owner and date can't be edited here.
    sales.patch(f"{RECORDS}/{sold['id']}", {"start_date": "2020-01-01"}, format="json")
    assert OwnershipRecord.objects.get(pk=sold["id"]).start_date.isoformat() == "2025-06-01"


@pytest.mark.django_db
def test_correcting_an_old_deal_leaves_the_unit_alone(
    client_for: Any, buyers: tuple[Customer, Customer]
) -> None:
    sales = client_for("sales")
    u = new_stock_unit(sales)
    sold = change(
        sales,
        u["id"],
        owner_kind="customer",
        customer=str(buyers[0].pk),
        reason="sold",
        start_date="2025-06-01",
        price="27000",
    ).json()
    change(sales, u["id"], owner_kind="dealer", reason="buy_back", start_date="2026-01-01")
    sales.patch(f"{RECORDS}/{sold['id']}", {"price": "26000"}, format="json")
    assert unit(sales, u["id"])["sale_price"] is None


# --- Bought and sold list ------------------------------------------------------------------


def history_for(admin: APIClient, buyers: tuple[Customer, Customer]) -> dict[str, Any]:
    u = new_stock_unit(admin)
    change(
        admin,
        u["id"],
        owner_kind="customer",
        customer=str(buyers[0].pk),
        reason="sold",
        start_date="2025-01-10",
        price="28000",
        reference="INV-1",
    )
    change(
        admin,
        u["id"],
        owner_kind="dealer",
        reason="trade_in",
        start_date="2026-01-10",
        price="9000",
    )
    change(
        admin,
        u["id"],
        owner_kind="customer",
        customer=str(buyers[1].pk),
        reason="sold",
        start_date="2026-03-10",
        price="15000",
    )
    return u


@pytest.mark.django_db
def test_bought_and_sold_list_and_totals(
    client_for: Any, buyers: tuple[Customer, Customer]
) -> None:
    admin = client_for("admin")
    history_for(admin, buyers)
    rows = admin.get(CHANGES).json()["results"]
    assert [(r["from_label"], r["owner_label"], r["reason"]) for r in rows] == [
        ("Maine Material Handling stock", "Bangor Building Supply", "sold"),
        ("Katahdin Lumber", "Maine Material Handling stock", "trade_in"),
        ("Maine Material Handling stock", "Katahdin Lumber", "sold"),
    ]  # newest first; the first owner on record isn't a change
    assert admin.get(f"{CHANGES}?direction=in").json()["count"] == 1
    assert admin.get(f"{CHANGES}?direction=out").json()["count"] == 2
    assert admin.get(f"{CHANGES}?reason=trade_in").json()["count"] == 1
    assert admin.get(f"{CHANGES}?date_from=2026-01-01").json()["count"] == 2
    assert admin.get(f"{CHANGES}?date_to=2025-12-31&date_from=bad").json()["count"] == 1
    assert admin.get(f"{CHANGES}?q=katahdin").json()["count"] == 2
    assert admin.get(f"{CHANGES}?q=inv-1").json()["count"] == 1
    assert admin.get(f"{CHANGES}?q=c52c00999").json()["count"] == 3

    totals = admin.get(f"{CHANGES}/totals").json()
    assert totals["sold"] == {
        "count": 2,
        "total": "43000.00",
        "margin": "13000.00",  # (28000 - 21000) + (15000 - 9000)
        "with_margin": 2,
    }
    assert totals["came_back"] == {"count": 1, "total": "9000.00"}
    assert totals["between_customers"] == {"count": 0}


@pytest.mark.django_db
def test_customer_page_lists_units_they_used_to_own(
    client_for: Any, buyers: tuple[Customer, Customer]
) -> None:
    admin = client_for("admin")
    u = history_for(admin, buyers)
    former = admin.get(f"{URL}?scope=all&former_owner={buyers[0].pk}").json()["results"]
    assert [r["id"] for r in former] == [u["id"]]
    assert admin.get(f"{URL}?scope=all&former_owner={buyers[1].pk}").json()["count"] == 0


@pytest.mark.django_db
@pytest.mark.parametrize("role", ["service", "parts", "read_only"])
def test_prices_on_deals_hidden_from_other_roles(
    client_for: Any, buyers: tuple[Customer, Customer], role: str
) -> None:
    u = history_for(client_for("admin"), buyers)
    client = client_for(role)
    history = client.get(f"{URL}/{u['id']}/ownership").json()
    assert history and all("price" not in h and "cost" not in h for h in history)
    assert history[0]["reason_label"] == "Sold"
    if role == "read_only":
        rows = client.get(CHANGES).json()["results"]
        assert rows and all("price" not in r and "cost" not in r for r in rows)
        totals = client.get(f"{CHANGES}/totals").json()
        assert totals["sold"] == {"count": 2}


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("role", "can_change", "can_view_list", "can_undo"),
    [
        ("admin", True, True, True),
        ("sales", True, True, False),
        ("service", False, False, False),
        ("parts", False, False, False),
        ("read_only", False, True, False),
    ],
)
def test_changing_hands_role_matrix(
    client_for: Any,
    buyers: tuple[Customer, Customer],
    role: str,
    can_change: bool,
    can_view_list: bool,
    can_undo: bool,
) -> None:
    admin = client_for("admin")
    u = new_stock_unit(admin)
    record = OwnershipRecord.objects.get(unit_id=u["id"])
    client = client_for(role)
    sold = change(
        client,
        u["id"],
        owner_kind="customer",
        customer=str(buyers[0].pk),
        reason="sold",
        start_date="2026-01-01",
    )
    assert sold.status_code == (201 if can_change else 403)
    if not can_change:
        sold = change(
            admin,
            u["id"],
            owner_kind="customer",
            customer=str(buyers[0].pk),
            reason="sold",
            start_date="2026-01-01",
        )
    assert client.get(f"{RECORDS}/{record.pk}").status_code == 200
    edit = client.patch(f"{RECORDS}/{record.pk}", {"note": "checked"}, format="json")
    assert edit.status_code == (200 if can_change else 403)
    assert client.get(CHANGES).status_code == (200 if can_view_list else 403)
    assert client.get(f"{CHANGES}/totals").status_code == (200 if can_view_list else 403)
    undo = client.post(f"{URL}/{u['id']}/undo-change", {"record": sold.json()["id"]}, format="json")
    assert undo.status_code == (200 if can_undo else 403)


@pytest.mark.django_db
def test_anonymous_and_flags(client_for: Any, anon_client: APIClient) -> None:
    assert anon_client.get(CHANGES).status_code == 401
    assert anon_client.get(f"{RECORDS}/00000000-0000-0000-0000-000000000000").status_code == 401
    flag = FeatureFlag.objects.get(key="units-changing-hands")
    flag.enabled = False
    flag.save()
    admin = client_for("admin")
    assert admin.get(CHANGES).status_code == 404
    # The unit page's ownership history and changes keep working.
    u = new_stock_unit(admin)
    assert admin.get(f"{URL}/{u['id']}/ownership").status_code == 200
