"""Work order printout: for the shop floor, the field, and the customer's
signature. Empty boxes and lines are left to write on."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from reportlab.lib.units import inch
from reportlab.platypus import KeepTogether, Spacer, Table, TableStyle

from apps.core.pdf import LINE, WIDTH, box, date_text, facts, grid, number, p, render, text
from apps.units import services as unit_services

from .models import WorkOrder


def _signatures() -> Table:
    cells = [[p("Technician", "label"), p("Customer", "label"), p("Date", "label")]]
    table = Table(
        [[""] * 3, *cells],
        colWidths=[WIDTH * 0.4, WIDTH * 0.4, WIDTH * 0.2],
        rowHeights=[0.45 * inch, None],
    )
    table.setStyle(
        TableStyle(
            [
                ("LINEABOVE", (0, 1), (-1, 1), 0.75, LINE),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 14),
            ]
        )
    )
    return table


def work_order_pdf(wo: WorkOrder) -> bytes:
    unit = wo.unit
    customer = wo.customer
    reading = (
        wo.hour_reading
        if wo.hour_reading is not None and wo.hour_reading.deleted_at is None
        else None
    )
    latest = unit.hour_readings.first()
    hours = reading.hours if reading else (latest.hours if latest else None)
    labor = list(wo.labor.select_related("mechanic"))
    total = sum((line.hours for line in labor), Decimal("0"))
    open_job = wo.status not in (WorkOrder.Status.COMPLETED, WorkOrder.Status.CANCELLED)
    owner = unit_services.open_ownership(unit)
    contact_phone = customer.phone if customer else ""
    primary = customer.contacts.filter(is_primary=True).first() if customer else None

    story: list[Any] = [
        p(f"Work order {wo.number}", "title"),
        p(
            " · ".join(
                x
                for x in [
                    wo.get_status_display(),
                    wo.get_kind_display()
                    + (f" ({wo.maintenance_plan.name})" if wo.maintenance_plan else ""),
                    wo.get_location_display(),
                    f"Opened {date_text(wo.opened_on)}",
                    f"Due {date_text(wo.due_on)}" if wo.due_on else "",
                    f"Completed {date_text(wo.completed_at)}" if wo.completed_at else "",
                ]
                if x
            ),
            "subtitle",
        ),
        Spacer(1, 8),
        p("Customer", "h2"),
        facts(
            [
                ("Customer", customer.name if customer else "Maine Material Handling stock"),
                ("Account", customer.account_number if customer else ""),
                ("Phone", contact_phone),
                (
                    "Main contact",
                    f"{primary.first_name} {primary.last_name}".strip() if primary else "",
                ),
                ("On site", wo.contact),
                ("Customer PO", wo.customer_po),
            ],
            columns=3,
        ),
        p("Unit", "h2"),
        facts(
            [
                ("Make / model", " ".join(x for x in [unit.make, unit.model] if x)),
                ("Serial", unit.serial_number),
                ("Stock #", unit.stock_number),
                ("Year", unit.year),
                ("Hour meter", f"{number(hours)} h" if hours is not None else ""),
                ("Fuel", unit.get_fuel_type_display() if unit.fuel_type else ""),
                ("Capacity", f"{unit.capacity_lbs:,} lb" if unit.capacity_lbs else ""),
                (
                    "Owner",
                    owner.customer.name
                    if owner and owner.customer
                    else ("Our stock" if owner else ""),
                ),
            ],
            columns=4,
        ),
        Spacer(1, 6),
        box("Complaint", wo.complaint, 0.7 * inch),
        Spacer(1, 6),
        box("Cause", wo.cause),
        Spacer(1, 6),
        box("Correction", wo.correction, 1.1 * inch),
        p("Labor", "h2"),
        grid(
            ["Date", "Technician", "Hours", "Work done"],
            [
                [
                    date_text(line.work_date),
                    line.mechanic.full_name or line.mechanic.email,
                    number(line.hours),
                    line.description,
                ]
                for line in labor
            ],
            [0.16, 0.24, 0.1, 0.5],
            blank_rows=4 if open_job else 0,
        ),
        p(f"Total labor: <b>{number(total)} h</b>" if labor else "", "right", raw=True),
        p("Parts used", "h2"),
        grid(
            ["Part number", "Description", "Qty"],
            [],
            [0.25, 0.63, 0.12],
            blank_rows=5 if open_job else 1,
        ),
    ]
    if wo.hold_reason:
        story.insert(2, p(f"<b>On hold:</b> {text(wo.hold_reason)}", "body", raw=True))
    if wo.notes.strip():
        story += [Spacer(1, 6), box("Notes", wo.notes, 0.4 * inch)]
    story += [
        Spacer(1, 18),
        KeepTogether(
            [p("I confirm the work above was done.", "small"), Spacer(1, 4), _signatures()]
        ),
    ]
    return render(story, title=f"Work order {wo.number}", label=f"Work order {wo.number}")
