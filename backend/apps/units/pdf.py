"""Unit spec sheet: the card's details in a form a customer can be handed.
Internal notes and cost are never printed; the asking price only on request
(and only for admin and sales)."""

from __future__ import annotations

import io
from typing import Any

from reportlab.lib.units import inch
from reportlab.platypus import Image, Spacer, Table, TableStyle

from apps.core.pdf import LINE, WIDTH, date_text, facts, grid, number, p, render

from . import services
from .models import Unit, UnitFile


def _photo(unit: Unit) -> Any:
    photo = (
        unit.files.filter(kind=UnitFile.Kind.PHOTO).order_by("-is_primary", "sort_order").first()
    )
    if photo is None:
        return p("No photo yet", "small")
    field = photo.thumbnail or photo.file
    try:
        with field.open("rb") as fh:
            data = io.BytesIO(fh.read())
    except (FileNotFoundError, OSError):
        return p("Photo unavailable", "small")
    image = Image(data)
    scale = min(3.2 * inch / image.imageWidth, 2.6 * inch / image.imageHeight)
    image.drawWidth, image.drawHeight = image.imageWidth * scale, image.imageHeight * scale
    return image


def spec_sheet_pdf(unit: Unit, *, price: bool = False) -> bytes:
    title = " ".join(x for x in [str(unit.year or ""), unit.make, unit.model] if x) or "Forklift"
    latest = unit.hour_readings.first()
    owner = services.open_ownership(unit)
    key = facts(
        [
            ("Hours", f"{number(latest.hours)} h" if latest else ""),
            ("Capacity", f"{unit.capacity_lbs:,} lb" if unit.capacity_lbs else ""),
            ("Fuel", unit.get_fuel_type_display() if unit.fuel_type else ""),
            (
                "Max lift height",
                f"{unit.mast_lift_height_in} in" if unit.mast_lift_height_in else "",
            ),
            (
                "Lowered height",
                f"{unit.mast_lowered_height_in} in" if unit.mast_lowered_height_in else "",
            ),
            ("Mast", " ".join(x for x in [unit.mast_make, unit.mast_type, unit.mast_size] if x)),
            (
                "Tires",
                ", ".join(
                    x
                    for x in [
                        unit.tire_type,
                        unit.tire_drive_size and f"drive {unit.tire_drive_size}",
                        unit.tire_steer_size and f"steer {unit.tire_steer_size}",
                    ]
                    if x
                ),
            ),
            ("Forks", "; ".join(f"{f.quantity} \u00d7 {f.dimensions}" for f in unit.forks.all())),
        ],
        columns=2,
        width=WIDTH - 3.4 * inch,
    )
    top = Table([[_photo(unit), key]], colWidths=[3.4 * inch, WIDTH - 3.4 * inch])
    top.setStyle(
        TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)])
    )

    story: list[Any] = [
        p(title, "title"),
        p(
            " · ".join(
                x
                for x in [
                    unit.get_condition_display(),
                    f"Serial {unit.serial_number}" if unit.serial_number else "",
                    f"Stock # {unit.stock_number}" if unit.stock_number else "",
                    unit.get_stock_status_display()
                    if unit.stock_status and unit.stock_status != "sold"
                    else "",
                ]
                if x
            ),
            "subtitle",
        ),
        Spacer(1, 10),
        top,
    ]
    if price and unit.asking_price is not None:
        banner = Table(
            [
                [
                    p("ASKING PRICE", "label"),
                    p(f"<b>${unit.asking_price:,.0f}</b>", "title", raw=True),
                ]
            ],
            colWidths=[1.4 * inch, WIDTH - 1.4 * inch],
        )
        banner.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.75, LINE),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        story += [Spacer(1, 8), banner]

    components = list(unit.components.all())
    if components:
        story += [
            p("Components", "h2"),
            grid(
                ["Component", "Make", "Model", "Serial"],
                [
                    [
                        c.get_kind_display() + (f" ({c.spools})" if c.spools else ""),
                        c.make,
                        c.model,
                        c.serial_number,
                    ]
                    for c in components
                ],
                [0.28, 0.22, 0.25, 0.25],
            ),
        ]
    story += [
        p("Mast, carriage and tilt", "h2"),
        facts(
            [
                ("Mast make", unit.mast_make),
                ("Mast type", unit.mast_type),
                ("Mast size", unit.mast_size),
                ("Lift cylinder #", unit.lift_cylinder_number),
                ("Carriage", unit.carriage),
                (
                    "Backrest",
                    " \u00d7 ".join(x for x in [unit.backrest_height, unit.backrest_width] if x),
                ),
                (
                    "Tilt fwd / back",
                    " / ".join(
                        f"{d}°"
                        for d in [unit.tilt_forward_deg, unit.tilt_back_deg]
                        if d is not None
                    ),
                ),
                ("Tilt reference", unit.tilt_reference),
            ]
        ),
    ]
    if unit.tire_notes:
        story += [p(f"Tires: {unit.tire_notes}", "small")]
    electrics = [
        ("Battery", " ".join(x for x in [unit.battery_make, unit.battery_model] if x)),
        ("Battery serial", unit.battery_serial),
        (
            "Volts / Ah",
            " / ".join(str(x) for x in [unit.battery_volts, unit.battery_amp_hours] if x),
        ),
        ("Battery size", unit.battery_size),
        ("Battery weight", f"{unit.battery_weight_lbs:,} lb" if unit.battery_weight_lbs else ""),
        ("Charger", " ".join(x for x in [unit.charger_make, unit.charger_model] if x)),
        ("Charger serial", unit.charger_serial),
    ]
    if any(v for _, v in electrics):
        story += [p("Battery and charger", "h2"), facts(electrics)]
    attachments = list(unit.attachments.all())
    if attachments:
        story += [
            p("Attachments", "h2"),
            grid(
                ["Manufacturer", "Type", "Model", "Serial", "Details"],
                [
                    [
                        a.manufacturer,
                        a.type,
                        a.model,
                        a.serial_number,
                        ", ".join(
                            x
                            for x in [
                                a.date_code and f"date code {a.date_code}",
                                "hose reel" if a.hose_reel else "",
                                "internal hose" if a.internal_hose else "",
                                a.reel_number and f"reel # {a.reel_number}",
                                a.get_side_display() if a.side else "",
                            ]
                            if x
                        ),
                    ]
                    for a in attachments
                ],
                [0.18, 0.16, 0.22, 0.16, 0.28],
            ),
        ]
    if unit.special_equipment or unit.field_modifications:
        story += [
            p("Equipment and modifications", "h2"),
            facts(
                [
                    ("Special equipment", unit.special_equipment),
                    ("Field modifications", unit.field_modifications),
                ],
                columns=2,
            ),
        ]
    if owner is not None and owner.owner_kind == "customer" and owner.customer:
        story += [Spacer(1, 10), p(f"Owner: {owner.customer.name}", "small")]
    story += [
        Spacer(1, 10),
        p(
            f"Specifications from our records as of {date_text(unit.updated_at)}. "
            "Subject to prior sale.",
            "small",
        ),
    ]
    label = f"Spec sheet · {title}" + (f" · {unit.serial_number}" if unit.serial_number else "")
    return render(story, title=f"{title} spec sheet", label=label)
