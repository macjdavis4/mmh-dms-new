"""Phase 8: quotes, the quote PDF, and recording a sale with trade-ins."""

from decimal import Decimal
from typing import Any

import pytest
from django.db import DatabaseError, transaction
from django.test import override_settings
from rest_framework.test import APIClient

from apps.core.models import FeatureFlag
from apps.customers.models import Customer
from apps.sales.models import Quote, QuoteLine, Sale, SaleUnitChange
from apps.sales.totals import LineAmount, TradeAmount, compute
from apps.units import services as unit_services
from apps.units.models import HourMeterReading, OwnershipRecord, Unit

QUOTES = "/api/v1/quotes"
SALES = "/api/v1/sales"
UNITS = "/api/v1/units"


@pytest.fixture
def customer(db: Any) -> Customer:
    return Customer.objects.create(name="Katahdin Lumber", phone="207-555-0130")


@pytest.fixture
def stock_unit(db: Any) -> Unit:
    unit = Unit.objects.create(
        make="Hyundai",
        model="30L-9A",
        serial_number="HHKHFR30A00999",
        stock_number="MMH-2501",
        condition="new",
        stock_status="available",
        cost=Decimal("24000"),
        asking_price=Decimal("31900"),
    )
    unit_services.transfer_ownership(unit, owner_kind="dealer", start_date=_d("2025-06-01"))
    return unit


@pytest.fixture
def their_unit(customer: Customer) -> Unit:
    unit = Unit.objects.create(make="Doosan", model="G25N-7", serial_number="FGA25-70111")
    unit_services.transfer_ownership(
        unit, owner_kind="customer", customer=customer, start_date=_d("2019-04-01")
    )
    return unit


def _d(value: str) -> Any:
    from datetime import date

    return date.fromisoformat(value)


def quote_body(customer: Customer, unit: Unit | None = None, **extra: Any) -> dict[str, Any]:
    lines: list[dict[str, Any]] = []
    if unit is not None:
        lines.append({"kind": "unit", "unit": str(unit.pk), "unit_price": "31000"})
    lines += [
        {"kind": "attachment", "description": "Cascade side shifter", "unit_price": "2400"},
        {
            "kind": "delivery",
            "description": "Delivery to Millinocket",
            "unit_price": "350",
            "taxable": False,
        },
        {"kind": "discount", "description": "Fleet discount", "unit_price": "500"},
    ]
    return {
        "customer": str(customer.pk),
        "quote_date": "2026-09-01",
        "valid_until": "2026-12-31",
        "tax_rate": "5.5",
        "lines": lines,
        "trade_ins": [],
        **extra,
    }


def make_quote(client: APIClient, customer: Customer, unit: Unit | None, **extra: Any) -> Any:
    res = client.post(QUOTES, quote_body(customer, unit, **extra), format="json")
    assert res.status_code == 201, res.json()
    return res.json()


# --- Totals -----------------------------------------------------------------------------------


def test_totals_math() -> None:
    lines = [
        LineAmount(Decimal("1"), Decimal("31000"), True),
        LineAmount(Decimal("2"), Decimal("12.345"), True),  # rounds per line to the cent
        LineAmount(Decimal("1"), Decimal("350"), False),
        LineAmount(Decimal("1"), Decimal("-500"), True),
    ]
    trades = [TradeAmount(Decimal("9000"), Decimal("1200.5")), TradeAmount(Decimal("500"), None)]
    t = compute(lines, trades, tax_rate=Decimal("5.5"), tax_exempt=False)
    assert t.subtotal == Decimal("30874.69")
    assert t.trade_allowance == Decimal("9500.00")
    assert t.trade_payoff == Decimal("1200.50")
    assert t.taxable_amount == Decimal("21024.69")  # taxable lines less the allowance
    assert t.tax == Decimal("1156.36")
    assert t.total == Decimal("23731.55")  # 30874.69 - 9500 + 1200.50 + 1156.36
    exempt = compute(lines, trades, tax_rate=Decimal("5.5"), tax_exempt=True)
    assert (exempt.taxable_amount, exempt.tax) == (Decimal("0.00"), Decimal("0.00"))
    big_trade = compute(
        lines[:1], [TradeAmount(Decimal("40000"), None)], tax_rate=Decimal("5.5"), tax_exempt=False
    )
    assert big_trade.taxable_amount == Decimal("0.00")  # never below zero
    assert big_trade.total == Decimal("-9000.00")  # we owe the customer


