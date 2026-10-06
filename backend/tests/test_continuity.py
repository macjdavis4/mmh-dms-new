"""Phase 13: the nightly paper backup and the offline copy for devices."""

import io
import zipfile
from datetime import timedelta
from typing import Any

import pytest
from django.core.files.storage import storages
from django.db import connection
from django.utils import timezone
from pypdf import PdfReader

from apps.core.models import FeatureFlag
from apps.ops import paper
from apps.ops.models import BackupRun
from apps.service.models import WorkOrder
from apps.units.models import Unit

PAPER = "/api/v1/admin/paper-backups"
OFFLINE = "/api/v1/offline/units"


@pytest.fixture
def demo(db: Any, make_user: Any) -> None:
    from apps.parts.demo import load_demo_parts, load_demo_stock
    from apps.service.demo import load_demo_work_orders
    from apps.units.demo import load_demo_data

    make_user("service", email="service@mmh.test")
    load_demo_data(with_files=False)
    load_demo_work_orders()
    load_demo_parts()
    load_demo_stock()


def read(run: BackupRun, name: str) -> bytes:
    with paper.open_file(run, name) as f:
        return f.read()  # type: ignore[no-any-return]


# --- Paper backup --------------------------------------------------------------------------


@pytest.mark.django_db
def test_paper_backup_files(demo: None) -> None:
    run = paper.run_paper_backup()
    assert run.status == "succeeded", run.error
    assert run.objects_copied == len(paper.FILES)
    open_count = WorkOrder.objects.filter(status__in=WorkOrder.OPEN_STATUSES).count()
    assert run.row_counts["open_work_orders"] == open_count == 3
    # Every open work order printed in full after a cover page.
    pdf = PdfReader(io.BytesIO(read(run, "open-work-orders.pdf")))
    text = "\n".join(page.extract_text() for page in pdf.pages)
    assert len(pdf.pages) >= 1 + open_count
    for wo in WorkOrder.objects.filter(status__in=WorkOrder.OPEN_STATUSES):
        assert wo.number in text
    customers = read(run, "customers.csv").decode("utf-8-sig")
    assert customers.splitlines()[0].startswith("Customer,Phone,Contact")
    assert "Katahdin Lumber" in customers
    units = read(run, "units.csv").decode("utf-8-sig")
    header = units.splitlines()[0].split(",")
    assert "serial_number" in header and "components" in header
    assert not {"cost", "asking_price", "sale_price"} & set(header)  # no money on paper
    assert "HHKHFV30K00057" in units
    parts_csv = read(run, "parts.csv").decode("utf-8-sig")
    assert "31N4-01050" in parts_csv
    bundle = zipfile.ZipFile(io.BytesIO(read(run, "paper-backup.zip")))
    names = {n.split("/", 1)[1] for n in bundle.namelist()}
    assert names == {name for name, _, _ in paper.FILES} - {"paper-backup.zip"}


@pytest.mark.django_db
def test_paper_backup_once_a_day_unless_forced(demo: None) -> None:
    first = paper.run_paper_backup()
    again = paper.run_paper_backup()
    assert again.pk == first.pk  # skipped, already done today
    fresh = paper.run_paper_backup(force=True)
    assert fresh.pk != first.pk and fresh.status == "succeeded"
    first.refresh_from_db()
    assert first.status == "skipped"
    # The files of the day are the fresh ones (not renamed copies).
    store = storages["paper"]
    assert store.exists(f"{fresh.object_key}/parts.csv")


@pytest.mark.django_db
def test_paper_backup_failure_is_recorded(demo: None, monkeypatch: Any) -> None:
    def broken(today: Any) -> Any:
        raise RuntimeError("disk full")

    monkeypatch.setattr(paper, "build", broken)
    run = paper.run_paper_backup()
    assert run.status == "failed"
    assert "disk full" in run.error


@pytest.mark.django_db
def test_csv_cells_cant_become_formulas() -> None:
    assert paper._safe("=CMD()") == "'=CMD()"
    assert paper._safe("-12.5") == "-12.5"
    assert paper._safe(None) == ""


@pytest.mark.django_db
def test_nightly_task(demo: None) -> None:
    from apps.ops.tasks import nightly_paper_backup

    nightly_paper_backup(timestamp=0)
    nightly_paper_backup(timestamp=0)
    assert BackupRun.objects.filter(kind="paper", status="succeeded").count() == 1


