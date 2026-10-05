import csv
import io
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework.test import APIClient

from apps.core.models import FeatureFlag
from apps.customers.models import Customer
from apps.imports import formats, services
from apps.imports.columns import COLUMNS, SAMPLE_ROWS
from apps.imports.management.commands.write_import_docs import generated_files
from apps.imports.models import ApiKey, ImportBatch, ImportRow
from apps.imports.parsing import parse_row, read_csv
from apps.units.models import HourMeterReading, OwnershipRecord, Unit, UnitFile

BATCHES = "/api/v1/imports/batches"
API = "/api/v1/import/v1"


def make_csv(rows: list[dict[str, str]], *, delimiter: str = ",", encoding: str = "utf-8") -> bytes:
    columns = list(dict.fromkeys(k for row in rows for k in row))
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=columns, delimiter=delimiter)
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode(encoding)


def upload(client: APIClient, data: bytes, name: str = "cards.csv") -> Any:
    return client.post(BATCHES, {"file": SimpleUploadedFile(name, data, "text/csv")}, format="multipart")


def png(name: str = "card-0001.png") -> SimpleUploadedFile:
    buf = io.BytesIO()
    Image.new("RGB", (40, 30), (200, 200, 200)).save(buf, "PNG")
    return SimpleUploadedFile(name, buf.getvalue(), "image/png")


def rows_of(client: APIClient, batch_id: str, show: str = "") -> list[dict[str, Any]]:
    res = client.get(f"{BATCHES}/{batch_id}/rows", {"show": show} if show else {})
    assert res.status_code == 200, res.content
    return res.json()["results"]


ROW = {
    "customer_name": "Penobscot Paper Co.",
    "card_date": "3/12/2024",
    "mechanic": "Sam W.",
    "condition": "used",
    "hour_meter": "10,288",
    "unit_make": "Doosan",
    "unit_model": "G25N-7",
    "unit_serial": "FGA25-71234",
    "capacity_lbs": "5000 lbs",
    "engine_make": "Nissan",
    "engine_model": "K25",
    "control_valve_make": "Hydrocontrol",
    "control_valve_spools": "3sp",
    "forks": "1.75 x 4 x 48 STD; 1.75 x 4 x 48 STD",
    "attachment_1_mfg": "Cascade",
    "attachment_1_type": "SS/FP",
    "attachment_1_model": "65K-FPS-8169-C",
    "attachment_1_hose_reel": "yes",
    "attachment_1_side": "lh",
    "tire_drive_size": "8.15-15",
}


# --- Format files ----------------------------------------------------------------------------


def test_generated_docs_are_up_to_date() -> None:
    for path, content in generated_files().items():
        assert Path(path).exists(), f"run: python manage.py write_import_docs ({path} missing)"
        assert Path(path).read_bytes().decode("utf-8") == content, (
            f"{path} is out of date; run: python manage.py write_import_docs"
        )


def test_template_has_every_column_and_sample_parses() -> None:
    header = next(csv.reader(io.StringIO(formats.template_csv().lstrip("﻿"))))
    assert header == [c.name for c in COLUMNS]
    rows, messages = read_csv(formats.sample_csv().encode())
    assert messages == []
    assert len(rows) == len(SAMPLE_ROWS)
    for row in rows:
        assert parse_row(row, can_price=True).errors == []


def test_parse_keeps_unreadable_values_as_written() -> None:
    parsed = parse_row(
        {"unit_serial": "A1", "capacity_lbs": "5 ton", "card_date": "spring 2019", "year": "1999"},
        can_price=True,
    )
    assert "capacity_lbs" not in parsed.unit
    assert parsed.unit["year"] == 1999
    assert parsed.as_written == ["card_date as written: spring 2019", "capacity_lbs as written: 5 ton"]
    assert {w.column for w in parsed.warnings} == {"capacity_lbs", "card_date"}