# --- Quotes -----------------------------------------------------------------------------------


@pytest.mark.django_db
def test_create_quote_with_lines_and_trade_in(
    client_for: Any, customer: Customer, stock_unit: Unit, their_unit: Unit
) -> None:
    sales = client_for("sales")
    q = make_quote(
        sales,
        customer,
        stock_unit,
        trade_ins=[{"unit": str(their_unit.pk), "allowance": "6000", "hours": "11200"}],
        notes="Wants it before the snow",
    )
    assert q["number"].startswith("Q-3")
    assert q["status"] == "draft"
    assert q["salesperson_name"]  # defaults to whoever made it
    assert [x["kind"] for x in q["lines"]] == ["unit", "attachment", "delivery", "discount"]
    assert q["lines"][3]["unit_price"] == "-500.00"  # discounts always take money off
    assert q["lines"][0]["unit_summary"]["serial_number"] == "HHKHFR30A00999"
    assert q["totals"] == {
        "subtotal": "33250.00",
        "trade_allowance": "6000.00",
        "trade_payoff": "0.00",
        "taxable_amount": "26900.00",  # 31000 + 2400 - 500 - 6000 (delivery not taxed)
        "tax_rate": "5.500",
        "tax": "1479.50",
        "total": "28729.50",
    }
    listed = sales.get(QUOTES).json()["results"]
    assert listed[0]["total"] == "28729.50"
    assert listed[0]["units"] == ["Hyundai 30L-9A"]
    assert listed[0]["trade_in_count"] == 1


@pytest.mark.django_db
def test_edit_quote_lines(client_for: Any, customer: Customer, stock_unit: Unit) -> None:
    sales = client_for("sales")
    q = make_quote(sales, customer, stock_unit)
    keep = q["lines"][0]
    res = sales.patch(
        f"{QUOTES}/{q['id']}",
        {
            "lines": [
                {**keep, "unit_price": "30500"},
                {"kind": "other", "description": "Fuel tank", "unit_price": "95", "quantity": "2"},
            ]
        },
        format="json",
    )
    assert res.status_code == 200, res.json()
    lines = res.json()["lines"]
    assert [(x["id"] == keep["id"], x["amount"]) for x in lines] == [
        (True, "30500.00"),
        (False, "190.00"),
    ]
    assert QuoteLine.all_objects.filter(quote_id=q["id"], deleted_at__isnull=False).count() == 3


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("line", "field"),
    [
        ({"kind": "unit", "unit_price": "100"}, "unit"),
        ({"kind": "other", "description": "", "unit_price": "100"}, "description"),
        ({"kind": "other", "description": "Credit", "unit_price": "-100"}, "unit_price"),
        ({"kind": "other", "description": "Mats", "unit_price": "10", "quantity": "0"}, "quantity"),
    ],
)
def test_line_validation(client_for: Any, customer: Customer, line: Any, field: str) -> None:
    res = client_for("sales").post(
        QUOTES, {"customer": str(customer.pk), "lines": [line]}, format="json"
    )
    assert res.status_code == 400
    assert field in str(res.json()["fields"])


@pytest.mark.django_db
def test_same_unit_twice_and_bad_dates(
    client_for: Any, customer: Customer, stock_unit: Unit
) -> None:
    sales = client_for("sales")
    line = {"kind": "unit", "unit": str(stock_unit.pk), "unit_price": "1"}
    twice = sales.post(QUOTES, {"customer": str(customer.pk), "lines": [line, line]}, format="json")
    assert twice.status_code == 400
    assert "twice" in str(twice.json())
    backwards = sales.post(
        QUOTES,
        {"customer": str(customer.pk), "quote_date": "2026-09-01", "valid_until": "2026-08-01"},
        format="json",
    )
    assert "valid_until" in backwards.json()["fields"]


