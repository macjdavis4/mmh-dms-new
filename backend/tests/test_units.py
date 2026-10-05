import io
from decimal import Decimal
from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError, transaction
from PIL import Image
from rest_framework.test import APIClient

from apps.core.models import FeatureFlag
from apps.customers.models import Customer
from apps.units.models import (
    HourMeterReading,
    OwnershipRecord,
    Unit,
    UnitComponent,
    UnitFile,
    normalize_serial,
    parse_fork,
)

URL = "/api/v1/units"

CARD = {
    "make": "Hyundai",
    "model": "35LN-9A",
    "serial_number": "HHKHHF04-0123",
    "year": 2019,
    "condition": "used",
    "fuel_type": "lpg",
    "capacity_lbs": 7000,
    "card_date": "2024-03-12",
    "card_customer_name": "Penobscot Paper",
    "mechanic": "Sam W.",
    "work_order_number": "WO-4471",
    "mast_make": "Hyundai",
    "mast_type": "TF470",
    "mast_size": "69MN-T4715",
    "mast_lift_height_in": 189,
    "lift_cylinder_number": "LC-2231",
    "carriage": "Class II, 40 in",
    "backrest_height": "48 in",
    "backrest_width": "40 in",
    "tilt_forward_deg": "6.0",
    "tilt_back_deg": "10.0",
    "tilt_reference": "TR-9",
    "tire_type": "solid",
    "tire_drive_size": "8.15-15",
    "tire_steer_size": "6.50-10",
    "tire_notes": "7.00 rim",
    "special_equipment": "LED blue spot",
    "field_modifications": "Added fire extinguisher bracket",
    "notes": "Card is water stained",
    "components": [
        {"kind": "engine", "make": "Hyundai", "model": "L4KB", "serial_number": "L4KB-99812"},
        {"kind": "control_valve", "make": "Hyundai", "model": "CV-3", "spools": "3SP"},
        {"kind": "transmission", "make": "Hyundai", "model": "T-1"},
    ],
    "forks": [{"dimensions": "1.75 x 4 x 48 STD", "quantity": 2}],
    "attachments": [
        {
            "manufacturer": "Cascade",
            "type": "SS/FP",
            "model": "65K-FPS-8169-C",
            "serial_number": "CS-1",
            "hose_reel": True,
            "side": "LH",
        }
    ],
}


def create(client: APIClient, **overrides: Any) -> dict[str, Any]:
    res = client.post(URL, {**CARD, **overrides}, format="json")
    assert res.status_code == 201, res.json()
    return res.json()


def png_bytes(size: tuple[int, int] = (1600, 1200)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, (11, 42, 74)).save(buf, "PNG")
    return buf.getvalue()


# --- Parsing helpers --------------------------------------------------------------------------


def test_serials_compare_without_case_spaces_or_dashes() -> None:
    assert normalize_serial(" ab-123 4/x ") == "AB1234X"
    assert normalize_serial("") == ""


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1.75 x 4 x 48 STD", (Decimal("1.75"), Decimal("4"), Decimal("48"))),
        ("2X5X60", (Decimal("2"), Decimal("5"), Decimal("60"))),
        ("1.5 × 4 × 42", (Decimal("1.5"), Decimal("4"), Decimal("42"))),
        ("48 inch forks", None),
        ("", None),
    ],
)
def test_fork_dimensions_parse_only_when_clean(raw: str, expected: Any) -> None:
    assert parse_fork(raw) == expected


# --- Create / update ------------------------------------------------------------------------------


@pytest.mark.django_db
def test_create_unit_with_every_card_section(client_for: Any) -> None:
    client = client_for("sales")
    customer = Customer.objects.create(name="Penobscot Paper Co.")
    unit = create(
        client,
        initial_owner_kind="customer",
        initial_owner_customer=str(customer.pk),
        initial_hours="4512.5",
        battery_make="EnerSys",
        battery_volts=36,
        battery_amp_hours=750,
        charger_make="Hobart",
    )
    detail = client.get(f"{URL}/{unit['id']}").json()
    assert detail["mast_size"] == "69MN-T4715"
    assert detail["tire_drive_size"] == "8.15-15"
    assert detail["battery_volts"] == 36
    assert [c["kind"] for c in detail["components"]] == ["engine", "control_valve", "transmission"]
    assert detail["components"][1]["spools"] == "3SP"
    assert detail["forks"][0]["length_in"] == "48.00"
    assert detail["attachments"][0]["model"] == "65K-FPS-8169-C"
    assert detail["owner_name"] == "Penobscot Paper Co."
    assert detail["owner_kind"] == "customer"
    assert detail["current_hours"] == "4512.5"
    reading = HourMeterReading.objects.get(unit_id=unit["id"])
    assert reading.source == "card"
    assert str(reading.reading_date) == "2024-03-12"


