"""Phase 11: supplier invoices (upload, reading, checking, receiving, backorders)."""

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError, connection, transaction
from rest_framework.test import APIClient

from apps.core.models import FeatureFlag
from apps.parts import invoice_reader, invoices, sample_invoice, stock
from apps.parts.models import Invoice, InvoiceLine, Part, StockMovement
from apps.service.models import WorkOrder
from apps.units.models import Unit

URL = "/api/v1/parts-invoices"
LINES = "/api/v1/parts-invoice-lines"


@pytest.fixture
def catalog(db: Any) -> None:
    from apps.parts.demo import load_demo_parts

    load_demo_parts()


def part(number: str) -> Part:
    return Part.objects.get(part_number=number)


def upload(client: APIClient, data: bytes, name: str = "invoice.pdf", **extra: Any) -> Any:
    return client.post(URL, {"file": SimpleUploadedFile(name, data), **extra}, format="multipart")


def uploaded(
    client: APIClient, data: bytes | None = None, name: str = "invoice.pdf"
) -> dict[str, Any]:
    res = upload(client, data if data is not None else sample_invoice.pdf(), name)
    assert res.status_code == 201, res.json()
    return res.json()  # type: ignore[no-any-return]


def lines_by_number(invoice: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {line["part_number"]: line for line in invoice["lines"]}


# --- Reading -------------------------------------------------------------------------------


def test_parse_line_layouts() -> None:
    a = invoice_reader.parse_line("31N4-01050  ENGINE OIL FILTER   12   9.80   117.60")
    assert a is not None
    assert (a.part_number, a.description, a.quantity_shipped, a.unit_cost) == (
        "31N4-01050",
        "ENGINE OIL FILTER",
        Decimal("12"),
        Decimal("9.80"),
    )
    assert a.check_reason == ""
    b = invoice_reader.parse_line("  8    6   2   31N4-01060   FUEL FILTER   14.25   85.50")
    assert b is not None
    assert (b.quantity_shipped, b.quantity_backordered) == (Decimal("6"), Decimal("2"))
    c = invoice_reader.parse_line("10 8 31N4-01060 FUEL FILTER $14.25 $114.00")
    assert c is not None
    assert (c.quantity_shipped, c.quantity_backordered) == (Decimal("8"), Decimal("2"))
    assert c.check_reason == ""  # extended on the quantity ordered is fine
    wrong = invoice_reader.parse_line("31N4-01050 OIL FILTER 12 9.80 100.00")
    assert wrong is not None and "doesn't match" in wrong.check_reason
    nopart = invoice_reader.parse_line("SHOP RAGS BOX 2 5.00 10.00")
    assert nopart is not None and "No part number" in nopart.check_reason
    core = invoice_reader.parse_line("1 CORE CHARGE 45.00 45.00")
    assert core is not None and core.not_stocked
    assert invoice_reader.parse_line("Sold to: Maine Material Handling") is None
    assert invoice_reader.parse_line("Phone 207-555-0101") is None


def test_parse_dates_and_money() -> None:
    assert invoice_reader.parse_date("Date: 10/01/2026") == date(2026, 10, 1)
    assert invoice_reader.parse_date("2026-09-30") == date(2026, 9, 30)
    assert invoice_reader.parse_date("Shipped Oct 2, 2026") == date(2026, 10, 2)
    assert invoice_reader.parse_date("3 Sept 2026") == date(2026, 9, 3)
    assert invoice_reader.parse_date("13/45/2026 nothing") is None
    assert invoice_reader.money("$1,234.50") == Decimal("1234.50")
    assert invoice_reader.money("12") is None


def test_suggest_from_sample_text() -> None:
    s = invoice_reader.suggest("\n".join(sample_invoice.text_lines()))
    assert s.invoice_number == "HMA-558812"
    assert s.invoice_date == date(2026, 10, 1)
    assert (s.total, s.freight) == (Decimal("564.90"), Decimal("35.00"))
    assert [line.part_number for line in s.lines] == [row[3] for row in sample_invoice.LINES]


@pytest.mark.django_db
def test_upload_pdf_is_read_and_matched(client_for: Any, catalog: None) -> None:
    inv = uploaded(client_for("parts"))
    assert inv["status"] == "review"
    assert inv["read_method"] == "pdf-text"
    assert inv["supplier"] == "Hyundai parts"  # a supplier we already buy from
    assert inv["invoice_number"] == "HMA-558812"
    assert inv["invoice_date"] == "2026-10-01"
    assert (inv["total"], inv["freight"]) == ("564.90", "35.00")
    assert inv["lines_total"] == "529.90"
    assert inv["has_file"] is True and "HMA-558812" in inv["extracted_text"]
    lines = lines_by_number(inv)
    assert lines["31N4-01050"]["part_summary"]["part_number"] == "31N4-01050"
    assert lines["31N4-01060"]["quantity_backordered"] == "2.00"
    # A replaced number leads to the part that replaced it.
    assert lines["XKBH-00117"]["part_summary"]["part_number"] == "XKBH-00117A"
    unknown = lines["99Z9-12345"]
    assert unknown["part"] is None
    assert "not in the catalog" in unknown["check_reason"]
    assert all(line["raw_text"] for line in inv["lines"])  # kept as read
    file = client_for("parts").get(f"{URL}/{inv['id']}/file")
    assert file.status_code == 200 and file["Content-Type"] == "application/pdf"


@pytest.mark.django_db
def test_upload_photo_is_read_with_ocr(client_for: Any, catalog: None) -> None:
    inv = uploaded(client_for("parts"), sample_invoice.png(), "photo.png")
    assert inv["read_method"] == "ocr"
    assert inv["invoice_number"] == "HMA-558812"
    matched = [line for line in inv["lines"] if line["part"]]
    assert len(matched) >= 4
    assert inv["is_image"] is True


@pytest.mark.django_db
def test_scanned_pdf_is_read_with_ocr(client_for: Any, catalog: None) -> None:
    inv = uploaded(client_for("parts"), sample_invoice.scanned_pdf(), "scan.pdf")
    assert inv["read_method"] == "ocr"
    assert inv["invoice_number"] == "HMA-558812"
    assert len([line for line in inv["lines"] if line["part"]]) >= 4


@pytest.mark.django_db
def test_files_that_cant_be_read(client_for: Any) -> None:
    parts = client_for("parts")
    assert upload(parts, b"just some text", "notes.txt").status_code == 400
    assert upload(parts, b"", "empty.pdf").status_code == 400
    broken = upload(parts, b"%PDF-1.4 this is not really a pdf", "broken.pdf")
    assert broken.status_code == 201
    assert broken.json()["status"] == "review"
    assert "couldn't be opened" in broken.json()["read_error"]
    # A paper invoice without a scan: type it in.
    blank = parts.post(URL, {"supplier": "Maine Tire Co."}, format="json")
    assert blank.status_code == 201
    assert (blank.json()["status"], blank.json()["has_file"]) == ("review", False)
    assert parts.post(f"{URL}/{blank.json()['id']}/read-again").status_code == 400


@pytest.mark.django_db
def test_reading_job_is_safe_to_run_twice(client_for: Any, catalog: None, settings: Any) -> None:
    from apps.parts.tasks import read_parts_invoice

    settings.INVOICE_READ_INLINE = False
    inv = uploaded(client_for("parts"))
    assert inv["status"] == "reading"
    read_parts_invoice(invoice_id=inv["id"])
    read_parts_invoice(invoice_id=inv["id"])
    invoice = Invoice.objects.get(pk=inv["id"])
    assert invoice.status == "review"
    assert invoice.lines.count() == 5


@pytest.mark.django_db
def test_same_invoice_twice_is_flagged(client_for: Any, catalog: None) -> None:
    parts = client_for("parts")
    first = uploaded(parts)
    second = uploaded(parts)
    assert second["invoice_number"] == ""  # not claimed
    assert "already entered" in second["read_error"]
    res = parts.patch(f"{URL}/{second['id']}", {"invoice_number": "hma-558812"}, format="json")
    assert res.status_code == 400
    assert "already entered" in res.json()["fields"]["invoice_number"][0]
    # Once the first is cancelled, the number is free again.
    parts.post(f"{URL}/{first['id']}/cancel", {"reason": "Entered twice"}, format="json")
    res = parts.patch(f"{URL}/{second['id']}", {"invoice_number": "HMA-558812"}, format="json")
    assert res.status_code == 200, res.json()


# --- Checking and receiving ----------------------------------------------------------------


@pytest.mark.django_db
def test_check_receive_partly_and_backorders(client_for: Any, catalog: None) -> None:
    parts = client_for("parts")
    inv = uploaded(parts)
    lines = lines_by_number(inv)
    belt = Part.objects.create(part_number="99Z9-12345", description="Seat belt, orange")
    # Checking: pick our part for the unknown line, fix a quantity.
    edited = [
        {**line, "part": str(belt.pk) if line["part_number"] == "99Z9-12345" else line["part"]}
        for line in inv["lines"]
    ]
    res = parts.patch(f"{URL}/{inv['id']}", {"lines": edited}, format="json")
    assert res.status_code == 200, res.json()
    checked = lines_by_number(res.json())
    assert checked["99Z9-12345"]["part"] == str(belt.pk)
    assert checked["99Z9-12345"]["check_reason"] == ""  # a person looked at it

    oil = part("31N4-01050")
    stock.count(oil, Decimal("8"))
    receipt = parts.post(
        f"{URL}/{inv['id']}/receive",
        {
            "lines": [
                {"line": lines["31N4-01050"]["id"], "quantity": "12"},
                {"line": lines["31N4-01060"]["id"], "quantity": "4"},  # 2 missing from the box
            ]
        },
        format="json",
    )
    assert receipt.status_code == 200, receipt.json()
    body = receipt.json()
    assert body["status"] == "partial"
    after = lines_by_number(body)
    assert (after["31N4-01060"]["received"], after["31N4-01060"]["outstanding"]) == (
        "4.00",
        "4.00",  # 6 shipped + 2 backordered - 4 received
    )
    assert stock.on_hand(oil) == Decimal("20")
    movement = StockMovement.objects.get(part=oil, kind="receive")
    assert movement.reference == "Hyundai parts HMA-558812"
    assert movement.unit_cost == Decimal("9.80")
    assert movement.invoice_line_id is not None

    # Too many, or a line with no part, is refused; nothing is received.
    too_many = parts.post(
        f"{URL}/{inv['id']}/receive",
        {"lines": [{"line": lines["31N4-01060"]["id"], "quantity": "5"}]},
        format="json",
    )
    assert too_many.status_code == 400
    assert "Only 4 of 31N4-01060 still to come" in too_many.json()["fields"]["lines"][0]
    # Lines are fixed once something is received.
    assert parts.patch(f"{URL}/{inv['id']}", {"lines": edited}, format="json").status_code == 400
    assert (
        parts.post(f"{URL}/{inv['id']}/cancel", {"reason": "x"}, format="json").status_code == 400
    )

    waiting = parts.get(f"{URL}/backorders").json()
    numbers = {row["part_number"]: row for row in waiting}
    assert numbers["31N4-01060"]["outstanding"] == "4.00"
    assert numbers["31N4-01060"]["invoice_label"] == "Hyundai parts HMA-558812"
    assert "31N4-01050" not in numbers  # all in
    assert parts.get(f"{URL}/counts").json()["partial"] == 1

    # The rest arrives (with a cost update), and the supplier cancels what's left.
    rest = [
        {"line": lines[n]["id"], "quantity": q}
        for n, q in (
            ("31N4-01060", "2"),
            ("31N4-40020", "4"),
            ("XKBH-00117", "2"),
            ("99Z9-12345", "1"),
        )
    ]
    res = parts.post(
        f"{URL}/{inv['id']}/receive", {"lines": rest, "update_costs": True}, format="json"
    )
    assert res.status_code == 200, res.json()
    assert part("31N4-01060").cost == Decimal("14.25")
    assert res.json()["status"] == "partial"  # 2 still backordered
    close = parts.post(f"{LINES}/{lines['31N4-01060']['id']}/close", {"reason": ""}, format="json")
    assert close.status_code == 400
    close = parts.post(
        f"{LINES}/{lines['31N4-01060']['id']}/close",
        {"reason": "Supplier cancelled the backorder"},
        format="json",
    )
    assert close.status_code == 200, close.json()
    assert close.json()["outstanding"] == "0.00"
    assert parts.get(f"{URL}/{inv['id']}").json()["status"] == "received"
    assert parts.get(f"{URL}/backorders").json() == []
    reopened = parts.post(f"{LINES}/{lines['31N4-01060']['id']}/reopen")
    assert reopened.status_code == 200
    assert parts.get(f"{URL}/{inv['id']}").json()["status"] == "partial"
    assert stock.check_drift().ok


@pytest.mark.django_db
def test_reversing_a_receipt_reopens_the_line(client_for: Any, catalog: None) -> None:
    parts = client_for("parts")
    inv = uploaded(parts)
    rows = [
        {"line": line["id"], "quantity": line["quantity_shipped"]}
        for line in inv["lines"]
        if line["part"]
    ]
    one = Invoice.objects.get(pk=inv["id"]).lines.get(part_number="99Z9-12345")
    one.not_stocked = True  # treat the unknown line as a fee, for this test
    one.save()
    res = parts.post(f"{URL}/{inv['id']}/receive", {"lines": rows}, format="json")
    assert res.json()["status"] == "partial", res.json()  # backorder of 2 still to come
    brake = StockMovement.objects.get(part__part_number="31N4-40020", kind="receive")
    reversal = parts.post(f"/api/v1/stock-movements/{brake.pk}/reverse", {}, format="json")
    assert reversal.status_code == 201, reversal.json()
    line = lines_by_number(parts.get(f"{URL}/{inv['id']}").json())["31N4-40020"]
    assert (line["received"], line["outstanding"]) == ("0.00", "4.00")


@pytest.mark.django_db
def test_receiving_needs_supplier_and_number(client_for: Any, catalog: None) -> None:
    parts = client_for("parts")
    blank = parts.post(URL, {}, format="json").json()
    res = parts.patch(
        f"{URL}/{blank['id']}",
        {
            "lines": [
                {
                    "part": str(part("31N4-01050").pk),
                    "part_number": "31N4-01050",
                    "description": "Oil filter",
                    "quantity_shipped": "2",
                    "unit_cost": "9.80",
                },
                {"description": "Freight", "not_stocked": True, "unit_cost": "12.00"},
            ]
        },
        format="json",
    )
    assert res.status_code == 200, res.json()
    line = res.json()["lines"][0]
    receive = {"lines": [{"line": line["id"], "quantity": "2"}]}
    refused = parts.post(f"{URL}/{blank['id']}/receive", receive, format="json")
    assert refused.status_code == 400
    assert "supplier and invoice number" in refused.json()["fields"]["invoice_number"][0]
    parts.patch(
        f"{URL}/{blank['id']}",
        {"supplier": "Hyundai parts", "invoice_number": "T-1"},
        format="json",
    )
    assert parts.post(f"{URL}/{blank['id']}/receive", receive, format="json").status_code == 200
    fee = res.json()["lines"][1]
    fee_receipt = {"lines": [{"line": fee["id"], "quantity": "1"}]}
    assert parts.post(f"{URL}/{blank['id']}/receive", fee_receipt, format="json").status_code == 400
    # A stock line needs a quantity.
    empty = parts.patch(
        f"{URL}/{blank['id']}",
        {"lines": [{"description": "x", "quantity_shipped": "0"}]},
        format="json",
    )
    assert empty.status_code == 400


@pytest.mark.django_db
def test_cancel(client_for: Any, catalog: None) -> None:
    parts = client_for("parts")
    inv = uploaded(parts)
    assert parts.post(f"{URL}/{inv['id']}/cancel", {"reason": ""}, format="json").status_code == 400
    done = parts.post(f"{URL}/{inv['id']}/cancel", {"reason": "Wrong store"}, format="json")
    assert done.json()["status"] == "cancelled"
    assert parts.patch(f"{URL}/{inv['id']}", {"note": "x"}, format="json").status_code == 400
    assert parts.get(f"{URL}?status=cancelled").json()["count"] == 1
    assert parts.get(URL).json()["count"] == 0  # open ones by default


@pytest.mark.django_db
def test_database_refuses_bad_invoices(catalog: None) -> None:
    Invoice.objects.create(supplier="Hyundai parts", invoice_number="A-1")
    with pytest.raises(DatabaseError), transaction.atomic():
        Invoice.objects.create(supplier="HYUNDAI PARTS", invoice_number="a-1")
    inv = Invoice.objects.create(supplier="Other", invoice_number="A-1")
    with pytest.raises(DatabaseError), transaction.atomic():
        InvoiceLine.objects.create(invoice=inv, description="nothing")  # no quantity
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cur:
        cur.execute("DELETE FROM parts_invoice WHERE id = %s", [inv.pk])  # soft delete only
    line = InvoiceLine.objects.create(invoice=inv, description="x", quantity_shipped=Decimal("1"))
    unit = Unit.objects.create(make="Hyundai", model="35LN-9A", serial_number="INV-T-1")
    wo = WorkOrder.objects.create(unit=unit, complaint="x")
    oil = part("31N4-01050")
    stock.count(oil, Decimal("5"))
    with pytest.raises(DatabaseError), transaction.atomic():
        StockMovement.objects.create(
            part=oil,
            kind="issue",
            quantity=Decimal("-1"),
            work_order=wo,
            invoice_line=line,
            balance_after=Decimal("4"),
        )


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("role", "reads", "writes"),
    [
        ("admin", True, True),
        ("parts", True, True),
        ("sales", True, False),
        ("service", False, False),
        ("read_only", False, False),
    ],
)
def test_invoice_role_matrix(
    client_for: Any, catalog: None, role: str, reads: bool, writes: bool
) -> None:
    inv = uploaded(client_for("parts"))
    line = inv["lines"][0]
    client = client_for(role)
    read = 200 if reads else 403
    assert client.get(URL).status_code == read
    assert client.get(f"{URL}/{inv['id']}").status_code == read
    assert client.get(f"{URL}/{inv['id']}/file").status_code == read
    assert client.get(f"{URL}/backorders").status_code == read
    write = 403 if not writes else None
    created = upload(client, sample_invoice.pdf(number=f"R-{role}"))
    assert created.status_code == (write or 201)
    patched = client.patch(f"{URL}/{inv['id']}", {"note": role}, format="json")
    assert patched.status_code == (write or 200)
    received = client.post(
        f"{URL}/{inv['id']}/receive",
        {"lines": [{"line": line["id"], "quantity": "1"}]},
        format="json",
    )
    assert received.status_code == (write or 200)
    closed = client.post(f"{LINES}/{line['id']}/close", {"reason": "test"}, format="json")
    assert closed.status_code == (write or 200)