@pytest.mark.django_db
def test_paper_backup_admin_page(client_for: Any, demo: None) -> None:
    admin = client_for("admin")
    assert admin.get(PAPER).json()["results"] == []
    made = admin.post(PAPER)
    assert made.status_code == 201, made.json()
    body = made.json()
    assert body["status"] == "succeeded"
    assert body["folder"] == f"paper/test/{body['date']}/"
    assert [f["name"] for f in body["files"]] == [name for name, _, _ in paper.FILES]
    pdf = admin.get(f"{PAPER}/{body['id']}/customers.pdf")
    assert pdf.status_code == 200 and pdf["Content-Type"] == "application/pdf"
    assert pdf["Content-Disposition"].startswith("inline")
    csv = admin.get(f"{PAPER}/{body['id']}/parts.csv")
    assert csv["Content-Disposition"].startswith("attachment")
    assert admin.get(f"{PAPER}/{body['id']}/secrets.txt").status_code == 404
    assert len(admin.get(PAPER).json()["results"]) == 1
    health = admin.get("/api/v1/admin/health").json()
    assert health["last_paper_backup"]["status"] == "succeeded"
    assert health["last_backup"] is None  # the database backup is reported separately
    for role in ("sales", "service", "parts", "read_only"):
        client = client_for(role)
        assert client.get(PAPER).status_code == 403
        assert client.post(PAPER).status_code == 403
        assert client.get(f"{PAPER}/{body['id']}/customers.pdf").status_code == 403


# --- Offline copy --------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("role", ["admin", "sales", "service", "parts", "read_only"])
def test_offline_copy(client_for: Any, demo: None, role: str) -> None:
    res = client_for(role).get(OFFLINE)
    assert res.status_code == 200
    assert res["Cache-Control"] == "private, no-store"
    body = res.json()
    assert body["keep_days"] == 14
    units = {u["serial_number"]: u for u in body["units"]}
    assert units, "no units saved"
    for unit in units.values():
        assert not {"cost", "asking_price", "sale_price"} & set(unit)
        assert "components" in unit and "attachments" in unit  # the full spec card
    stock = [u for u in body["units"] if u["in_stock"]]
    assert stock and all(u["owner_kind"] == "dealer" for u in stock)
    # A unit with open work is in; a customer's unit nobody has touched for a year isn't.
    assert "HHKHFV30K00057" in units


@pytest.mark.django_db
def test_offline_copy_leaves_out_old_customer_units(client_for: Any, demo: None) -> None:
    old = Unit.objects.create(make="Clark", model="C25", serial_number="OLD-1")
    with connection.cursor() as cur:  # last touched over a year ago
        cur.execute(
            "UPDATE units_unit SET updated_at = %s WHERE id = %s",
            [timezone.now() - timedelta(days=400), old.pk],
        )
    serials = {u["serial_number"] for u in client_for("service").get(OFFLINE).json()["units"]}
    assert "OLD-1" not in serials


@pytest.mark.django_db
def test_offline_flag_and_anonymous(client_for: Any, anon_client: Any, demo: None) -> None:
    assert anon_client.get(OFFLINE).status_code in (401, 403)
    flag = FeatureFlag.objects.get(key="offline")
    flag.enabled = False
    flag.save()
    assert client_for("admin").get(OFFLINE).status_code == 404


def test_service_worker_served_at_root(client: Any, tmp_path: Any, monkeypatch: Any) -> None:
    from apps.core import views

    monkeypatch.setattr(views, "_SERVICE_WORKER", tmp_path / "nope.js")
    missing = client.get("/sw.js")
    assert missing.status_code == 200 and b"no service worker" in missing.content
    built = tmp_path / "sw.js"
    built.write_text("self.addEventListener('fetch', () => {});")
    monkeypatch.setattr(views, "_SERVICE_WORKER", built)
    res = client.get("/sw.js")
    assert res["Content-Type"].startswith("text/javascript")
    assert res["Cache-Control"] == "no-cache, max-age=0"
    assert res["Service-Worker-Allowed"] == "/"
    assert b"addEventListener" in res.content