@pytest.mark.parametrize(
    ("row", "column"),
    [
        ({"unit_model": "35LN-9A"}, "unit_serial"),
        ({"unit_serial": "1.23E+12"}, "unit_serial"),
        ({"unit_serial": "A1", "condition": "nearly new"}, "condition"),
        ({"unit_serial": "A1", "owner": "customer"}, "customer_name"),
        ({"unit_serial": "A1", "attachment_2_serial": "X"}, "attachment_2_mfg"),
        ({"unit_serial": "A1", "unit_make": "x" * 61}, "unit_make"),
    ],
)
def test_parse_errors(row: dict[str, str], column: str) -> None:
    errors = parse_row(row, can_price=True).errors
    assert column in {e.column for e in errors}


def test_read_csv_handles_excel_files() -> None:
    semicolons = make_csv([{"Unit Serial": "A1", "Customer Name": "Café Lumber"}], delimiter=";", encoding="cp1252")
    rows, messages = read_csv(semicolons)
    assert rows == [{"unit_serial": "A1", "customer_name": "Café Lumber"}]
    assert messages == []
    rows, messages = read_csv(b"\xef\xbb\xbfserial,colour\r\nA1,red\r\n")
    assert rows == [{"unit_serial": "A1"}]
    assert messages[0].column == "colour"
    with pytest.raises(services.ImportFileError, match="Excel workbook"):
        read_csv(b"PK\x03\x04rest-of-a-zip")
    with pytest.raises(services.ImportFileError, match="unit_serial"):
        read_csv(b"unit_make\r\nHyundai\r\n")


# --- Permissions ---------------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("role", "allowed"),
    [("admin", True), ("sales", True), ("service", True), ("parts", False), ("read_only", False)],
)
def test_who_can_import(client_for: Any, role: str, allowed: bool) -> None:
    client = client_for(role)
    expected = 200 if allowed else 403
    assert client.get(BATCHES).status_code == expected
    assert client.get(f"{BATCHES}/template.csv").status_code == expected
    assert upload(client, make_csv([ROW])).status_code == (201 if allowed else 403)
    assert client.get("/api/v1/admin/api-keys").status_code == (200 if role == "admin" else 403)


@pytest.mark.django_db
def test_anonymous_and_flag_off(anon_client: APIClient, client_for: Any) -> None:
    assert anon_client.get(BATCHES).status_code in (401, 403)
    flag = FeatureFlag.objects.get(key="batch-import")  # created on, by a migration
    flag.enabled = False
    flag.save()
    assert client_for("admin").get(BATCHES).status_code == 404


@pytest.mark.django_db
def test_template_and_sample_downloads(client_for: Any) -> None:
    client = client_for("sales")
    res = client.get(f"{BATCHES}/template.csv")
    assert res["Content-Disposition"] == 'attachment; filename="unit-import-template.csv"'
    assert res.content.decode("utf-8-sig").startswith("customer_name,card_date,")
    assert b"Penobscot Paper Co." in client.get(f"{BATCHES}/sample.csv").content


# --- Validate, apply, re-import, undo -------------------------------------------------------------