@pytest.mark.django_db
def test_database_refuses_bad_lines(customer: Customer, stock_unit: Unit) -> None:
    quote = Quote.objects.create(customer=customer)
    for bad in (
        {"kind": "unit", "unit_price": Decimal("1")},  # unit line without a unit
        {"kind": "other", "description": "x", "unit_price": Decimal("-1")},
        {"kind": "discount", "description": "x", "unit_price": Decimal("5")},
        {"kind": "other", "description": "x", "unit": stock_unit, "unit_price": Decimal("1")},
    ):
        with pytest.raises(DatabaseError), transaction.atomic():
            QuoteLine.objects.create(quote=quote, **bad)


@pytest.mark.django_db
def test_status_changes(client_for: Any, customer: Customer, stock_unit: Unit) -> None:
    sales = client_for("sales")
    q = make_quote(sales, customer, stock_unit)
    url = f"{QUOTES}/{q['id']}/status"
    sent = sales.post(url, {"status": "sent"}, format="json").json()
    assert sent["status"] == "sent" and sent["sent_at"]
    declined = sales.post(url, {"status": "declined"}, format="json").json()
    assert declined["status"] == "declined" and declined["is_open"] is False
    locked = sales.patch(f"{QUOTES}/{q['id']}", {"attention": "Morgan"}, format="json")
    assert locked.status_code == 400
    assert sales.post(url, {"status": "accepted"}, format="json").status_code == 400
    assert sales.post(url, {"status": "draft"}, format="json").json()["status"] == "draft"
    assert sales.post(url, {"status": "sold"}, format="json").status_code == 400


@pytest.mark.django_db
def test_expired(client_for: Any, customer: Customer) -> None:
    q = make_quote(
        client_for("sales"), customer, None, quote_date="2026-01-01", valid_until="2026-01-31"
    )
    assert q["is_expired"] is True


# --- Recording the sale ---------------------------------------------------------------------


@pytest.mark.django_db
def test_record_sale_with_trade_ins(
    client_for: Any, customer: Customer, stock_unit: Unit, their_unit: Unit
) -> None:
    sales = client_for("sales")
    q = make_quote(
        sales,
        customer,
        stock_unit,
        trade_ins=[
            {"unit": str(their_unit.pk), "allowance": "6000", "hours": "11200"},
            {
                "make": "Clark",
                "model": "C25",
                "serial_number": "C232-0099",
                "year": 2008,
                "hours": "18000",
                "allowance": "1500",
                "payoff": "800",
                "payoff_to": "Bangor Savings",
                "description": "Needs mast chains",
            },
        ],
    )
    assert sales.get(f"{QUOTES}/{q['id']}/sell").json() == {"problems": {}}
    res = sales.post(
        f"{QUOTES}/{q['id']}/sell",
        {
            "sale_date": "2026-10-01",
            "invoice_number": "INV-10600",
            "hours": {str(stock_unit.pk): "8"},
        },
        format="json",
    )
    assert res.status_code == 201, res.json()
    body = res.json()
    assert body["status"] == "sold"
    sale = Sale.objects.get(pk=body["sale"]["id"])
    assert sale.number.startswith("S-4")
    assert (sale.total, sale.trade_allowance, sale.trade_payoff) == (
        Decimal("27947.00"),  # 33250 - 7500 + 800 + 1397 (5.5% of 32900 - 7500)
        Decimal("7500.00"),
        Decimal("800.00"),
    )

    # The unit we sold now belongs to the customer, with the deal's price.
    stock_unit.refresh_from_db()
    assert stock_unit.stock_status == "sold"
    assert stock_unit.sale_price == Decimal("31000.00")
    sold = unit_services.open_ownership(stock_unit)
    assert sold is not None
    assert (sold.customer_id, sold.reason, sold.price, sold.cost) == (
        customer.pk,
        "sold",
        Decimal("31000.00"),
        Decimal("24000.00"),
    )
    assert sold.reference == f"{sale.number} / INV-10600"
    assert HourMeterReading.objects.filter(unit=stock_unit, hours=8, source="sale").exists()

    # Their unit came into our stock as a trade-in at the allowance.
    their_unit.refresh_from_db()
    assert (their_unit.stock_status, their_unit.condition, their_unit.cost) == (
        "in_prep",
        "used",
        Decimal("6000.00"),
    )
    # The described trade-in became a unit: first the customer's, then ours.
    clark = Unit.objects.get(serial_number="C232-0099")
    history = list(clark.ownerships.order_by("start_date", "created_at"))
    assert [(h.owner_kind, h.reason) for h in history] == [("customer", ""), ("dealer", "trade_in")]
    assert clark.notes == "Needs mast chains"
    assert clark.cost == Decimal("1500.00")
    changes = SaleUnitChange.objects.filter(sale=sale)
    assert sorted(c.kind for c in changes) == ["sold", "trade_in", "trade_in"]
    assert changes.get(ownership__unit=clark).created_unit is True

    # A sold quote is locked.
    assert sales.patch(f"{QUOTES}/{q['id']}", {"notes": "x"}, format="json").status_code == 400
    assert sales.get(f"{SALES}?status=completed").json()["results"][0]["number"] == sale.number


