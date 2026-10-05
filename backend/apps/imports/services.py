"""Validate, apply and undo import batches.

* Validation changes nothing. It works out, row by row, whether the unit is
  new or already known (matched on the serial, else the stock number) and
  what would change.
* Applying runs one transaction per row and is safe to repeat: rows already
  applied are skipped, and importing the same card twice changes nothing.
* Undo reverses a whole batch, except rows whose unit was edited by someone
  after the import (those are left alone and listed).

Blank cells never clear existing data. Values that didn't parse are kept, as
written, in the unit's notes.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, cast

from django.apps import apps as django_apps
from django.contrib.postgres.search import TrigramSimilarity
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile
from django.db import IntegrityError, models, transaction
from django.utils import timezone

from apps.accounts.roles import PRICE_ROLES
from apps.core.context import acting_as
from apps.core.models import AuditLog
from apps.customers.models import Customer
from apps.units import services as unit_services
from apps.units.models import (
    HourMeterReading,
    OwnershipRecord,
    Unit,
    UnitAttachment,
    UnitComponent,
    UnitFile,
    UnitFork,
)

from .models import ImportBatch, ImportFile, ImportRow
from .parsing import ImportFileError, Message, ParsedRow, from_json, parse_row, read_csv

INLINE_MAX_ROWS = 300  # bigger batches run in the background worker
MAX_SCAN_BYTES = unit_services.MAX_UPLOAD_BYTES
MAX_SCANS = 2000
ATTACHMENT_FIELDS = (
    "manufacturer",
    "type",
    "model",
    "serial_number",
    "date_code",
    "hose_reel",
    "internal_hose",
    "reel_number",
    "side",
)
COMPONENT_FIELDS = ("make", "model", "serial_number", "spools")
SUFFIXES = re.compile(r"\b(inc|llc|co|corp|corporation|company|ltd|the)\b")


def can_price(user: Any) -> bool:
    return getattr(user, "role", "") in PRICE_ROLES


def customer_key(name: str) -> str:
    """'Penobscot Paper Co.' and 'penobscot paper company' match."""
    key = name.lower().replace("&", " and ")
    key = re.sub(r"[^a-z0-9 ]", " ", key)
    key = SUFFIXES.sub(" ", key)
    return " ".join(key.split())


def _ref(obj: Any) -> list[str]:
    return [obj._meta.label, str(obj.pk)]


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    return value


# --- Creating batches -------------------------------------------------------------------


def create_csv_batch(upload: UploadedFile, *, filename: str = "") -> ImportBatch:
    data = upload.read()
    try:
        rows, messages = read_csv(data)
    except ImportFileError as exc:
        raise ValidationError({"file": str(exc)}) from exc
    with transaction.atomic():
        batch = ImportBatch(
            source=ImportBatch.Source.CSV,
            filename=(filename or upload.name or "import.csv")[:255],
            file_messages=[m.as_dict() for m in messages],
            row_count=len(rows),
        )
        batch.original.save("source.csv", ContentFile(data), save=False)
        batch.save()
        ImportRow.objects.bulk_create(
            ImportRow(batch=batch, row_number=i + 2, raw=row) for i, row in enumerate(rows)
        )
    validate_batch(batch)
    return batch


def create_json_batch(
    units: list[dict[str, Any]],
    *,
    api_key: Any = None,
    reference: str = "",
    on_existing: str = ImportBatch.OnExisting.UPDATE,
    skip_invalid: bool = False,
) -> ImportBatch:
    with transaction.atomic():
        batch = ImportBatch(
            source=ImportBatch.Source.API,
            api_key=api_key,
            reference=reference[:100],
            on_existing=on_existing,
            skip_invalid=skip_invalid,
            row_count=len(units),
        )
        batch.save()
        ImportRow.objects.bulk_create(
            ImportRow(batch=batch, row_number=i + 1, raw=from_json(item))
            for i, item in enumerate(units)
        )
    validate_batch(batch)
    return batch


def add_scan(batch: ImportBatch, upload: UploadedFile) -> ImportFile:
    """A scanned card for this batch, matched to rows by file name."""
    if batch.status != ImportBatch.Status.DRAFT:
        raise ValidationError({"file": "Scans can only be added before importing."})
    if batch.files.count() >= MAX_SCANS:
        raise ValidationError({"file": f"A batch can have up to {MAX_SCANS:,} scans."})
    name = (upload.name or "").rsplit("/", 1)[-1].rsplit("\\", 1)[-1][:255]
    if not name:
        raise ValidationError({"file": "The file needs a name."})
    if not upload.size:
        raise ValidationError({"file": "The file is empty."})
    if upload.size > MAX_SCAN_BYTES:
        raise ValidationError({"file": "Scans can be up to 25 MB each."})
    data = upload.read()
    inspected = unit_services.inspect_upload(data)
    if batch.files.filter(original_name__iexact=name).exists():
        raise ValidationError({"file": f"“{name}” is already uploaded to this import."})
    scan = ImportFile(
        batch=batch,
        original_name=name,
        content_type=inspected.content_type,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
    )
    scan.file.save(name, ContentFile(data), save=False)
    scan.save()
    return scan


# --- Working out what each row would do ---------------------------------------------------


@dataclass
class Plan:
    action: str  # ImportRow.Plan
    unit: Unit | None = None
    restore: bool = False
    unit_changes: dict[str, Any] = field(default_factory=dict)
    component_changes: dict[str, dict[str, Any]] = field(default_factory=dict)
    replace_forks: bool = False
    replace_attachments: bool = False
    add_hours: bool = False
    customer: Customer | None = None
    new_customer: str = ""
    scans: list[ImportFile] = field(default_factory=list)
    errors: list[Message] = field(default_factory=list)
    warnings: list[Message] = field(default_factory=list)

    @property
    def change_labels(self) -> list[str]:
        labels = [k for k in self.unit_changes if k not in {"needs_review", "review_note"}]
        labels += [f"{kind} {f}" for kind, fields in self.component_changes.items() for f in fields]
        if self.replace_forks:
            labels.append("forks")
        if self.replace_attachments:
            labels.append("attachments")
        if self.add_hours:
            labels.append("hour_meter")
        if self.new_customer:
            labels.append(f"new customer “{self.new_customer}”")
        labels += [f"card scan {s.original_name}" for s in self.scans]
        return labels


class Context:
    """Lookups shared by all rows of a batch (a few queries, not one per row)."""

    def __init__(self, batch: ImportBatch, parsed: Iterable[ParsedRow]) -> None:
        parsed = list(parsed)
        self.batch = batch
        serials = {p.match_serial for p in parsed if p.match_serial}
        stocks = {p.stock_number for p in parsed if p.stock_number}
        self.by_serial = {
            u.serial_normalized: u for u in Unit.all_objects.filter(serial_normalized__in=serials)
        }
        self.by_stock = {u.stock_number: u for u in Unit.objects.filter(stock_number__in=stocks)}
        self.customers: dict[str, Customer] = {}
        for c in Customer.objects.only("id", "name"):
            self.customers.setdefault(customer_key(c.name), c)
        self.new_customers: dict[str, str] = {}  # key -> name, customers this batch will add
        self.scans = {f.original_name.lower(): f for f in batch.files.all()}
        self.seen: dict[str, int] = {}  # unit key -> row number, to catch repeats in the file
        self._similar: dict[str, list[str]] = {}

    def similar_customers(self, name: str) -> list[str]:
        if name not in self._similar:
            self._similar[name] = list(
                Customer.objects.annotate(sim=TrigramSimilarity("name", name))
                .filter(sim__gte=0.45)
                .order_by("-sim")
                .values_list("name", flat=True)[:3]
            )
        return self._similar[name]

    def find_unit(self, p: ParsedRow) -> Unit | None:
        unit = self.by_serial.get(p.match_serial) if p.match_serial else None
        if unit is None and p.stock_number:
            by_stock = self.by_stock.get(p.stock_number)
            # Only a unit without a serial of its own can be matched by stock number.
            if by_stock is not None and (not p.match_serial or not by_stock.serial_normalized):
                unit = by_stock
        return unit


def removed_by_undo(unit: Unit) -> bool:
    """True when the unit was only removed because an import was undone, so a
    corrected re-import may bring it back."""
    return ImportRow.objects.filter(
        unit=unit, result=ImportRow.Result.CREATED, undo_result="Undone"
    ).exists()


def _notes_with(existing: str, lines: list[str]) -> str:
    missing = [line for line in lines if line not in existing]
    if not missing:
        return existing
    block = "\n".join(f"[Import] {line}" for line in missing)
    return f"{existing.rstrip()}\n{block}".strip()


def make_plan(p: ParsedRow, ctx: Context, row_number: int) -> Plan:
    plan = Plan(action=ImportRow.Plan.CREATE, errors=list(p.errors), warnings=list(p.warnings))
    key = p.match_serial or (f"stock:{p.stock_number}" if p.stock_number else "")
    if key:
        if key in ctx.seen:
            plan.errors.append(
                Message(
                    "unit_serial",
                    f"Same unit as row {ctx.seen[key]}; each unit can appear once per file.",
                )
            )
        else:
            ctx.seen[key] = row_number

    unit = ctx.find_unit(p)
    if unit is not None and unit.is_deleted:
        if removed_by_undo(unit):
            plan.restore = True
            plan.warnings.append(
                Message(
                    "unit_serial",
                    "This unit was removed when an earlier import was undone; it will be brought back.",
                )
            )
        else:
            plan.errors.append(
                Message(
                    "unit_serial",
                    f"This serial belongs to a removed unit ({unit}). Restore it on its page first.",
                )
            )
    plan.unit = unit

    # Stock numbers are unique among current units.
    stock = p.stock_number
    if stock:
        holder = ctx.by_stock.get(stock)
        if holder is not None and (unit is None or holder.pk != unit.pk):
            plan.errors.append(
                Message("stock_number", f"Stock number {stock} is already used by {holder}.")
            )

    if unit is not None and ctx.batch.on_existing == ImportBatch.OnExisting.SKIP:
        plan.action = ImportRow.Plan.SKIP
        return plan

    # Scanned cards named on the row.
    for name in p.scans:
        scan = ctx.scans.get(name.lower())
        if scan is None:
            plan.warnings.append(
                Message(
                    "source_image_filename",
                    f"“{name}” wasn't uploaded with this import; add it to the unit later.",
                )
            )
        elif (
            unit is None
            or not unit.files.filter(
                original_name=scan.original_name, size_bytes=scan.size_bytes
            ).exists()
        ):
            plan.scans.append(scan)

    if unit is None:
        _plan_create(p, ctx, plan)
    else:
        _plan_update(p, ctx, plan, unit)

    # Flag the unit for a second look when something needs checking.
    wants_review = p.unit.get("needs_review") is True or (
        bool(plan.warnings) and plan.action in (ImportRow.Plan.CREATE, ImportRow.Plan.UPDATE)
    )
    if wants_review:
        current_flag = (
            unit.needs_review
            if unit is not None and plan.action != ImportRow.Plan.CREATE
            else False
        )
        if not current_flag:
            plan.unit_changes["needs_review"] = True
        current_note = (
            unit.review_note if unit is not None and plan.action != ImportRow.Plan.CREATE else ""
        )
        note = (
            str(p.unit.get("review_note", ""))
            or current_note
            or ("Import warnings: " + "; ".join(w.message for w in plan.warnings))
        )
        if note[:300] != current_note:
            plan.unit_changes["review_note"] = note[:300]
    if plan.action == ImportRow.Plan.UNCHANGED and plan.unit_changes:
        plan.action = ImportRow.Plan.UPDATE
    return plan


def _plan_create(p: ParsedRow, ctx: Context, plan: Plan) -> None:
    plan.action = ImportRow.Plan.CREATE
    values = {k: v for k, v in p.unit.items() if k not in {"needs_review", "review_note"}}
    if p.as_written:
        values["notes"] = _notes_with(str(values.get("notes", "")), p.as_written)
    plan.unit_changes = values
    plan.component_changes = {k: dict(v) for k, v in p.components.items()}
    plan.replace_forks = bool(p.forks)
    plan.replace_attachments = bool(p.attachments)
    plan.add_hours = p.hours is not None
    if p.owner_kind == "customer":
        key = customer_key(p.owner_name)
        existing = ctx.customers.get(key)
        if existing is not None:
            plan.customer = existing
        else:
            plan.new_customer = ctx.new_customers.setdefault(key, p.owner_name)
            similar = [n for n in ctx.similar_customers(p.owner_name) if customer_key(n) != key]
            if similar:
                plan.warnings.append(
                    Message(
                        "customer_name",
                        f"Added as a new customer, but it looks like “{similar[0]}”. Check for a duplicate customer.",
                    )
                )


def _plan_update(p: ParsedRow, ctx: Context, plan: Plan, unit: Unit) -> None:
    changes: dict[str, Any] = {}
    for name, value in p.unit.items():
        if name in {"needs_review", "review_note"}:
            continue
        if getattr(unit, name) != value:
            changes[name] = value
    notes = str(changes.get("notes", unit.notes))
    if p.as_written:
        notes = _notes_with(notes, p.as_written)
    if notes != unit.notes:
        changes["notes"] = notes
    plan.unit_changes = changes

    existing = {c.kind: c for c in unit.components.all()}
    for kind, values in p.components.items():
        current = existing.get(kind)
        diff = {f: v for f, v in values.items() if current is None or getattr(current, f) != v}
        if diff:
            plan.component_changes[kind] = diff

    if p.forks:
        current_forks = Counter((f.dimensions, f.quantity) for f in unit.forks.all())
        plan.replace_forks = current_forks != Counter(p.forks)
    if p.attachments:

        def norm(a: dict[str, Any]) -> tuple[Any, ...]:
            defaults = {"hose_reel": False, "internal_hose": False}
            return tuple(a.get(f, defaults.get(f, "")) for f in ATTACHMENT_FIELDS)

        current_atts = sorted(
            norm({f: getattr(a, f) for f in ATTACHMENT_FIELDS}) for a in unit.attachments.all()
        )
        plan.replace_attachments = current_atts != sorted(norm(a) for a in p.attachments)
    if p.hours is not None:
        plan.add_hours = not unit.hour_readings.filter(hours=p.hours).exists()
        latest = unit.hour_readings.first()
        if plan.add_hours and latest is not None and p.hours < latest.hours:
            plan.warnings.append(
                Message(
                    "hour_meter",
                    f"{p.hours} is lower than the latest reading ({latest.hours} on {latest.reading_date:%b %d, %Y}).",
                )
            )

    owner = unit_services.open_ownership(unit)
    card_owner = customer_key(p.owner_name) if p.owner_kind == "customer" else ""
    if owner is not None:
        current_owner = customer_key(owner.customer.name) if owner.customer else ""
        if p.owner_name and (owner.owner_kind != p.owner_kind or current_owner != card_owner):
            plan.warnings.append(
                Message(
                    "customer_name",
                    f"The card says “{p.owner_name}” but the current owner is {owner.customer or 'our stock'}. Kept the current owner; use Change owner if it changed hands.",
                )
            )

    something = (
        plan.unit_changes
        or plan.component_changes
        or plan.replace_forks
        or plan.replace_attachments
        or plan.add_hours
        or plan.scans
        or plan.restore
    )
    plan.action = ImportRow.Plan.UPDATE if something else ImportRow.Plan.UNCHANGED


# --- Validation -------------------------------------------------------------------------


def _parse_all(batch: ImportBatch) -> list[tuple[ImportRow, ParsedRow]]:
    pricing = can_price(batch.created_by) if batch.created_by_id else False  # type: ignore[attr-defined]
    return [(row, parse_row(row.raw, can_price=pricing)) for row in batch.rows.all()]


def validate_batch(batch: ImportBatch) -> ImportBatch:
    """Check every row against the current data. Changes nothing but the rows' report."""
    pairs = _parse_all(batch)
    ctx = Context(batch, (p for _, p in pairs))
    referenced: set[str] = set()
    for row, parsed in pairs:
        plan = make_plan(parsed, ctx, row.row_number)
        referenced.update(n.lower() for n in parsed.scans)
        row.errors = [m.as_dict() for m in plan.errors]
        row.warnings = [m.as_dict() for m in plan.warnings]
        row.status = (
            ImportRow.Check.ERROR
            if plan.errors
            else ImportRow.Check.WARNING
            if plan.warnings
            else ImportRow.Check.OK
        )
        row.plan = plan.action
        row.changes = plan.change_labels
        row.serial = parsed.serial[:80]
        row.label = parsed.label[:200]
        row.customer_name = parsed.owner_name[:200]
        row.unit = plan.unit
    ImportRow.objects.bulk_update(
        [r for r, _ in pairs],
        [
            "errors",
            "warnings",
            "status",
            "plan",
            "changes",
            "serial",
            "label",
            "customer_name",
            "unit",
            "updated_at",
        ],
    )
    file_messages = [m for m in batch.file_messages if m.get("source") != "scans"]
    for name, scan in ctx.scans.items():
        if name not in referenced:
            file_messages.append(
                {
                    "column": scan.original_name,
                    "message": "No row names this scan in source_image_filename.",
                    "source": "scans",
                }
            )
    batch.file_messages = file_messages
    batch.validated_at = timezone.now()
    batch.counts = summarize(batch)
    batch.save()
    return batch