@pytest.mark.django_db
def test_new_units_default_to_dealer_stock(client_for: Any) -> None:
    unit = create(
        client_for("admin"), serial_number="NEW-1", stock_status="available", condition="new"
    )
    record = OwnershipRecord.objects.get(unit_id=unit["id"])
    assert record.owner_kind == "dealer"
    assert record.customer is None


@pytest.mark.django_db
def test_update_syncs_child_rows(client_for: Any) -> None:
    client = client_for("service")
    unit = create(client)
    components = unit["components"]
    engine = next(c for c in components if c["kind"] == "engine")
    res = client.patch(
        f"{URL}/{unit['id']}",
        {
            # keep the engine (edit it), drop the transmission and valve, add a pump
            "components": [
                {**engine, "serial_number": "L4KB-NEW"},
                {"kind": "hydraulic_pump", "make": "Kayaba"},
            ],
            "forks": [],
        },
        format="json",
    )
    assert res.status_code == 200, res.json()
    kinds = {c["kind"]: c for c in res.json()["components"]}
    assert set(kinds) == {"engine", "hydraulic_pump"}
    assert kinds["engine"]["id"] == engine["id"]
    assert kinds["engine"]["serial_number"] == "L4KB-NEW"
    assert res.json()["forks"] == []
    # Removed rows are soft-deleted, not gone.
    assert (
        UnitComponent.all_objects.filter(unit_id=unit["id"], deleted_at__isnull=False).count() == 2
    )


@pytest.mark.django_db
def test_replacing_a_component_of_the_same_kind(client_for: Any) -> None:
    client = client_for("service")
    unit = create(client)
    res = client.patch(
        f"{URL}/{unit['id']}",
        {"components": [{"kind": "engine", "make": "Nissan", "model": "K25"}]},
        format="json",
    )
    assert res.status_code == 200, res.json()
    assert res.json()["components"][0]["model"] == "K25"


@pytest.mark.django_db
def test_component_validation(client_for: Any) -> None:
    client = client_for("service")
    dup = client.post(
        URL, {**CARD, "components": [{"kind": "engine"}, {"kind": "engine"}]}, format="json"
    )
    assert dup.status_code == 400
    spools = client.post(
        URL,
        {**CARD, "serial_number": "X2", "components": [{"kind": "engine", "spools": "2SP"}]},
        format="json",
    )
    assert spools.status_code == 400
    nothing = client.post(URL, {"make": "Hyundai"}, format="json")
    assert nothing.status_code == 400
    assert "serial_number" in nothing.json()["fields"]


# --- Duplicate serials -------------------------------------------------------------------------------


@pytest.mark.django_db
def test_duplicate_serials_are_refused_and_warned(client_for: Any) -> None:
    client = client_for("sales")
    first = create(client, serial_number="AB-1234")
    check = client.get(URL + "/serial-check?serial=ab 1234").json()
    assert check["duplicates"][0]["id"] == first["id"]
    assert (
        client.get(URL + f"/serial-check?serial=ab1234&exclude={first['id']}").json()["duplicates"]
        == []
    )

    res = client.post(URL, {**CARD, "serial_number": "ab1234"}, format="json")
    assert res.status_code == 400
    assert "already on" in res.json()["fields"]["serial_number"][0]

    # The database refuses it too, even if the API check is bypassed.
    with pytest.raises(DatabaseError), transaction.atomic():
        Unit.objects.create(model="Other", serial_number="A B 1 2 3 4")


@pytest.mark.django_db
def test_removed_units_still_block_their_serial(client_for: Any) -> None:
    admin = client_for("admin")
    unit = create(admin, serial_number="GONE-1")
    assert admin.delete(f"{URL}/{unit['id']}").status_code == 204
    res = admin.post(URL, {**CARD, "serial_number": "gone1"}, format="json")
    assert res.status_code == 400
    assert "restore it instead" in res.json()["fields"]["serial_number"][0]
    assert admin.post(f"{URL}/{unit['id']}/restore").status_code == 200