@pytest.mark.django_db
def test_full_card_import(client_for: Any) -> None:
    client = client_for("sales")
    existing = Customer.objects.create(name="Penobscot Paper Company")
    second = {**ROW, "unit_serial": "HHK-2", "unit_make": "Hyundai", "customer_name": "Katahdin Lumber", "capacity_lbs": "5 ton"}
    res = upload(client, make_csv([ROW, second]))
    assert res.status_code == 201, res.content
    batch = res.json()
    assert batch["status"] == "draft"
    assert batch["counts"]["plan_create"] == 2
    assert Unit.objects.count() == 0  # checking changes nothing
    preview = rows_of(client, batch["id"])
    assert preview[0]["status"] == "ok"
    assert preview[1]["status"] == "warning"
    assert "new customer “Katahdin Lumber”" in preview[1]["changes"]

    res = client.post(f"{BATCHES}/{batch['id']}/apply", {}, format="json")
    assert res.status_code == 200, res.content
    assert res.json()["status"] == "imported"
    assert res.json()["counts"]["result_created"] == 2

    unit = Unit.objects.get(serial_normalized="FGA2571234")
    assert unit.card_date.isoformat() == "2024-03-12"
    assert unit.card_customer_name == "Penobscot Paper Co."
    assert unit.capacity_lbs == 5000
    assert unit.needs_review is False
    assert {c.kind: c.spools for c in unit.components.all()} == {"engine": "", "control_valve": "3SP"}
    assert [(f.dimensions, f.quantity, f.length_in) for f in unit.forks.all()] == [("1.75 x 4 x 48 STD", 2, Decimal("48.00"))]
    att = unit.attachments.get()
    assert (att.manufacturer, att.hose_reel, att.side) == ("Cascade", True, "LH")
    reading = unit.hour_readings.get()
    assert (reading.hours, reading.reading_date.isoformat(), reading.source) == (Decimal("10288.0"), "2024-03-12", "card")
    owner = OwnershipRecord.objects.get(unit=unit)
    assert owner.customer == existing  # matched despite "Co." vs "Company"

    flagged = Unit.objects.get(serial_normalized="HHK2")
    assert flagged.needs_review is True
    assert "capacity_lbs as written: 5 ton" in flagged.notes
    assert flagged.ownerships.get().customer.name == "Katahdin Lumber"

    # The same file again changes nothing.
    again = upload(client, make_csv([ROW, second])).json()
    assert again["counts"]["plan_unchanged"] == 2
    client.post(f"{BATCHES}/{again['id']}/apply", {}, format="json")
    assert Unit.objects.count() == 2
    assert HourMeterReading.objects.count() == 2
    assert Customer.objects.filter(name="Katahdin Lumber").count() == 1


@pytest.mark.django_db
def test_update_then_undo_restores_previous_values(client_for: Any) -> None:
    client = client_for("admin")
    first = upload(client, make_csv([ROW])).json()
    client.post(f"{BATCHES}/{first['id']}/apply", {}, format="json")
    unit = Unit.objects.get()

    changed = {**ROW, "mechanic": "Dave", "engine_serial": "K25-1", "forks": "2 x 5 x 60", "hour_meter": "11000"}
    second = upload(client, make_csv([changed])).json()
    row = rows_of(client, second["id"])[0]
    assert row["plan"] == "update"
    assert {"mechanic", "engine serial_number", "forks", "hour_meter"} <= set(row["changes"])
    client.post(f"{BATCHES}/{second['id']}/apply", {}, format="json")
    unit.refresh_from_db()
    assert unit.mechanic == "Dave"
    assert [f.dimensions for f in unit.forks.all()] == ["2 x 5 x 60"]

    res = client.post(f"{BATCHES}/{second['id']}/undo")
    assert res.status_code == 200, res.content
    assert res.json()["status"] == "undone"
    unit.refresh_from_db()
    assert unit.mechanic == "Sam W."
    assert unit.components.get(kind="engine").serial_number == ""
    assert [f.dimensions for f in unit.forks.all()] == ["1.75 x 4 x 48 STD"]
    assert unit.hour_readings.count() == 1


@pytest.mark.django_db
def test_undo_new_units_and_reimport_brings_them_back(client_for: Any) -> None:
    client = client_for("sales")
    batch = upload(client, make_csv([ROW])).json()
    client.post(f"{BATCHES}/{batch['id']}/apply", {}, format="json")
    assert Customer.objects.count() == 1
    client.post(f"{BATCHES}/{batch['id']}/undo")
    assert Unit.objects.count() == 0
    assert Customer.objects.count() == 0  # the import added it, nothing else uses it
    assert Unit.all_objects.count() == 1  # removed, not deleted

    fixed = upload(client, make_csv([{**ROW, "mechanic": "Sam Wilson"}])).json()
    row = rows_of(client, fixed["id"])[0]
    assert row["plan"] == "update"
    assert "brought back" in row["warnings"][0]["message"]
    client.post(f"{BATCHES}/{fixed['id']}/apply", {}, format="json")
    unit = Unit.objects.get()
    assert unit.mechanic == "Sam Wilson"
    assert unit.ownerships.count() == 1