def summarize(batch: ImportBatch) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row_status, plan, result, undo_result in batch.rows.values_list(
        "status", "plan", "result", "undo_result"
    ):
        counts[row_status] += 1
        if plan:
            counts[f"plan_{plan}"] += 1
        if result:
            counts[f"result_{result}"] += 1
        if undo_result:
            counts["undone" if undo_result == "Undone" else "kept"] += 1
    return dict(counts)


# --- Applying ---------------------------------------------------------------------------


def start_apply(
    batch: ImportBatch, *, on_existing: str | None = None, skip_invalid: bool | None = None
) -> ImportBatch:
    """Re-check, then import now (small batches) or queue it for the worker."""
    with transaction.atomic():
        locked = ImportBatch.objects.select_for_update().get(pk=batch.pk)
        if locked.status not in (ImportBatch.Status.DRAFT, ImportBatch.Status.FAILED):
            raise ValidationError(
                {"status": f"This import is {locked.get_status_display().lower()}."}
            )
        if on_existing is not None:
            locked.on_existing = on_existing
        if skip_invalid is not None:
            locked.skip_invalid = skip_invalid
        locked.save()
    validate_batch(locked)
    errors = locked.counts.get("error", 0)
    if errors and not locked.skip_invalid:
        raise ValidationError(
            {"rows": f"{errors} row(s) have errors. Fix the file, or choose to skip those rows."}
        )
    importable = locked.row_count - errors
    if importable == 0:
        raise ValidationError({"rows": "There's nothing to import."})
    locked.status = ImportBatch.Status.QUEUED
    locked.error = ""
    locked.save()
    if locked.row_count <= INLINE_MAX_ROWS:
        apply_batch(locked.pk)
    else:
        from .tasks import apply_import

        apply_import.configure(queueing_lock=f"import-{locked.pk}").defer(batch_id=str(locked.pk))
    locked.refresh_from_db()
    return locked


