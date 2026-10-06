"""Phase 12: dashboard tiles and reports."""

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.core.models import FeatureFlag
from apps.parts import stock
from apps.parts.models import Part
from apps.reports import periods
from apps.reports.registry import csv_text
from apps.service import services as service_services
from apps.service.models import WorkOrder
from apps.units.models import Unit

DASH = "/api/v1/dashboard"
REPORTS = "/api/v1/reports"
ALL_KEYS = {
    "units-sold",
    "units-in-stock",
    "parts-valuation",
    "parts-used",
    "parts-received",
    "labor-by-mechanic",
    "work-orders-completed",
}


@pytest.fixture
def demo(db: Any, make_user: Any) -> None:
    """The same demo data the seed command loads."""
    from apps.parts.demo import load_demo_invoices, load_demo_parts, load_demo_stock
    from apps.sales.demo import load_demo_quotes
    from apps.service.demo import load_demo_plans, load_demo_work_orders
    from apps.units.demo import load_demo_data

    sam = make_user("service", email="service@mmh.test")
    sam.first_name, sam.last_name = "Sam", "Wrench"
    sam.save()
    make_user("sales", email="sales@mmh.test")
    load_demo_data(with_files=False)
    load_demo_work_orders()
    load_demo_plans()
    load_demo_quotes()
    load_demo_parts()
    load_demo_stock()
    load_demo_invoices()


def report(client: APIClient, key: str, **params: str) -> dict[str, Any]:
    res = client.get(f"{REPORTS}/{key}", params)
    assert res.status_code == 200, res.content
    return res.json()  # type: ignore[no-any-return]


# --- Periods and CSV safety ----------------------------------------------------------------


def test_period_presets() -> None:
    today = date(2026, 10, 6)
    assert periods.preset("this_month", today) == periods.Period(
        date(2026, 10, 1), today, "this_month"
    )
    last = periods.preset("last_month", date(2026, 1, 15))
    assert (last.start, last.end) == (date(2025, 12, 1), date(2025, 12, 31))
    assert periods.preset("last_12_months", today).start == date(2025, 11, 1)
    assert periods.preset("last_12_months", date(2026, 12, 2)).start == date(2026, 1, 1)
    assert periods.preset("last_year", today).end == date(2025, 12, 31)
    custom = periods.from_params({"from": "2026-01-01", "to": "2026-03-31"})
    assert custom.label == "Jan 1, 2026 to Mar 31, 2026"
    for bad in ({"from": "2026-03-01", "to": "2026-01-01"}, {"from": "x", "to": "y"}):
        with pytest.raises(ValidationError):
            periods.from_params(bad)
    with pytest.raises(ValidationError):
        periods.from_params({"period": "forever"})


def test_csv_cells_cant_become_formulas() -> None:
    assert csv_text("=HYPERLINK(1)") == "'=HYPERLINK(1)"
    assert csv_text("@SUM(A1)") == "'@SUM(A1)"
    assert csv_text("-470.00") == "-470.00"  # a negative number stays a number
    assert csv_text("31N4-01050") == "31N4-01050"
    assert csv_text(None) == ""


# --- Dashboard -----------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("role", "has", "hasnt"),
    [
        (
            "admin",
            {
                "open-quotes",
                "sales-this-month",
                "parts-value",
                "invoices-to-check",
                "my-work-orders",
            },
            set(),
        ),
        (
            "sales",
            {"open-quotes", "sales-this-month", "parts-value", "backorders"},
            {"my-work-orders"},
        ),
        (
            "service",
            {"open-work-orders", "my-work-orders", "maintenance-due", "low-stock"},
            {"open-quotes", "sales-this-month", "parts-value", "invoices-to-check"},
        ),
        (
            "parts",
            {"low-stock", "parts-value", "invoices-to-check"},
            {"open-quotes", "sales-this-month"},
        ),
        (
            "read_only",
            {"units-in-stock", "open-work-orders", "low-stock"},
            {"parts-value", "sales-this-month", "invoices-to-check", "open-quotes"},
        ),
    ],
)
def test_dashboard_tiles_by_role(
    client_for: Any, demo: None, role: str, has: set[str], hasnt: set[str]
) -> None:
    tiles = {t["key"]: t for t in client_for(role).get(DASH).json()["tiles"]}
    assert has <= set(tiles), tiles.keys()
    assert not (hasnt & set(tiles))