# --- Pricing visibility -----------------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("role", "sees"),
    [("admin", True), ("sales", True), ("service", False), ("parts", False), ("read_only", False)],
)
def test_prices_visible_only_to_admin_and_sales(client_for: Any, role: str, sees: bool) -> None:
    unit = create(
        client_for("admin"),
        stock_status="available",
        cost="18500.00",
        asking_price="24900.00",
        sale_price=None,
    )
    client = client_for(role)
    detail = client.get(f"{URL}/{unit['id']}").json()
    row = client.get(URL).json()["results"][0]
    for field in ("cost", "asking_price", "sale_price"):
        assert (field in detail) is sees
    assert ("asking_price" in row) is sees
    # Price filters and sorting are ignored for roles that can't see prices.
    filtered = client.get(URL + "?price_max=1000").json()["count"]
    assert filtered == (0 if sees else 1)
    history = client.get(f"{URL}/{unit['id']}/history").json()
    created = next(h for h in history if h["action"] == "create")
    assert ("cost" in created["after"]) is sees


@pytest.mark.django_db
def test_non_price_roles_cannot_set_prices_or_stock_status(client_for: Any) -> None:
    unit = create(client_for("admin"), stock_status="in_prep", cost="1000")
    res = client_for("service").patch(
        f"{URL}/{unit['id']}",
        {"cost": "1", "asking_price": "2", "stock_status": "sold", "notes": "Prepped"},
        format="json",
    )
    assert res.status_code == 200
    obj = Unit.objects.get(pk=unit["id"])
    assert obj.cost == Decimal("1000.00")
    assert obj.asking_price is None
    assert obj.stock_status == "in_prep"
    assert obj.notes == "Prepped"


@pytest.mark.django_db
def test_negative_money_refused(client_for: Any) -> None:
    res = client_for("admin").post(URL, {**CARD, "cost": "-5"}, format="json")
    assert res.status_code == 400
    with pytest.raises(DatabaseError), transaction.atomic():
        Unit.objects.create(model="X", cost=Decimal("-1"))


# --- Inventory list --------------------------------------------------------------------------------------------


@pytest.mark.django_db
def test_inventory_filters(client_for: Any) -> None:
    admin = client_for("admin")
    create(
        admin, serial_number="S1", stock_status="available", condition="used", asking_price="20000"
    )
    create(
        admin,
        serial_number="S2",
        make="Doosan",
        model="G25N-7",
        stock_status="in_prep",
        condition="new",
        fuel_type="gasoline",
        capacity_lbs=5000,
        mast_lift_height_in=130,
        asking_price="31000",
    )
    create(admin, serial_number="S3", stock_status="sold")
    create(admin, serial_number="S4")  # a customer/service unit, not stock

    def count(query: str) -> int:
        return admin.get(URL + query).json()["count"]

    assert count("") == 2  # default scope: in stock (available, on hold, in prep)
    assert count("?scope=all") == 4
    assert count("?scope=all&status=sold") == 1
    assert count("?condition=new") == 1
    assert count("?make=Doosan") == 1
    assert count("?fuel_type=lpg") == 1
    assert count("?capacity_min=6000") == 1
    assert count("?lift_max=150") == 1
    assert count("?price_min=25000") == 1
    assert count("?q=s2") == 1
    assert count("?q=G25N") == 1
    first = admin.get(URL + "?ordering=-price").json()["results"][0]
    assert first["serial_number"] == "S2"


@pytest.mark.django_db
def test_facets(client_for: Any) -> None:
    admin = client_for("admin")
    create(admin, serial_number="F1")
    create(admin, serial_number="F2", make="Doosan", model="G25N-7")
    facets = client_for("parts").get(URL + "/facets").json()
    assert facets["makes"] == ["Doosan", "Hyundai"]
    assert facets["models"]["Doosan"] == ["G25N-7"]
    assert facets["can_see_pricing"] is False


@pytest.mark.django_db
def test_global_search_finds_any_serial(client_for: Any) -> None:
    create(client_for("admin"), serial_number="HHKHHF04-0123")
    client = client_for("parts")
    by_unit = client.get("/api/v1/search?q=hhkhhf040123").json()["groups"]["unit"]
    assert by_unit[0]["title"] == "Hyundai 35LN-9A"
    by_engine = client.get("/api/v1/search?q=L4KB-99812").json()["groups"]["unit"]
    assert len(by_engine) == 1