def apply_batch(batch_id: Any) -> None:
    """Import every row not imported yet. Safe to run again after a failure."""
    batch = ImportBatch.objects.get(pk=batch_id)
    if batch.status not in (ImportBatch.Status.QUEUED, ImportBatch.Status.IMPORTING):
        return
    batch.status = ImportBatch.Status.IMPORTING
    batch.started_at = batch.started_at or timezone.now()
    batch.save()
    try:
        with acting_as(user=batch.created_by, source="import", request_id=batch.audit_tag):
            pairs = [(r, p) for r, p in _parse_all(batch) if r.applied_at is None]
            ctx = Context(batch, (p for _, p in pairs))
            for row, parsed in pairs:
                apply_row(batch, row, parsed, ctx)
    except Exception as exc:
        batch.status = ImportBatch.Status.FAILED
        batch.error = f"{type(exc).__name__}: {exc}"[:2000]
        batch.counts = summarize(batch)
        batch.save()
        raise
    batch.status = ImportBatch.Status.IMPORTED
    batch.finished_at = timezone.now()
    batch.counts = summarize(batch)
    batch.save()


def apply_row(batch: ImportBatch, row: ImportRow, parsed: ParsedRow, ctx: Context) -> None:
    plan = make_plan(parsed, ctx, row.row_number)
    row.errors = [m.as_dict() for m in plan.errors]
    row.warnings = [m.as_dict() for m in plan.warnings]
    row.applied_at = timezone.now()
    if plan.errors:
        row.status, row.result = ImportRow.Check.ERROR, ImportRow.Result.SKIPPED
        row.save()
        return
    if plan.action == ImportRow.Plan.SKIP:
        row.result = ImportRow.Result.SKIPPED
        row.save()
        return
    if plan.action == ImportRow.Plan.UNCHANGED:
        row.result = ImportRow.Result.UNCHANGED
        row.save()
        return
    try:
        with transaction.atomic():
            undo = (
                _create(plan, parsed, ctx)
                if plan.action == ImportRow.Plan.CREATE
                else _update(plan, parsed, ctx)
            )
    except (IntegrityError, ValidationError) as exc:
        message = (
            "; ".join(exc.messages)
            if isinstance(exc, ValidationError)
            else "The database refused it (probably a duplicate)."
        )
        row.errors = [*row.errors, {"column": "", "message": message}]
        row.status, row.result = ImportRow.Check.ERROR, ImportRow.Result.FAILED
        row.save()
        return
    row.undo = undo
    row.unit_id = undo["unit"]
    row.result = (
        ImportRow.Result.CREATED
        if plan.action == ImportRow.Plan.CREATE
        else ImportRow.Result.UPDATED
    )
    row.changes = plan.change_labels
    row.save()