@pytest.mark.django_db
def test_what_stops_a_sale(
    client_for: Any, customer: Customer, stock_unit: Unit, their_unit: Unit
) -> None:
    sales = client_for("sales")
    other = Customer.objects.create(name="Pat Murphy")
    unit_services.change_hands(
        stock_unit,
        owner_kind="customer",
        customer=other,
        reason="sold",
        start_date=_d("2026-02-01"),
    )
    q = make_quote(
        sales,
        customer,
        stock_unit,
        trade_ins=[{"serial_number": "FGA25 70111", "model": "G25N-7", "allowance": "1"}],
    )
    problems = sales.get(f"{QUOTES}/{q['id']}/sell").json()["problems"]
    assert "Pat Murphy owns it" in problems["lines"][0]
    assert "already on" in problems["trade_ins"][0]
    res = sales.post(f"{QUOTES}/{q['id']}/sell", {"sale_date": "2026-10-01"}, format="json")
    assert res.status_code == 400
    assert Sale.objects.count() == 0  # nothing half done
    future = sales.post(f"{QUOTES}/{q['id']}/sell", {"sale_date": "2099-01-01"}, format="json")
    assert "sale_date" in future.json()["fields"]


@pytest.mark.django_db
def test_sale_date_before_we_owned_it(
    client_for: Any, customer: Customer, stock_unit: Unit
) -> None:
    sales = client_for("sales")
    q = make_quote(sales, customer, stock_unit)
    res = sales.post(f"{QUOTES}/{q['id']}/sell", {"sale_date": "2025-01-01"}, format="json")
    assert res.status_code == 400
    assert "Hyundai 30L-9A" in res.json()["fields"]["sale_date"][0]