@pytest.mark.django_db
def test_flag_off(client_for: Any) -> None:
    flag = FeatureFlag.objects.get(key="parts-invoices")
    flag.enabled = False
    flag.save()
    assert client_for("admin").get(URL).status_code == 404
    assert client_for("admin").get("/api/v1/parts").status_code == 200


@pytest.mark.django_db
def test_match_part_ignores_ambiguous_numbers(catalog: None) -> None:
    assert invoices.match_part("31n4 01050") == part("31N4-01050")
    assert invoices.match_part("p550084") == part("31N4-01050")  # a cross reference
    Part.objects.create(manufacturer="Clark", part_number="31N4-01050", description="Clark filter")
    assert invoices.match_part("31N4-01050") is None  # two makers: a person picks
    assert invoices.match_part("x") is None


@pytest.mark.django_db
def test_demo_invoices_load_once() -> None:
    from apps.parts.demo import load_demo_invoices, load_demo_parts, load_demo_stock

    load_demo_parts()
    load_demo_stock()
    load_demo_invoices()
    load_demo_invoices()
    assert Invoice.objects.count() == 2
    assert set(Invoice.objects.values_list("status", flat=True)) == {"review", "partial"}
    waiting = invoices.backorders()
    assert [(line.part_number, invoices.outstanding(line)) for line in waiting] == [
        ("31N4-02100", Decimal("2"))
    ]
    assert stock.check_drift().ok