def _customer_for(plan: Plan, ctx: Context, created: list[list[str]]) -> Customer | None:
    if plan.customer is not None:
        return plan.customer
    if not plan.new_customer:
        return None
    key = customer_key(plan.new_customer)
    existing = ctx.customers.get(key)
    if existing is None:
        existing = Customer(name=plan.new_customer, notes="Added by a unit card import.")
        existing.save()
        ctx.customers[key] = existing
        created.append(_ref(existing))
    return existing


def _children(
    unit: Unit, plan: Plan, parsed: ParsedRow, created: list[list[str]], undo: dict[str, Any]
) -> None:
    existing = {c.kind: c for c in unit.components.all()}
    for kind, values in plan.component_changes.items():
        comp = existing.get(kind)
        if comp is None:
            comp = UnitComponent(unit=unit, kind=kind, **values)
            comp.save()
            created.append(_ref(comp))
        else:
            undo["components_before"][str(comp.pk)] = {f: getattr(comp, f) for f in values}
            for f, v in values.items():
                setattr(comp, f, v)
            comp.save()
    if plan.replace_forks:
        for old in unit.forks.all():
            old.soft_delete()
            undo["removed"].append(_ref(old))
        for dims, qty in parsed.forks:
            fork = UnitFork(unit=unit, dimensions=dims, quantity=qty)
            fork.save()
            created.append(_ref(fork))
    if plan.replace_attachments:
        for old_att in unit.attachments.all():
            old_att.soft_delete()
            undo["removed"].append(_ref(old_att))
        for values in parsed.attachments:
            att = UnitAttachment(unit=unit, **values)
            att.save()
            created.append(_ref(att))
    if plan.add_hours and parsed.hours is not None:
        reading = HourMeterReading(
            unit=unit,
            hours=parsed.hours,
            reading_date=unit.card_date or timezone.localdate(),
            source=HourMeterReading.Source.CARD,
            note="From a unit card import",
        )
        reading.save()
        created.append(_ref(reading))
    for scan in plan.scans:
        with scan.file.open("rb") as fh:
            upload = ContentFile(fh.read(), name=scan.original_name)
        record = unit_services.add_file(
            unit, upload, kind=UnitFile.Kind.SCANNED_CARD, caption="Original unit card"
        )
        created.append(_ref(record))