@pytest.mark.django_db
def test_void_sale_and_sell_again(
    client_for: Any, customer: Customer, stock_unit: Unit, their_unit: Unit
) -> None:
    admin = client_for("admin")
    q = make_quote(
        admin, customer, stock_unit, trade_ins=[{"unit": str(their_unit.pk), "allowance": "6000"}]
    )
    sold = admin.post(f"{QUOTES}/{q['id']}/sell", {"sale_date": "2026-10-01"}, format="json").json()
    sale_id = sold["sale"]["id"]
    assert (
        client_for("sales")
        .post(f"{SALES}/{sale_id}/void", {"reason": "x"}, format="json")
        .status_code
        == 403
    )
    no_reason = admin.post(f"{SALES}/{sale_id}/void", {"reason": " "}, format="json")
    assert no_reason.status_code == 400
    res = admin.post(
        f"{SALES}/{sale_id}/void", {"reason": "Customer's financing fell through"}, format="json"
    )
    assert res.status_code == 200, res.json()
    assert res.json()["status"] == "voided"
    stock_unit.refresh_from_db()
    their_unit.refresh_from_db()
    assert (stock_unit.stock_status, stock_unit.sale_price) == ("available", None)
    assert unit_services.open_ownership(their_unit).customer_id == customer.pk  # type: ignore[union-attr]
    quote = admin.get(f"{QUOTES}/{q['id']}").json()
    assert (quote["status"], quote["sale"], len(quote["past_sales"])) == ("accepted", None, 1)
    again = admin.post(f"{QUOTES}/{q['id']}/sell", {"sale_date": "2026-10-02"}, format="json")
    assert again.status_code == 201, again.json()


@pytest.mark.django_db
def test_void_refused_once_a_unit_moved_on(
    client_for: Any, customer: Customer, stock_unit: Unit
) -> None:
    admin = client_for("admin")
    q = make_quote(admin, customer, stock_unit)
    sale_id = admin.post(
        f"{QUOTES}/{q['id']}/sell", {"sale_date": "2026-10-01"}, format="json"
    ).json()["sale"]["id"]
    unit_services.change_hands(
        stock_unit, owner_kind="dealer", reason="buy_back", start_date=_d("2026-10-03")
    )
    res = admin.post(f"{SALES}/{sale_id}/void", {"reason": "Mistake"}, format="json")
    assert res.status_code == 400
    assert "changed hands again" in str(res.json())


@pytest.mark.django_db
def test_sold_quote_cannot_be_removed(
    client_for: Any, customer: Customer, stock_unit: Unit
) -> None:
    admin = client_for("admin")
    q = make_quote(admin, customer, stock_unit)
    admin.post(f"{QUOTES}/{q['id']}/sell", {"sale_date": "2026-10-01"}, format="json")
    assert admin.delete(f"{QUOTES}/{q['id']}").status_code == 400
    draft = make_quote(admin, customer, None)
    assert admin.delete(f"{QUOTES}/{draft['id']}").status_code == 204
    assert admin.post(f"{QUOTES}/{draft['id']}/restore").status_code == 200


# --- PDF, search, lists -------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(PDF_COMPRESS=False)
def test_quote_pdf(client_for: Any, customer: Customer, stock_unit: Unit, their_unit: Unit) -> None:
    sales = client_for("sales")
    q = make_quote(
        sales,
        customer,
        stock_unit,
        notes="Secret: they'd pay 32k",
        trade_ins=[{"unit": str(their_unit.pk), "allowance": "6000"}],
    )
    res = sales.get(f"{QUOTES}/{q['id']}/pdf")
    assert res.status_code == 200
    assert res["Content-Type"] == "application/pdf"
    assert f'filename="{q["number"]}.pdf"' in res["Content-Disposition"]
    body = res.content
    for expected in (
        q["number"],
        "Katahdin Lumber",
        "HHKHFR30A00999",
        "Trade-in allowance",
        "$28,729.50",
        "Fleet discount",
        "FGA25-70111",
    ):
        assert expected.encode() in body, expected
    assert b"Secret" not in body  # internal notes are never printed
    assert b"24,000" not in body  # nor our cost