@pytest.mark.django_db
def test_undo_leaves_units_edited_after_the_import(client_for: Any) -> None:
    client = client_for("admin")
    batch = upload(client, make_csv([ROW, {**ROW, "unit_serial": "OTHER-1"}])).json()
    client.post(f"{BATCHES}/{batch['id']}/apply", {}, format="json")
    edited = Unit.objects.get(serial_normalized="FGA2571234")
    client.patch(f"/api/v1/units/{edited.pk}", {"notes": "Checked by hand"}, format="json")

    res = client.post(f"{BATCHES}/{batch['id']}/undo").json()
    assert res["counts"]["kept"] == 1
    assert res["counts"]["undone"] == 1
    assert list(Unit.objects.values_list("serial_number", flat=True)) == ["FGA25-71234"]
    kept = rows_of(client, batch["id"], "kept")
    assert kept[0]["undo_result"].startswith("Kept")


@pytest.mark.django_db
def test_only_admin_or_the_importer_can_undo(client_for: Any) -> None:
    importer = client_for("service")
    batch = upload(importer, make_csv([ROW])).json()
    importer.post(f"{BATCHES}/{batch['id']}/apply", {}, format="json")
    assert client_for("sales").post(f"{BATCHES}/{batch['id']}/undo").status_code == 403
    assert importer.post(f"{BATCHES}/{batch['id']}/undo").status_code == 200


@pytest.mark.django_db
def test_errors_block_import_unless_skipped(client_for: Any) -> None:
    client = client_for("admin")
    rows = [ROW, {**ROW, "unit_serial": "fga25 71234"}, {"unit_model": "No serial"}, {**ROW, "unit_serial": "B2", "condition": "meh"}]
    batch = upload(client, make_csv(rows)).json()
    assert batch["counts"]["error"] == 3
    errors = rows_of(client, batch["id"], "errors")
    assert "Same unit as row 2" in errors[0]["errors"][0]["message"]
    res = client.post(f"{BATCHES}/{batch['id']}/apply", {}, format="json")
    assert res.status_code == 400
    assert Unit.objects.count() == 0
    res = client.post(f"{BATCHES}/{batch['id']}/apply", {"skip_invalid": True}, format="json")
    assert res.json()["counts"]["result_created"] == 1
    assert res.json()["counts"]["result_skipped"] == 3


@pytest.mark.django_db
def test_skip_existing_and_removed_units(client_for: Any) -> None:
    client = client_for("admin")
    batch = upload(client, make_csv([ROW])).json()
    client.post(f"{BATCHES}/{batch['id']}/apply", {}, format="json")
    second = upload(client, make_csv([{**ROW, "mechanic": "Changed"}])).json()
    client.post(f"{BATCHES}/{second['id']}/apply", {"on_existing": "skip"}, format="json")
    assert Unit.objects.get().mechanic == "Sam W."

    removed = Unit.objects.create(make="Hyundai", model="20BT-9", serial_number="GONE-1")
    removed.soft_delete()
    third = upload(client, make_csv([{**ROW, "unit_serial": "gone 1"}])).json()
    assert "removed unit" in rows_of(client, third["id"])[0]["errors"][0]["message"]