def _create(plan: Plan, parsed: ParsedRow, ctx: Context) -> dict[str, Any]:
    created: list[list[str]] = []
    undo: dict[str, Any] = {
        "created": created,
        "removed": [],
        "before": {},
        "components_before": {},
    }
    customer = _customer_for(plan, ctx, created)
    unit = Unit(**plan.unit_changes)
    unit.save()
    created.insert(0, _ref(unit))
    ownership = OwnershipRecord(
        unit=unit,
        owner_kind=OwnershipRecord.OwnerKind.CUSTOMER
        if customer
        else OwnershipRecord.OwnerKind.DEALER,
        customer=customer,
        start_date=unit.card_date or timezone.localdate(),
        note="From a unit card import",
    )
    ownership.save()
    created.append(_ref(ownership))
    _children(unit, plan, parsed, created, undo)
    ctx.by_serial[unit.serial_normalized] = unit
    if unit.stock_number:
        ctx.by_stock[unit.stock_number] = unit
    undo["unit"] = str(unit.pk)
    return undo


def _update(plan: Plan, parsed: ParsedRow, ctx: Context) -> dict[str, Any]:
    assert plan.unit is not None
    unit = Unit.all_objects.select_for_update().get(pk=plan.unit.pk)
    created: list[list[str]] = []
    undo: dict[str, Any] = {
        "created": created,
        "removed": [],
        "before": {k: _jsonable(getattr(unit, k)) for k in plan.unit_changes},
        "components_before": {},
        "restored": plan.restore,
    }
    if plan.restore:
        unit.restore()
    for name, value in plan.unit_changes.items():
        setattr(unit, name, value)
    if plan.unit_changes:
        unit.save()
    if plan.restore and unit_services.open_ownership(unit) is None:
        customer = _customer_for(plan, ctx, created) if parsed.owner_kind == "customer" else None
        if customer is None and parsed.owner_kind == "customer":
            customer = ctx.customers.get(customer_key(parsed.owner_name))
        ownership = OwnershipRecord(
            unit=unit,
            owner_kind=OwnershipRecord.OwnerKind.CUSTOMER
            if customer
            else OwnershipRecord.OwnerKind.DEALER,
            customer=customer,
            start_date=unit.card_date or timezone.localdate(),
            note="From a unit card import",
        )
        ownership.save()
        created.append(_ref(ownership))
    _children(unit, plan, parsed, created, undo)
    undo["components_before"] = {
        k: {f: _jsonable(v) for f, v in vals.items()}
        for k, vals in undo["components_before"].items()
    }
    undo["unit"] = str(unit.pk)
    return undo


