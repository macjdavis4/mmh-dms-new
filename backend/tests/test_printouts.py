"""Printouts. PDF compression is off in tests, so the text is in the bytes."""

import io
from decimal import Decimal
from typing import Any

import pytest
from django.core.files.base import ContentFile
from PIL import Image

from apps.customers.models import Contact, Customer
from apps.service.models import MaintenancePlan, WorkOrder
from apps.service.services import add_labor, change_status, save_work_order
from apps.units.models import (
    HourMeterReading,
    OwnershipRecord,
    Unit,
    UnitAttachment,
    UnitComponent,
    UnitFork,
)
from apps.units.services import add_file


@pytest.fixture
def unit(db: Any) -> Unit:
    unit = Unit.objects.create(
        make="Hyundai",
        model="70D-9",
        serial_number="HHKHFV30K00057",
        year=2019,
        fuel_type="diesel",
        capacity_lbs=15500,
        mast_make="Hyundai",
        mast_type="TF470",
        mast_size="69MN-T4715",
        tire_drive_size="8.15-15",
        battery_make="",
        special_equipment="Blue spot light",
        notes="INTERNAL: customer slow to pay",
        cost=Decimal("21000"),
        asking_price=Decimal("38900"),
    )
    customer = Customer.objects.create(name="Katahdin Lumber", phone="207-555-0144")
    Contact.objects.create(
        customer=customer, first_name="Mike", last_name="Pelletier", is_primary=True
    )
    OwnershipRecord.objects.create(unit=unit, owner_kind="customer", customer=customer)
    HourMeterReading.objects.create(unit=unit, hours=Decimal("9120"), source="card")
    UnitComponent.objects.create(
        unit=unit, kind="engine", make="Hyundai", model="D4DB", serial_number="D4DB-1"
    )
    UnitFork.objects.create(unit=unit, dimensions="1.75 x 4 x 48 STD", quantity=2)
    UnitAttachment.objects.create(
        unit=unit,
        manufacturer="Cascade",
        type="SS/FP",
        model="65K-FPS-8169-C",
        hose_reel=True,
        side="LH",
    )
    return unit


def pdf(res: Any) -> bytes:
    assert res.status_code == 200, res.content[:300]
    assert res["Content-Type"] == "application/pdf"
    body = b"".join(res.streaming_content) if getattr(res, "streaming", False) else res.content
    assert body.startswith(b"%PDF")
    return body


@pytest.mark.django_db
def test_work_order_printout(client_for: Any, make_user: Any, unit: Unit) -> None:
    mechanic = make_user("service")
    mechanic.first_name, mechanic.last_name = "Sam", "Wrench"
    mechanic.save()
    plan = MaintenancePlan.objects.create(unit=unit, name="250-hour service", interval_days=90)
    wo = WorkOrder(
        unit=unit,
        complaint="Mast chatters",
        cause="Worn rollers",
        customer_po="PO-881",
        maintenance_plan=plan,
    )
    save_work_order(wo, hours=Decimal("9150"), hours_given=True)
    add_labor(
        wo,
        mechanic=mechanic,
        work_date=wo.opened_on,
        hours=Decimal("2.5"),
        description="Replaced rollers",
    )

    res = client_for("parts").get(f"/api/v1/work-orders/{wo.pk}/pdf")
    body = pdf(res)
    assert res["Content-Disposition"] == f'inline; filename="{wo.number}.pdf"'
    assert res["Cache-Control"] == "private, no-store"
    for text in [
        wo.number.encode(),
        b"Katahdin Lumber",
        b"Mike Pelletier",
        b"PO-881",
        b"HHKHFV30K00057",
        b"9,150",
        b"Mast chatters",
        b"Worn rollers",
        b"Sam Wrench",
        b"Replaced rollers",
        b"250-hour service",
        b"Maine Material Handling",
        b"AUTHORIZED HYUNDAI DEALER",
    ]:
        assert text in body, text

    wo.correction = "Replaced rollers"
    wo.save()
    change_status(wo, "completed")
    assert b"Completed" in pdf(client_for("read_only").get(f"/api/v1/work-orders/{wo.pk}/pdf"))


@pytest.mark.django_db
def test_spec_sheet(client_for: Any, unit: Unit) -> None:
    buf = io.BytesIO()
    Image.new("RGB", (800, 600), (230, 120, 30)).save(buf, "JPEG")
    add_file(unit, ContentFile(buf.getvalue(), name="front.jpg"), kind="photo")

    body = pdf(client_for("service").get(f"/api/v1/units/{unit.pk}/spec-sheet"))
    for text in [
        b"2019 Hyundai 70D-9",
        b"HHKHFV30K00057",
        b"15,500 lb",
        b"Diesel",
        b"69MN-T4715",
        b"D4DB-1",
        b"1.75 x 4 x 48 STD",
        b"Cascade",
        b"hose reel",
        b"Blue spot light",
        b"Katahdin Lumber",
    ]:
        assert text in body, text
    assert b"/Subtype /Image" in body  # the photo
    assert b"38,900" not in body  # no price unless asked
    assert b"21,000" not in body and b"INTERNAL" not in body  # never cost or internal notes

    priced = pdf(client_for("sales").get(f"/api/v1/units/{unit.pk}/spec-sheet", {"price": "1"}))
    assert b"38,900" in priced and b"21,000" not in priced


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("role", "can_price"),
    [("admin", True), ("sales", True), ("service", False), ("parts", False), ("read_only", False)],
)
def test_who_can_print(client_for: Any, unit: Unit, role: str, can_price: bool) -> None:
    wo = WorkOrder(unit=unit, complaint="x")
    save_work_order(wo)
    client = client_for(role)
    assert client.get(f"/api/v1/work-orders/{wo.pk}/pdf").status_code == 200
    assert client.get(f"/api/v1/units/{unit.pk}/spec-sheet").status_code == 200
    priced = client.get(f"/api/v1/units/{unit.pk}/spec-sheet", {"price": "1"})
    assert priced.status_code == (200 if can_price else 403)


@pytest.mark.django_db
def test_blank_unit_still_prints(client_for: Any) -> None:
    bare = Unit.objects.create(stock_number="MMH-9999")
    body = pdf(client_for("admin").get(f"/api/v1/units/{bare.pk}/spec-sheet"))
    assert b"No photo yet" in body
    res = client_for("admin").get(f"/api/v1/units/{bare.pk}/spec-sheet")
    assert res["Content-Disposition"] == 'inline; filename="unit-spec-sheet.pdf"'


def test_safe_filename() -> None:
    from apps.core.pdf import safe_filename

    assert (
        safe_filename("Hyundai-35LN 9A-AB/12-spec-sheet.pdf")
        == "Hyundai-35LN-9A-AB-12-spec-sheet.pdf"
    )