@pytest.mark.django_db
def test_list_scopes_and_search(client_for: Any, customer: Customer, stock_unit: Unit) -> None:
    sales = client_for("sales")
    q = make_quote(sales, customer, stock_unit, customer_po="PO-777")
    make_quote(sales, Customer.objects.create(name="Pat Murphy"), None)
    assert sales.get(QUOTES).json()["count"] == 2
    assert sales.get(f"{QUOTES}?q=katahdin").json()["count"] == 1
    assert sales.get(f"{QUOTES}?q=HHKHFR30A").json()["count"] == 1
    assert sales.get(f"{QUOTES}?q=PO-777").json()["count"] == 1
    assert sales.get(f"{QUOTES}?unit={stock_unit.pk}").json()["count"] == 1
    sales.post(f"{QUOTES}/{q['id']}/sell", {"sale_date": "2026-10-01"}, format="json")
    assert sales.get(QUOTES).json()["count"] == 1  # open only by default
    assert sales.get(f"{QUOTES}?scope=sold").json()["results"][0]["sale_number"].startswith("S-")
    assert sales.get(f"{QUOTES}?scope=all").json()["count"] == 2

    found = sales.get(f"/api/v1/search?q={q['number']}").json()
    assert found["groups"]["quote"][0]["url"] == f"/sales/{q['id']}"
    hidden = client_for("service").get(f"/api/v1/search?q={q['number']}").json()
    assert hidden["groups"]["quote"] == []


# --- Roles and flag ----------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("role", ["admin", "sales", "service", "parts", "read_only"])
def test_sales_role_matrix(
    client_for: Any, customer: Customer, stock_unit: Unit, role: str
) -> None:
    allowed = role in ("admin", "sales")
    q = make_quote(client_for("admin"), customer, stock_unit)
    client = client_for(role)

    def expect(ok: int) -> int:
        return ok if allowed else 403

    assert client.get(QUOTES).status_code == expect(200)
    assert client.get(f"{QUOTES}/{q['id']}").status_code == expect(200)
    assert client.get(f"{QUOTES}/{q['id']}/pdf").status_code == expect(200)
    assert client.post(QUOTES, quote_body(customer), format="json").status_code == expect(201)
    assert client.patch(
        f"{QUOTES}/{q['id']}", {"attention": role}, format="json"
    ).status_code == expect(200)
    assert client.post(
        f"{QUOTES}/{q['id']}/status", {"status": "sent"}, format="json"
    ).status_code == expect(200)
    assert client.get(f"{QUOTES}/{q['id']}/sell").status_code == expect(200)
    assert client.get(SALES).status_code == expect(200)
    sold = client.post(f"{QUOTES}/{q['id']}/sell", {"sale_date": "2026-10-01"}, format="json")
    assert sold.status_code == expect(201)
    other = make_quote(client_for("admin"), customer, None)
    assert client.delete(f"{QUOTES}/{other['id']}").status_code == (204 if role == "admin" else 403)


@pytest.mark.django_db
def test_anonymous_and_flag(client_for: Any, anon_client: APIClient) -> None:
    assert anon_client.get(QUOTES).status_code == 401
    assert anon_client.get(SALES).status_code == 401
    flag = FeatureFlag.objects.get(key="sales")
    flag.enabled = False
    flag.save()
    assert client_for("admin").get(QUOTES).status_code == 404


@pytest.mark.django_db
def test_sold_unit_reference_in_bought_and_sold(
    client_for: Any, customer: Customer, stock_unit: Unit
) -> None:
    admin = client_for("admin")
    q = make_quote(admin, customer, stock_unit)
    sale = admin.post(
        f"{QUOTES}/{q['id']}/sell", {"sale_date": "2026-10-01"}, format="json"
    ).json()["sale"]
    rows = admin.get(f"/api/v1/unit-changes?q={sale['number']}").json()["results"]
    assert [r["reason"] for r in rows] == ["sold"]
    assert OwnershipRecord.objects.filter(reference=sale["number"]).count() == 1


@pytest.mark.django_db
def test_demo_quotes_load_once() -> None:
    from apps.sales.demo import load_demo_quotes
    from apps.units.demo import load_demo_data

    load_demo_data(with_files=False)
    load_demo_quotes()
    load_demo_quotes()
    assert sorted(Quote.objects.values_list("status", flat=True)) == [
        "accepted",
        "draft",
        "sent",
        "sold",
    ]
    sale = Sale.objects.get()
    assert sale.invoice_number == "INV-10571"
    clark = Unit.objects.get(serial_number="C500-Y60-4471")
    assert (clark.stock_status, clark.cost) == ("in_prep", Decimal("3000.00"))
