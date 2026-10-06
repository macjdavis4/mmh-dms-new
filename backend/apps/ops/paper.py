"""Nightly paper backup: what the shop needs to keep working if the app is
down, as files anyone can open and print.

- open-work-orders.pdf: every open work order, printed in full (one per page)
- customers.pdf: customer phone list
- parts.pdf: parts list with bins and on-hand counts
- stock-units.pdf: units in our stock
- customers.csv, units.csv, parts.csv, work-orders.csv: the same for a spreadsheet
- paper-backup.zip: all of the above in one download

Files go to the `paper` storage (the second-region backup bucket, under
paper/<environment>/<date>/), are kept 30 days, and are listed under
Admin > Paper backup. No costs or prices are included: the database backup
has everything; these are for running the shop.

Idempotent: a day that already has a successful run is skipped.
"""

from __future__ import annotations

import csv
import io
import logging
import zipfile
from collections.abc import Iterable, Sequence
from datetime import date, timedelta
from typing import Any

from django.core.files.base import ContentFile
from django.core.files.storage import storages
from django.db.models import Prefetch
from django.utils import timezone
from pypdf import PdfReader, PdfWriter

from apps.core.pdf import grid, p, render
from apps.customers.models import Contact, Customer
from apps.parts.models import Part
from apps.service.models import WorkOrder
from apps.service.pdf import work_order_pdf
from apps.units.models import Unit
from apps.units.serializers import UnitSerializer
from apps.units.views import annotate_units

from .models import BackupRun

logger = logging.getLogger("mmh.backup")

FILES = [
    ("open-work-orders.pdf", "application/pdf", "Open work orders, printed in full"),
    ("customers.pdf", "application/pdf", "Customer phone list"),
    ("parts.pdf", "application/pdf", "Parts list with bins and counts"),
    ("stock-units.pdf", "application/pdf", "Units in our stock"),
    ("customers.csv", "text/csv", "Customers (spreadsheet)"),
    ("units.csv", "text/csv", "Units with spec cards (spreadsheet)"),
    ("parts.csv", "text/csv", "Parts (spreadsheet)"),
    ("work-orders.csv", "text/csv", "Work orders, open and last 90 days (spreadsheet)"),
    ("paper-backup.zip", "application/zip", "All of the above in one file"),
]
CONTENT_TYPES = {name: kind for name, kind, _ in FILES}
DESCRIPTIONS = {name: text for name, _, text in FILES}
IN_STOCK = ("available", "on_hold", "in_prep")
NO_MONEY = {"cost", "asking_price", "sale_price"}
UNIT_SKIP = NO_MONEY | {"components", "forks", "attachments", "is_deleted", "primary_photo_id"}


def storage() -> Any:
    return storages["paper"]


def storage_location_env() -> str:
    """The environment folder the files are under (for the DigitalOcean steps)."""
    from django.conf import settings

    return str(settings.APP_ENV)


def folder(day: date) -> str:
    return f"{day:%Y-%m-%d}"