# --- Undo -------------------------------------------------------------------------------


def start_undo(batch: ImportBatch, user: Any) -> ImportBatch:
    with transaction.atomic():
        locked = ImportBatch.objects.select_for_update().get(pk=batch.pk)
        if locked.status not in (ImportBatch.Status.IMPORTED, ImportBatch.Status.FAILED):
            raise ValidationError({"status": "Only an imported batch can be undone."})
        locked.status = ImportBatch.Status.UNDOING
        locked.undone_by = user
        locked.save()
    if locked.row_count <= INLINE_MAX_ROWS:
        undo_batch(locked.pk)
    else:
        from .tasks import undo_import

        undo_import.configure(queueing_lock=f"undo-{locked.pk}").defer(batch_id=str(locked.pk))
    locked.refresh_from_db()
    return locked


def _model_object(ref: list[str]) -> Any:
    model = django_apps.get_model(ref[0])
    return model.all_objects.filter(pk=ref[1]).first()


def _touched_since(row: ImportRow, batch: ImportBatch) -> bool:
    """Has anyone (other than this import) changed the unit or its parts since?"""
    unit_id = row.undo.get("unit")
    ids = {str(unit_id)} | {ref[1] for ref in row.undo.get("created", [])}
    ids |= set(row.undo.get("components_before", {}))
    ids |= {ref[1] for ref in row.undo.get("removed", [])}
    if unit_id:
        ids |= {
            str(pk)
            for pk in UnitComponent.all_objects.filter(unit_id=unit_id).values_list("pk", flat=True)
        }
        ids |= {
            str(pk)
            for pk in UnitFile.all_objects.filter(unit_id=unit_id).values_list("pk", flat=True)
        }
        ids |= {
            str(pk)
            for pk in HourMeterReading.all_objects.filter(unit_id=unit_id).values_list(
                "pk", flat=True
            )
        }
        ids |= {
            str(pk)
            for pk in OwnershipRecord.all_objects.filter(unit_id=unit_id).values_list(
                "pk", flat=True
            )
        }
    customer_ids = {ref[1] for ref in row.undo.get("created", []) if ref[0] == "customers.Customer"}
    return (
        AuditLog.objects.filter(object_id__in=ids - customer_ids, at__gt=row.applied_at)
        .exclude(request_id__in=[batch.audit_tag, f"undo-{batch.pk}"])
        .exists()
    )