@pytest.mark.django_db
def test_existing_owner_and_prices(client_for: Any) -> None:
    sales = client_for("sales")
    batch = upload(sales, make_csv([{**ROW, "customer_name": "", "owner": "stock", "stock_status": "available", "asking_price": "$18,500"}])).json()
    sales.post(f"{BATCHES}/{batch['id']}/apply", {}, format="json")
    unit = Unit.objects.get()
    assert (unit.asking_price, unit.stock_status) == (Decimal("18500.00"), "available")
    assert unit.ownerships.get().owner_kind == "dealer"

    service = client_for("service")
    again = upload(service, make_csv([{**ROW, "asking_price": "1"}])).json()
    row = rows_of(service, again["id"])[0]
    messages = {w["column"]: w["message"] for w in row["warnings"]}
    assert "Only admin and sales" in messages["asking_price"]
    assert "Kept the current owner" in messages["customer_name"]
    service.post(f"{BATCHES}/{again['id']}/apply", {}, format="json")
    unit.refresh_from_db()
    assert unit.asking_price == Decimal("18500.00")
    assert unit.ownerships.get().owner_kind == "dealer"


@pytest.mark.django_db
def test_similar_customer_warns(client_for: Any) -> None:
    Customer.objects.create(name="Bangor Building Supply")
    client = client_for("admin")
    batch = upload(client, make_csv([{**ROW, "customer_name": "Bangor Bldg Supply"}])).json()
    warning = rows_of(client, batch["id"])[0]["warnings"][0]
    assert "Bangor Building Supply" in warning["message"]


@pytest.mark.django_db
def test_scanned_cards_are_attached(client_for: Any) -> None:
    client = client_for("sales")
    rows = [{**ROW, "source_image_filename": "Card-0001.png"}, {**ROW, "unit_serial": "B2", "source_image_filename": "missing.jpg"}]
    batch = upload(client, make_csv(rows)).json()
    res = client.post(f"{BATCHES}/{batch['id']}/files", {"file": png("card-0001.png")}, format="multipart")
    assert res.status_code == 201, res.content
    dup = client.post(f"{BATCHES}/{batch['id']}/files", {"file": png("CARD-0001.png")}, format="multipart")
    assert dup.status_code == 400
    bad = client.post(f"{BATCHES}/{batch['id']}/files", {"file": SimpleUploadedFile("x.png", b"not an image")}, format="multipart")
    assert bad.status_code == 400
    client.post(f"{BATCHES}/{batch['id']}/files", {"file": png("unused.png")}, format="multipart")
    checked = client.post(f"{BATCHES}/{batch['id']}/validate").json()
    assert checked["file_messages"][0]["column"] == "unused.png"
    preview = rows_of(client, batch["id"])
    assert "card scan card-0001.png" in preview[0]["changes"]
    assert "wasn't uploaded" in preview[1]["warnings"][0]["message"]

    client.post(f"{BATCHES}/{batch['id']}/apply", {}, format="json")
    scan = UnitFile.objects.get(unit__serial_normalized="FGA2571234")
    assert (scan.kind, scan.original_name, scan.content_type) == ("scanned_card", "card-0001.png", "image/png")
    assert client.post(f"{BATCHES}/{batch['id']}/files", {"file": png("late.png")}, format="multipart").status_code == 400


@pytest.mark.django_db
def test_big_batches_run_in_the_background(client_for: Any) -> None:
    client = client_for("admin")
    batch = upload(client, make_csv([ROW, {**ROW, "unit_serial": "B2"}])).json()
    with mock.patch.object(services, "INLINE_MAX_ROWS", 1), mock.patch("apps.imports.tasks.apply_import.configure") as configure:
        res = client.post(f"{BATCHES}/{batch['id']}/apply", {}, format="json").json()
    assert res["status"] == "queued"
    configure.return_value.defer.assert_called_once_with(batch_id=batch["id"])
    services.apply_batch(batch["id"])
    services.apply_batch(batch["id"])  # a retried job does nothing more
    assert ImportBatch.objects.get(pk=batch["id"]).status == "imported"
    assert Unit.objects.count() == 2