@pytest.mark.django_db
def test_dashboard_numbers(client_for: Any, demo: None) -> None:
    tiles = {t["key"]: t for t in client_for("admin").get(DASH).json()["tiles"]}
    assert tiles["invoices-to-check"]["value"] == "1"
    assert tiles["invoices-to-check"]["tone"] == "warning"
    assert tiles["backorders"]["value"] == "1"
    assert tiles["low-stock"]["value"] == "5"
    assert tiles["parts-value"]["kind"] == "money"
    valuation = report(client_for("admin"), "parts-valuation")
    assert tiles["parts-value"]["value"] == valuation["totals"]["value"]
    assert tiles["parts-value"]["to"] == "/reports/parts-valuation"
    stocked = report(client_for("admin"), "units-in-stock")
    assert tiles["units-in-stock"]["value"] == str(len(stocked["rows"]))


@pytest.mark.django_db
def test_dashboard_follows_flags(client_for: Any, demo: None) -> None:
    for flag in FeatureFlag.objects.filter(key__in=("parts-stock", "sales", "reports")):
        flag.enabled = False
        flag.save()
    tiles = {t["key"]: t for t in client_for("admin").get(DASH).json()["tiles"]}
    assert "low-stock" not in tiles and "open-quotes" not in tiles
    assert tiles["units-in-stock"]["to"] == "/units"  # no report to link to
    assert client_for("admin").get(REPORTS).status_code == 404


# --- Reports -------------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("role", "allowed"),
    [
        ("admin", ALL_KEYS),
        ("sales", ALL_KEYS - {"labor-by-mechanic"}),
        ("service", {"parts-used", "labor-by-mechanic", "work-orders-completed"}),
        ("parts", {"parts-valuation", "parts-used", "parts-received", "work-orders-completed"}),
        ("read_only", {"parts-used", "work-orders-completed"}),
    ],
)
def test_report_role_matrix(client_for: Any, demo: None, role: str, allowed: set[str]) -> None:
    client = client_for(role)
    listed = {r["key"] for r in client.get(REPORTS).json()["reports"]}
    assert listed == allowed
    for key in ALL_KEYS:
        res = client.get(f"{REPORTS}/{key}")
        assert res.status_code == (200 if key in allowed else 403), (key, res.content)
        csv = client.get(f"{REPORTS}/{key}", {"download": "csv"})
        assert csv.status_code == (200 if key in allowed else 403)
    assert client.get(f"{REPORTS}/nope").status_code == 404


@pytest.mark.django_db
def test_units_sold_and_in_stock(client_for: Any, demo: None) -> None:
    sales = client_for("sales")
    sold = report(sales, "units-sold", **{"from": "2026-03-01", "to": "2026-03-31"})
    assert sold["period"]["label"] == "Mar 1, 2026 to Mar 31, 2026"
    assert len(sold["rows"]) == 1
    row = sold["rows"][0]
    assert Decimal(row["margin"]) == Decimal(row["price"]) - Decimal(row["cost"])
    assert row["_to"].startswith("/units/")
    assert sold["totals"]["unit"] == "1 sold"
    stocked = report(sales, "units-in-stock")
    assert stocked["period"]["label"] == "Today"
    statuses = {r["status"] for r in stocked["rows"]}
    assert statuses <= {"Available", "On hold", "In prep"}
    days = [r["days"] for r in stocked["rows"] if r["days"] is not None]
    assert days == sorted(days, reverse=True)  # oldest first