def undo_batch(batch_id: Any) -> None:
    batch = ImportBatch.objects.get(pk=batch_id)
    if batch.status != ImportBatch.Status.UNDOING:
        return
    with acting_as(user=batch.undone_by, source="import", request_id=f"undo-{batch.pk}"):
        rows = batch.rows.filter(
            result__in=[ImportRow.Result.CREATED, ImportRow.Result.UPDATED], undo_result=""
        ).order_by("-row_number")
        customers: list[list[str]] = []
        for row in rows:
            if _touched_since(row, batch):
                row.undo_result = "Kept: someone changed this unit after the import"
                row.save()
                continue
            with transaction.atomic():
                _undo_row(row, customers)
                row.undo_result = "Undone"
                row.save()
        for ref in customers:
            customer = _model_object(ref)
            if customer is None or customer.is_deleted:
                continue
            in_use = OwnershipRecord.objects.filter(customer=customer).exists()
            edited = (
                AuditLog.objects.filter(object_id=str(customer.pk))
                .exclude(request_id__in=[batch.audit_tag, f"undo-{batch.pk}"])
                .exists()
            )
            if (
                not in_use
                and not edited
                and not customer.contacts.exists()
                and not customer.addresses.exists()
            ):
                customer.soft_delete()
    batch.status = ImportBatch.Status.UNDONE
    batch.undone_at = timezone.now()
    batch.counts = summarize(batch)
    batch.save()