def _csv(header: Sequence[str], rows: Iterable[Sequence[Any]]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\r\n")
    writer.writerow(header)
    for row in rows:
        writer.writerow([_safe(v) for v in row])
    return ("﻿" + buf.getvalue()).encode("utf-8")


def _safe(value: Any) -> str:
    """A spreadsheet runs text starting with = + - @ as a formula; keep it text."""
    text = "" if value is None else str(value)
    if text[:1] in ("=", "+", "-", "@") and not _number(text):
        return "'" + text
    return text


def _number(text: str) -> bool:
    try:
        float(text)
    except ValueError:
        return False
    return True


def _primary(contacts: Sequence[Contact]) -> Contact | None:
    return next((c for c in contacts if c.is_primary), contacts[0] if contacts else None)


def _contact_name(c: Contact | None) -> str:
    return " ".join(x for x in (c.first_name, c.last_name) if x) if c else ""


# --- The files ---------------------------------------------------------------------------


def customers_files(customers: list[Customer]) -> tuple[bytes, bytes]:
    rows = []
    for c in customers:
        contact = _primary(list(c.contacts.all()))
        address = next(iter(c.addresses.all()), None)
        rows.append(
            [
                c.name,
                c.phone,
                _contact_name(contact),
                (contact.mobile or contact.phone) if contact else "",
                address.line1 if address else "",
                address.city if address else "",
                address.state if address else "",
                address.postal_code if address else "",
                c.email,
                c.account_number,
            ]
        )
    header = ["Customer", "Phone", "Contact", "Contact phone", "Address", "City", "State", "ZIP"]
    pdf = render(
        [
            p("Customer phone list", "title"),
            grid(
                ["Customer", "Phone", "Contact", "Contact phone", "City"],
                [[r[0], r[1], r[2], r[3], r[5]] for r in rows],
                [0.32, 0.17, 0.2, 0.17, 0.14],
            ),
        ],
        title="Customer phone list",
        label="Paper backup",
    )
    return pdf, _csv([*header, "Email", "Account #"], rows)


def units_csv(units: list[Unit]) -> bytes:
    data = [UnitSerializer(u, context={}).data for u in units]
    keys = [k for k in (data[0].keys() if data else []) if k not in UNIT_SKIP]
    header = [*keys, "components", "forks", "attachments"]
    rows = []
    for d in data:
        comps = "; ".join(
            f"{c['kind']}: "
            + " ".join(x for x in (c.get("make"), c.get("model"), c.get("serial")) if x)
            for c in d["components"]
        )
        forks = "; ".join(str(f.get("dimensions", "")) for f in d["forks"])
        attachments = "; ".join(
            " ".join(
                str(a.get(k) or "") for k in ("manufacturer", "type", "model", "serial")
            ).strip()
            for a in d["attachments"]
        )
        rows.append([*(d.get(k) for k in keys), comps, forks, attachments])
    return _csv(header, rows)


def _hours(unit: Unit) -> str:
    hours = getattr(unit, "current_hours", None)  # annotated by annotate_units
    return f"{hours:,.0f}" if hours is not None else ""


def stock_pdf(units: list[Unit]) -> bytes:
    stock = [u for u in units if u.stock_status in IN_STOCK]
    return render(
        [
            p("Units in our stock", "title"),
            grid(
                ["Stock #", "Unit", "Serial", "Status", "Hours"],
                [
                    [
                        u.stock_number,
                        " ".join(x for x in (str(u.year or ""), u.make, u.model) if x),
                        u.serial_number,
                        u.get_stock_status_display(),
                        _hours(u),
                    ]
                    for u in stock
                ],
                [0.14, 0.34, 0.24, 0.14, 0.14],
            ),
        ],
        title="Units in stock",
        label="Paper backup",
    )


def parts_files(parts: list[Part]) -> tuple[bytes, bytes]:
    rows = [
        [
            pt.manufacturer,
            pt.part_number,
            pt.description,
            pt.bin.code if pt.bin else "",
            f"{pt.stock.on_hand.normalize():f}" if hasattr(pt, "stock") else "0",
            "" if pt.reorder_point is None else f"{pt.reorder_point.normalize():f}",
            "" if pt.list_price is None else f"{pt.list_price:.2f}",
            pt.vendor,
        ]
        for pt in parts
    ]
    pdf = render(
        [
            p("Parts list", "title"),
            grid(
                ["Part #", "Description", "Bin", "On hand", "Reorder at"],
                [[r[1], r[2], r[3], r[4], r[5]] for r in rows],
                [0.2, 0.44, 0.14, 0.11, 0.11],
            ),
        ],
        title="Parts list",
        label="Paper backup",
    )
    header = ["Maker", "Part #", "Description", "Bin", "On hand", "Reorder at", "List price"]
    return pdf, _csv([*header, "Supplier"], rows)


def work_orders_files(today: date) -> tuple[bytes, bytes]:
    base = WorkOrder.objects.select_related("unit", "customer", "assigned_to").order_by("number")
    open_wos = list(base.filter(status__in=WorkOrder.OPEN_STATUSES))
    recent = base.filter(opened_on__gte=today - timedelta(days=90)) | base.filter(
        status__in=WorkOrder.OPEN_STATUSES
    )
    rows = [
        [
            wo.number,
            wo.get_status_display(),
            wo.get_kind_display(),
            wo.opened_on,
            wo.due_on or "",
            wo.unit.serial_number,
            " ".join(x for x in (wo.unit.make, wo.unit.model) if x),
            wo.customer.name if wo.customer else "Our stock",
            (wo.assigned_to.full_name or wo.assigned_to.email) if wo.assigned_to else "",
            wo.complaint,
            wo.correction,
        ]
        for wo in recent.distinct()
    ]
    writer = PdfWriter()
    cover = render(
        [
            p(f"Open work orders: {len(open_wos)}", "title"),
            p("Each one follows on its own pages, ready to work from and sign.", "small"),
            grid(
                ["Work order", "Unit", "Customer", "Due"],
                [
                    [
                        wo.number,
                        " ".join(
                            x for x in (wo.unit.make, wo.unit.model, wo.unit.serial_number) if x
                        ),
                        wo.customer.name if wo.customer else "Our stock",
                        wo.due_on.isoformat() if wo.due_on else "",
                    ]
                    for wo in open_wos
                ],
                [0.16, 0.4, 0.3, 0.14],
            ),
        ],
        title="Open work orders",
        label="Paper backup",
    )
    writer.append(PdfReader(io.BytesIO(cover)))
    for wo in open_wos:
        writer.append(PdfReader(io.BytesIO(work_order_pdf(wo))))
    out = io.BytesIO()
    writer.write(out)
    header = ["Work order", "Status", "Type", "Opened", "Due", "Serial", "Unit", "Customer"]
    return out.getvalue(), _csv([*header, "Mechanic", "Complaint", "Correction"], rows)


def build(today: date) -> tuple[dict[str, bytes], dict[str, int]]:
    customers = list(
        Customer.objects.order_by("name").prefetch_related(
            Prefetch("contacts", queryset=Contact.objects.order_by("-is_primary", "last_name")),
            "addresses",
        )
    )
    units = list(
        annotate_units(Unit.objects.all())
        .prefetch_related("components", "forks", "attachments")
        .order_by("make", "model", "serial_number")
    )
    parts = list(Part.objects.select_related("bin", "stock").order_by("number_normalized"))
    files: dict[str, bytes] = {}
    files["open-work-orders.pdf"], files["work-orders.csv"] = work_orders_files(today)
    files["customers.pdf"], files["customers.csv"] = customers_files(customers)
    files["parts.pdf"], files["parts.csv"] = parts_files(parts)
    files["stock-units.pdf"] = stock_pdf(units)
    files["units.csv"] = units_csv(units)
    bundle = io.BytesIO()
    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(f"paper-backup-{today:%Y-%m-%d}/{name}", data)
    files["paper-backup.zip"] = bundle.getvalue()
    counts = {
        "customers": len(customers),
        "units": len(units),
        "parts": len(parts),
        "open_work_orders": WorkOrder.objects.filter(status__in=WorkOrder.OPEN_STATUSES).count(),
    }
    return files, counts


def run_paper_backup(force: bool = False) -> BackupRun:
    today = timezone.localdate()
    done = BackupRun.objects.filter(
        kind=BackupRun.Kind.PAPER, run_date=today, status=BackupRun.Status.SUCCEEDED
    ).first()
    if done and not force:
        logger.info("paper backup already done today; skipping")
        return done
    if done:  # a fresh copy today, made by hand: the old run gives way
        done.status = BackupRun.Status.SKIPPED
        done.error = "Replaced by a newer copy the same day."
        done.save()
    run = BackupRun.objects.create(
        kind=BackupRun.Kind.PAPER, run_date=today, object_key=folder(today)
    )
    try:
        files, counts = build(today)
        store = storage()
        for name, data in files.items():
            path = f"{folder(today)}/{name}"
            if store.exists(path):  # a second copy the same day replaces the first
                store.delete(path)
            store.save(path, ContentFile(data))
        run.status = BackupRun.Status.SUCCEEDED
        run.size_bytes = sum(len(d) for d in files.values())
        run.objects_copied = len(files)
        run.row_counts = counts
    except Exception as exc:
        run.status = BackupRun.Status.FAILED
        run.error = str(exc)[:2000]
        logger.exception("paper backup failed")
    run.finished_at = timezone.now()
    run.save()
    if run.status == BackupRun.Status.SUCCEEDED:
        logger.info("paper backup done", extra={"files": run.objects_copied, "counts": counts})
    return run


def open_file(run: BackupRun, name: str) -> Any:
    if name not in CONTENT_TYPES:
        raise FileNotFoundError(name)
    return storage().open(f"{run.object_key}/{name}", "rb")