@pytest.mark.django_db
def test_failed_job_can_be_retried(client_for: Any) -> None:
    client = client_for("admin")
    batch = upload(client, make_csv([ROW, {**ROW, "unit_serial": "B2"}])).json()
    real = services.apply_row
    calls = {"n": 0}

    def flaky(*args: Any) -> None:
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("database went away")
        real(*args)

    with mock.patch.object(services, "apply_row", flaky), pytest.raises(RuntimeError):
        client.post(f"{BATCHES}/{batch['id']}/apply", {}, format="json")
    failed = ImportBatch.objects.get(pk=batch["id"])
    assert failed.status == "failed"
    assert "database went away" in failed.error
    assert Unit.objects.count() == 1
    res = client.post(f"{BATCHES}/{batch['id']}/apply", {}, format="json")
    assert res.json()["status"] == "imported"
    assert Unit.objects.count() == 2
    assert ImportRow.objects.filter(batch_id=batch["id"], result="created").count() == 2


@pytest.mark.django_db
def test_discard_draft(client_for: Any) -> None:
    client = client_for("admin")
    batch = upload(client, make_csv([ROW])).json()
    assert client.post(f"{BATCHES}/{batch['id']}/discard").json()["status"] == "discarded"
    assert client.get(BATCHES).json()["count"] == 0
    assert client.post(f"{BATCHES}/{batch['id']}/apply", {}, format="json").status_code == 400


@pytest.mark.django_db
def test_bad_files_are_refused(client_for: Any) -> None:
    client = client_for("admin")
    res = upload(client, b"PK\x03\x04junk", "cards.xlsx")
    assert res.status_code == 400
    assert "CSV UTF-8" in res.json()["fields"]["file"][0]
    assert upload(client, b"").status_code == 400
    assert upload(client, b"unit_serial\r\n").status_code == 400


@pytest.mark.django_db
def test_audit_entries_are_tagged_with_the_batch(client_for: Any) -> None:
    from apps.core.models import AuditLog

    client = client_for("admin")
    batch = upload(client, make_csv([ROW])).json()
    client.post(f"{BATCHES}/{batch['id']}/apply", {}, format="json")
    unit = Unit.objects.get()
    entry = AuditLog.objects.get(object_id=str(unit.pk), action="create")
    assert entry.request_id == f"import-{batch['id']}"
    assert entry.source == "import"
    assert entry.actor is not None


# --- API keys and the JSON API --------------------------------------------------------------


@pytest.fixture
def api_key(client_for: Any) -> tuple[APIClient, str]:
    admin = client_for("admin")
    res = admin.post("/api/v1/admin/api-keys", {"name": "Card scanner"}, format="json")
    assert res.status_code == 201, res.content
    raw = res.json()["key"]
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Api-Key {raw}")
    return client, raw


@pytest.mark.django_db
def test_api_keys_are_shown_once_and_stored_hashed(client_for: Any, api_key: tuple[APIClient, str]) -> None:
    _, raw = api_key
    key = ApiKey.objects.get()
    assert raw.startswith("mmh_") and key.key_hash != raw and raw.startswith(key.prefix)
    listed = client_for("admin").get("/api/v1/admin/api-keys").json()
    assert "key" not in listed[0]
    assert listed[0]["name"] == "Card scanner"