def _undo_row(row: ImportRow, customers: list[list[str]]) -> None:
    undo = row.undo
    unit = Unit.all_objects.select_for_update().get(pk=undo["unit"])
    for ref in reversed(undo.get("created", [])):
        if ref[0] == "customers.Customer":
            customers.append(ref)
            continue
        obj = _model_object(ref)
        if obj is not None and obj.pk != unit.pk:
            obj.soft_delete()
    for ref in undo.get("removed", []):
        obj = _model_object(ref)
        if obj is not None:
            obj.restore()
    for pk, values in undo.get("components_before", {}).items():
        comp = UnitComponent.all_objects.get(pk=pk)
        for f, v in values.items():
            setattr(comp, f, v)
        comp.save()
    if row.result == ImportRow.Result.CREATED:
        unit.soft_delete()
        return
    before = undo.get("before", {})
    if before:
        for name, value in before.items():
            model_field = cast("models.Field[Any, Any]", Unit._meta.get_field(name))
            setattr(unit, name, model_field.to_python(value))
        unit.save()
    if undo.get("restored"):
        unit.soft_delete()


def discard(batch: ImportBatch) -> ImportBatch:
    if batch.status != ImportBatch.Status.DRAFT:
        raise ValidationError({"status": "Only an import that hasn't run can be discarded."})
    batch.status = ImportBatch.Status.DISCARDED
    batch.save()
    return batch