@pytest.mark.django_db
def test_multi_word_search_matches_make_and_model(client_for: Any) -> None:
    admin = client_for("admin")
    create(admin, serial_number="MW1", stock_status="available")
    create(admin, serial_number="MW2", make="Doosan", model="G25N-7", stock_status="available")
    found = admin.get("/api/v1/search?q=hyundai 35").json()["groups"]["unit"]
    assert [u["title"] for u in found] == ["Hyundai 35LN-9A"]
    listed = admin.get(URL, {"q": "doosan g25"}).json()["results"]
    assert [u["serial_number"] for u in listed] == ["MW2"]
    assert admin.get(URL, {"q": "doosan 35"}).json()["count"] == 0


# --- Ownership and hours --------------------------------------------------------------------------------------------


@pytest.mark.django_db
def test_transfer_ownership(client_for: Any) -> None:
    sales = client_for("sales")
    unit = create(sales, stock_status="available")
    buyer = Customer.objects.create(name="Katahdin Lumber")
    res = sales.post(
        f"{URL}/{unit['id']}/transfer",
        {"owner_kind": "customer", "customer": str(buyer.pk), "start_date": "2025-01-15"},
        format="json",
    )
    assert res.status_code == 201, res.json()
    history = sales.get(f"{URL}/{unit['id']}/ownership").json()
    assert [h["owner_label"] for h in history] == [
        "Katahdin Lumber",
        "Maine Material Handling stock",
    ]
    assert history[1]["end_date"] == "2025-01-15"
    assert sales.get(f"{URL}/{unit['id']}").json()["owner_name"] == "Katahdin Lumber"

    same = sales.post(
        f"{URL}/{unit['id']}/transfer",
        {"owner_kind": "customer", "customer": str(buyer.pk), "start_date": "2025-02-01"},
        format="json",
    )
    assert same.status_code == 400
    backwards = sales.post(
        f"{URL}/{unit['id']}/transfer",
        {"owner_kind": "dealer", "start_date": "2020-01-01"},
        format="json",
    )
    assert backwards.status_code == 400
    assert "start_date" in backwards.json()["fields"]
    assert (
        client_for("service")
        .post(
            f"{URL}/{unit['id']}/transfer",
            {"owner_kind": "dealer", "start_date": "2026-01-01"},
            format="json",
        )
        .status_code
        == 403
    )

    # One open record per unit, enforced by the database.
    with pytest.raises(DatabaseError), transaction.atomic():
        OwnershipRecord.objects.create(unit_id=unit["id"], owner_kind="dealer")


@pytest.mark.django_db
def test_hour_readings(client_for: Any) -> None:
    service = client_for("service")
    unit = create(service, initial_hours="5000")
    up = service.post(
        f"{URL}/{unit['id']}/hours",
        {"hours": "5120.5", "reading_date": "2025-06-01"},
        format="json",
    )
    assert up.status_code == 201
    assert up.json()["warning"] is None
    down = service.post(
        f"{URL}/{unit['id']}/hours", {"hours": "12", "reading_date": "2025-07-01"}, format="json"
    )
    assert "lower than" in down.json()["warning"]
    assert service.get(f"{URL}/{unit['id']}").json()["current_hours"] == "12.0"
    assert (
        service.post(
            f"{URL}/{unit['id']}/hours",
            {"hours": "-1", "reading_date": "2025-07-02"},
            format="json",
        ).status_code
        == 400
    )
    readings = service.get(f"{URL}/{unit['id']}/hours").json()
    assert [r["hours"] for r in readings] == ["12.0", "5120.5", "5000.0"]
    # Only admins remove a reading.
    rid = readings[0]["id"]
    assert service.delete(f"/api/v1/hour-readings/{rid}").status_code == 403
    assert client_for("admin").delete(f"/api/v1/hour-readings/{rid}").status_code == 204
    assert service.get(f"{URL}/{unit['id']}").json()["current_hours"] == "5120.5"


# --- Files --------------------------------------------------------------------------------------------------------------