@pytest.mark.django_db
def test_api_import(api_key: tuple[APIClient, str]) -> None:
    client, _ = api_key
    unit = {"unit_serial": "API-1", "unit_make": "Hyundai", "unit_model": "50D-9", "forks": ["1.75 x 4 x 48", "1.75 x 4 x 48"], "attachment_1_mfg": "Cascade", "attachment_1_hose_reel": True, "hour_meter": 512}
    dry = client.post(f"{API}/units", {"units": [unit], "dry_run": True}, format="json")
    assert dry.status_code == 200, dry.content
    assert dry.json()["rows"][0]["plan"] == "create"
    assert Unit.objects.count() == 0

    bad = client.post(f"{API}/units", {"units": [unit, {"unit_model": "no serial"}]}, format="json")
    assert bad.status_code == 422
    assert bad.json()["rows"][1]["errors"][0]["column"] == "unit_serial"
    assert Unit.objects.count() == 0

    res = client.post(f"{API}/units", {"units": [unit], "reference": "scan-7"}, format="json")
    assert res.status_code == 201, res.content
    body = res.json()
    assert body["rows"][0]["result"] == "created"
    made = Unit.objects.get()
    assert made.forks.get().quantity == 2
    assert made.attachments.get().hose_reel is True
    assert made.created_by.email.startswith("admin")  # recorded as the key's admin

    status = client.get(f"{API}/batches/{body['id']}")
    assert status.json()["reference"] == "scan-7"
    unknown = client.post(f"{API}/units", {"units": [{"unit_serial": "X", "colour": "red"}]}, format="json")
    assert unknown.status_code == 400


@pytest.mark.django_db
def test_api_scans_via_draft_batch(api_key: tuple[APIClient, str]) -> None:
    client, _ = api_key
    draft = client.post(f"{API}/units", {"units": [{"unit_serial": "API-2", "source_image_filename": "c.png"}], "dry_run": True}, format="json").json()
    res = client.post(f"{API}/batches/{draft['id']}/files", {"file": png("c.png")}, format="multipart")
    assert res.status_code == 201, res.content
    done = client.post(f"{API}/batches/{draft['id']}/apply", {}, format="json")
    assert done.status_code == 201
    assert UnitFile.objects.get().kind == "scanned_card"


@pytest.mark.django_db
def test_api_auth_and_limits(api_key: tuple[APIClient, str], client_for: Any) -> None:
    client, raw = api_key
    assert APIClient().post(f"{API}/units", {"units": [{"unit_serial": "A"}]}, format="json").status_code == 401
    wrong = APIClient()
    wrong.credentials(HTTP_AUTHORIZATION="Api-Key mmh_nope")
    assert wrong.post(f"{API}/units", {"units": [{"unit_serial": "A"}]}, format="json").status_code == 401
    # A session user can't use the API endpoints without a key.
    assert client_for("admin").post(f"{API}/units", {"units": [{"unit_serial": "A"}]}, format="json").status_code in (401, 403)

    # Batches are only visible to the key that made them.
    batch = client.post(f"{API}/units", {"units": [{"unit_serial": "A"}], "dry_run": True}, format="json").json()
    other = client_for("admin").post("/api/v1/admin/api-keys", {"name": "Other"}, format="json").json()
    other_client = APIClient()
    other_client.credentials(HTTP_AUTHORIZATION=f"Api-Key {other['key']}")
    assert other_client.get(f"{API}/batches/{batch['id']}").status_code == 404

    with mock.patch("apps.imports.authentication.ApiKeyThrottle.THROTTLE_RATES", {"import-api": "2/min"}):
        codes = [client.get(f"{API}/batches/{batch['id']}").status_code for _ in range(3)]
    assert codes[-1] == 429

    key = ApiKey.objects.get(name="Card scanner")
    admin = client_for("admin")
    assert admin.post(f"/api/v1/admin/api-keys/{key.pk}/revoke").status_code == 200
    assert client.get(f"{API}/batches/{batch['id']}").status_code == 401


@pytest.mark.django_db
def test_api_key_stops_working_when_creator_loses_access(api_key: tuple[APIClient, str]) -> None:
    client, _ = api_key
    creator = ApiKey.objects.get().created_by
    creator.role = "parts"
    creator.save()
    assert client.post(f"{API}/units", {"units": [{"unit_serial": "A"}], "dry_run": True}, format="json").status_code == 401


def test_schema_is_public(client: Any) -> None:
    res = client.get(f"{API}/schema.json")
    assert res.status_code == 200
    assert "unit_serial" in res.json()["$defs"]["unit"]["properties"]