@pytest.mark.django_db
def test_parts_valuation_and_received(client_for: Any, demo: None) -> None:
    parts = client_for("parts")
    valuation = report(parts, "parts-valuation")
    oil = next(r for r in valuation["rows"] if r["part_number"] == "31N4-01050")
    assert (oil["on_hand"], oil["cost"], oil["value"]) == ("20", "9.80", "196.00")
    total = sum(Decimal(r["value"]) for r in valuation["rows"] if r["value"])
    assert Decimal(valuation["totals"]["value"]) == total
    assert any(n.startswith("By category:") for n in valuation["notes"])
    received = report(parts, "parts-received", period="this_month")
    refs = {r["reference"]: r for r in received["rows"]}
    assert refs["HMA-558790"]["supplier"] == "Hyundai parts"
    assert refs["HMA-558790"]["quantity"] == "6"  # 4 air filters + 2 switches
    assert refs["HMA-558790"]["value"] == "122.60"
    assert refs["HMA-558790"]["_to"].startswith("/parts/invoices/")
    assert "Hyundai invoice 55120 (demo)" in refs  # typed in on the part page


@pytest.mark.django_db
def test_parts_used_hides_cost_from_mechanics(client_for: Any, demo: None) -> None:
    oil = Part.objects.get(part_number="31N4-01050")
    unit = Unit.objects.create(make="Hyundai", model="25L-9A", serial_number="RPT-1")
    wo = WorkOrder.objects.create(unit=unit, complaint="Service")
    stock.issue(oil, wo, Decimal("3"))
    stock.return_to_stock(oil, wo, Decimal("1"))
    admin = report(client_for("admin"), "parts-used")
    row = next(r for r in admin["rows"] if r["part_number"] == "31N4-01050")
    assert (row["quantity"], row["jobs"], row["price"], row["cost"]) == ("2", 1, "37.00", "19.60")
    mechanic = report(client_for("service"), "parts-used")
    assert "cost" not in {c["key"] for c in mechanic["columns"]}
    assert all("cost" not in r for r in mechanic["rows"])
    assert "cost" not in mechanic["totals"]
    csv = client_for("service").get(f"{REPORTS}/parts-used", {"download": "csv"})
    assert "Our cost" not in csv.content.decode()


@pytest.mark.django_db
def test_service_reports(client_for: Any, demo: None, make_user: Any) -> None:
    labor = report(client_for("service"), "labor-by-mechanic", period="last_12_months")
    sam = next(r for r in labor["rows"] if r["mechanic"] == "Sam Wrench")
    assert Decimal(sam["hours"]) > 0
    assert labor["totals"]["hours"] == sam["hours"]  # the only mechanic in the demo
    done = report(client_for("read_only"), "work-orders-completed", period="last_12_months")
    assert [r["kind"] for r in done["rows"]] == ["Planned maintenance"]
    row = done["rows"][0]
    assert row["hours"] == "2"
    assert row["_to"].startswith("/service/")
    # Completing a job today shows up in this month's report.
    wo = WorkOrder.objects.filter(status__in=WorkOrder.OPEN_STATUSES).first()
    assert wo is not None
    wo.correction = "Done"
    wo.save()
    service_services.change_status(wo, "completed")
    month = report(client_for("admin"), "work-orders-completed")
    assert wo.number in [r["number"] for r in month["rows"]]


@pytest.mark.django_db
def test_csv_download(client_for: Any, demo: None) -> None:
    res = client_for("parts").get(f"{REPORTS}/parts-valuation", {"download": "csv"})
    assert res["Content-Type"] == "text/csv; charset=utf-8"
    assert res["Content-Disposition"].startswith('attachment; filename="parts-valuation-')
    text = res.content.decode("utf-8-sig")
    lines = text.strip().splitlines()
    assert lines[0] == "Part #,Description,Category,Bin,On hand,Cost each,Value"
    assert any(line.startswith("31N4-01050,Engine oil filter") for line in lines)
    assert lines[-1].startswith("12 parts,")  # the totals row


@pytest.mark.django_db
def test_bad_period_and_anonymous(client_for: Any, anon_client: APIClient) -> None:
    res = client_for("admin").get(
        f"{REPORTS}/parts-used", {"from": "2026-02-01", "to": "2026-01-01"}
    )
    assert res.status_code == 400
    assert anon_client.get(DASH).status_code in (401, 403)
    assert anon_client.get(REPORTS).status_code in (401, 403)