@pytest.mark.django_db
def test_photo_upload_thumbnail_and_streaming(client_for: Any) -> None:
    service = client_for("service")
    unit = create(service)
    upload = SimpleUploadedFile("lift.png", png_bytes(), content_type="image/png")
    res = service.post(
        f"{URL}/{unit['id']}/files", {"file": upload, "kind": "photo", "caption": "Left side"}
    )
    assert res.status_code == 201, res.json()
    photo = res.json()
    assert photo["is_primary"] is True  # first photo becomes the main one
    assert (photo["width"], photo["height"]) == (1600, 1200)
    assert photo["thumbnail_url"].endswith("?size=thumb")

    thumb = service.get(photo["thumbnail_url"])
    assert thumb.status_code == 200
    assert thumb["Content-Type"] == "image/webp"
    img = Image.open(io.BytesIO(b"".join(thumb.streaming_content)))
    assert max(img.size) == 640
    full = client_for("read_only").get(photo["url"])
    assert full["Content-Type"] == "image/png"
    assert full["Cache-Control"] == "private, max-age=3600"

    second = service.post(
        f"{URL}/{unit['id']}/files",
        {"file": SimpleUploadedFile("b.png", png_bytes((800, 600))), "kind": "photo"},
    ).json()
    assert second["is_primary"] is False
    assert (
        service.patch(
            f"/api/v1/unit-files/{second['id']}", {"is_primary": True}, format="json"
        ).status_code
        == 200
    )
    assert UnitFile.objects.get(pk=photo["id"]).is_primary is False
    assert service.get(f"{URL}/{unit['id']}").json()["primary_photo_id"] == second["id"]


@pytest.mark.django_db
def test_scanned_card_pdf_and_bad_files(client_for: Any) -> None:
    service = client_for("service")
    unit = create(service)
    pdf = SimpleUploadedFile(
        "card.pdf", b"%PDF-1.4\n%fake but signed\n", content_type="application/pdf"
    )
    res = service.post(f"{URL}/{unit['id']}/files", {"file": pdf, "kind": "scanned_card"})
    assert res.status_code == 201
    assert res.json()["content_type"] == "application/pdf"
    assert res.json()["thumbnail_url"] is None

    fake = SimpleUploadedFile("evil.jpg", b"<script>alert(1)</script>", content_type="image/jpeg")
    bad = service.post(f"{URL}/{unit['id']}/files", {"file": fake, "kind": "photo"})
    assert bad.status_code == 400
    pdf_as_photo = SimpleUploadedFile("x.pdf", b"%PDF-1.4\n")
    assert (
        service.post(
            f"{URL}/{unit['id']}/files", {"file": pdf_as_photo, "kind": "photo"}
        ).status_code
        == 400
    )
    assert service.post(f"{URL}/{unit['id']}/files", {"kind": "photo"}).status_code == 400
    parts = client_for("parts").post(
        f"{URL}/{unit['id']}/files",
        {"file": SimpleUploadedFile("a.png", png_bytes()), "kind": "photo"},
    )
    assert parts.status_code == 403


# --- Roles and flags -------------------------------------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("role", "can_edit", "can_remove"),
    [
        ("admin", True, True),
        ("sales", True, False),
        ("service", True, False),
        ("parts", False, False),
        ("read_only", False, False),
    ],
)
def test_unit_role_matrix(client_for: Any, role: str, can_edit: bool, can_remove: bool) -> None:
    unit = create(client_for("admin"), stock_status="available")
    client = client_for(role)
    assert client.get(URL).status_code == 200
    assert client.get(f"{URL}/{unit['id']}").status_code == 200
    assert client.get(f"{URL}/{unit['id']}/hours").status_code == 200
    created = client.post(URL, {**CARD, "serial_number": f"R-{role}"}, format="json")
    assert created.status_code == (201 if can_edit else 403)
    assert client.patch(f"{URL}/{unit['id']}", {"notes": role}, format="json").status_code == (
        200 if can_edit else 403
    )
    hours = client.post(
        f"{URL}/{unit['id']}/hours", {"hours": "1", "reading_date": "2026-01-01"}, format="json"
    )
    assert hours.status_code == (201 if can_edit else 403)
    assert client.delete(f"{URL}/{unit['id']}").status_code == (204 if can_remove else 403)


@pytest.mark.django_db
def test_anonymous_and_flag(client_for: Any, anon_client: APIClient) -> None:
    assert anon_client.get(URL).status_code == 401
    flag = FeatureFlag.objects.get(key="customers-units")
    flag.enabled = False
    flag.save()
    assert client_for("admin").get(URL).status_code == 404
