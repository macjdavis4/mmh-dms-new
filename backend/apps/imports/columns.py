"""The import format: one CSV row (or JSON object) per unit card.

This list is the single source of truth. The CSV template, the sample file,
the JSON Schema and docs/IMPORT_FORMAT.md are all generated from it
(`manage.py write_import_docs`), and a test fails if they drift.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Kind = Literal["text", "int", "decimal", "money", "date", "choice", "bool", "hours", "forks"]


@dataclass(frozen=True)
class Column:
    name: str
    kind: Kind
    target: str  # where the value goes: "unit.<field>", "component.<kind>.<field>", ...
    help: str
    section: str
    max_length: int = 0
    choices: dict[str, str] = field(default_factory=dict)  # accepted input -> stored value
    minimum: int | None = None
    maximum: int | None = None


COMPONENTS: list[tuple[str, str, str]] = [
    # (column prefix, component kind, label)
    ("engine", "engine", "Engine"),
    ("alternator", "alternator", "Generator / alternator"),
    ("controller", "controller", "Electrical controller"),
    ("ignition", "ignition", "Ignition system"),
    ("fuel_system", "fuel_system", "Fuel system"),
    ("hydraulic_pump", "hydraulic_pump", "Hydraulic pump"),
    ("control_valve", "control_valve", "Control valve"),
    ("transmission", "transmission", "Transmission"),
]
MAX_ATTACHMENTS = 4

CONDITION = {"new": "new", "used": "used", "n": "new", "u": "used"}
FUEL = {
    "lpg": "lpg",
    "lp": "lpg",
    "propane": "lpg",
    "gas": "gasoline",
    "gasoline": "gasoline",
    "diesel": "diesel",
    "dual": "dual",
    "dual fuel": "dual",
    "lpg/gas": "dual",
    "electric": "electric",
    "battery": "electric",
    "other": "other",
}
STOCK_STATUS = {
    "available": "available",
    "on hold": "on_hold",
    "on_hold": "on_hold",
    "hold": "on_hold",
    "in prep": "in_prep",
    "in_prep": "in_prep",
    "prep": "in_prep",
    "sold": "sold",
}
OWNER = {
    "customer": "customer",
    "stock": "dealer",
    "our stock": "dealer",
    "dealer": "dealer",
    "mmh": "dealer",
}
SPOOLS = {"2sp": "2SP", "3sp": "3SP", "4sp": "4SP", "2": "2SP", "3": "3SP", "4": "4SP"}
SIDE = {"lh": "LH", "rh": "RH", "left": "LH", "right": "RH"}


def _columns() -> list[Column]:
    cols: list[Column] = []

    def add(name: str, kind: Kind, target: str, help_text: str, section: str, **kw: object) -> None:
        cols.append(Column(name, kind, target, help_text, section, **kw))  # type: ignore[arg-type]

    s = "Card header"
    add(
        "customer_name",
        "text",
        "owner.name",
        "Customer as written on the card. Matched to an existing customer by name; a new customer is added if there's no match.",
        s,
        max_length=200,
    )
    add("card_date", "date", "unit.card_date", "Date on the card. 2024-03-12 or 3/12/2024.", s)
    add("mechanic", "text", "unit.mechanic", "Mechanic as written on the card.", s, max_length=100)
    add(
        "work_order_number",
        "text",
        "unit.work_order_number",
        "Work order number on the card.",
        s,
        max_length=40,
    )
    add(
        "condition",
        "choice",
        "unit.condition",
        "new or used. Blank means used.",
        s,
        choices=CONDITION,
    )
    add(
        "hour_meter",
        "hours",
        "hours",
        "Hour meter reading on the card. Saved as a dated reading (card date, or the import date).",
        s,
    )

    s = "Unit"
    add("unit_make", "text", "unit.make", "e.g. Hyundai, Doosan.", s, max_length=60)
    add("unit_model", "text", "unit.model", "e.g. 35LN-9A.", s, max_length=80)
    add(
        "unit_serial",
        "text",
        "unit.serial_number",
        "Unit serial number. Used to recognise the unit when the same card is imported again.",
        s,
        max_length=80,
    )
    add(
        "stock_number",
        "text",
        "unit.stock_number",
        "Our stock number, if it has one. Used to recognise the unit when there's no serial.",
        s,
        max_length=40,
    )
    add("year", "int", "unit.year", "Model year, e.g. 2019.", s, minimum=1940, maximum=2100)
    add(
        "fuel_type",
        "choice",
        "unit.fuel_type",
        "lpg, gasoline, diesel, dual, electric or other.",
        s,
        choices=FUEL,
    )
    add(
        "capacity_lbs",
        "int",
        "unit.capacity_lbs",
        "Rated capacity in pounds, e.g. 5000.",
        s,
        minimum=0,
        maximum=200000,
    )

    s = "Components"
    for prefix, kind, label in COMPONENTS:
        add(f"{prefix}_make", "text", f"component.{kind}.make", f"{label} make.", s, max_length=60)
        add(
            f"{prefix}_model",
            "text",
            f"component.{kind}.model",
            f"{label} model.",
            s,
            max_length=80,
        )
        add(
            f"{prefix}_serial",
            "text",
            f"component.{kind}.serial_number",
            f"{label} serial.",
            s,
            max_length=80,
        )
        if kind == "control_valve":
            add(
                "control_valve_spools",
                "choice",
                "component.control_valve.spools",
                "2SP, 3SP or 4SP.",
                s,
                choices=SPOOLS,
            )

    s = "Mast, carriage and tilt"
    add("mast_make", "text", "unit.mast_make", "Mast manufacturer, e.g. Hyundai.", s, max_length=60)
    add("mast_type", "text", "unit.mast_type", "e.g. TF470.", s, max_length=60)
    add("mast_size", "text", "unit.mast_size", "As written, e.g. 69MN-T4715.", s, max_length=60)
    add(
        "mast_lift_height_in",
        "int",
        "unit.mast_lift_height_in",
        "Maximum fork height in inches.",
        s,
        minimum=0,
        maximum=1200,
    )
    add(
        "mast_lowered_height_in",
        "int",
        "unit.mast_lowered_height_in",
        "Lowered (collapsed) height in inches.",
        s,
        minimum=0,
        maximum=1200,
    )
    add(
        "lift_cylinder",
        "text",
        "unit.lift_cylinder_number",
        "Lift cylinder number, as written.",
        s,
        max_length=100,
    )
    add(
        "forks",
        "forks",
        "forks",
        "Fork dimensions as written, e.g. 1.75 x 4 x 48 STD. Several sets: separate with ; (the same size twice counts as 2).",
        s,
    )
    add("carriage", "text", "unit.carriage", "Carriage, as written.", s, max_length=100)
    add(
        "backrest_height",
        "text",
        "unit.backrest_height",
        "Backrest height, as written.",
        s,
        max_length=40,
    )
    add(
        "backrest_width",
        "text",
        "unit.backrest_width",
        "Backrest width, as written.",
        s,
        max_length=40,
    )
    add(
        "tilt_forward_deg",
        "decimal",
        "unit.tilt_forward_deg",
        "Forward tilt in degrees, e.g. 6.",
        s,
        minimum=0,
        maximum=90,
    )
    add(
        "tilt_back_deg",
        "decimal",
        "unit.tilt_back_deg",
        "Back tilt in degrees, e.g. 10.",
        s,
        minimum=0,
        maximum=90,
    )
    add("tilt_reference", "text", "unit.tilt_reference", "Tilt reference number.", s, max_length=60)

    s = "Tires"
    add("tire_type", "text", "unit.tire_type", "e.g. solid, pneumatic, cushion.", s, max_length=40)
    add("tire_drive_size", "text", "unit.tire_drive_size", "e.g. 8.15-15.", s, max_length=40)
    add("tire_steer_size", "text", "unit.tire_steer_size", "e.g. 6.50-10.", s, max_length=40)
    add("tire_notes", "text", "unit.tire_notes", "Anything else, e.g. rim size.", s, max_length=200)

    s = "Battery and charger"
    add("battery_mfg", "text", "unit.battery_make", "Battery manufacturer.", s, max_length=60)
    add("battery_model", "text", "unit.battery_model", "Battery model.", s, max_length=60)
    add("battery_serial", "text", "unit.battery_serial", "Battery serial.", s, max_length=60)
    add("battery_volts", "int", "unit.battery_volts", "e.g. 36 or 48.", s, minimum=0, maximum=1000)
    add(
        "battery_amp_hours",
        "int",
        "unit.battery_amp_hours",
        "Amp-hours, e.g. 750.",
        s,
        minimum=0,
        maximum=100000,
    )
    add("battery_size", "text", "unit.battery_size", "W x L x H as written.", s, max_length=60)
    add(
        "battery_weight_lbs",
        "int",
        "unit.battery_weight_lbs",
        "Battery weight in pounds.",
        s,
        minimum=0,
        maximum=20000,
    )
    add("charger_make", "text", "unit.charger_make", "Charger make.", s, max_length=60)
    add("charger_model", "text", "unit.charger_model", "Charger model.", s, max_length=60)
    add("charger_serial", "text", "unit.charger_serial", "Charger serial.", s, max_length=60)

    s = "Attachments"
    for n in range(1, MAX_ATTACHMENTS + 1):
        p = f"attachment_{n}"
        add(
            f"{p}_mfg",
            "text",
            f"attachment.{n}.manufacturer",
            f"Attachment {n} manufacturer, e.g. Cascade.",
            s,
            max_length=60,
        )
        add(
            f"{p}_type",
            "text",
            f"attachment.{n}.type",
            f"Attachment {n} type, e.g. SS/FP (side shift / fork positioner).",
            s,
            max_length=80,
        )
        add(
            f"{p}_model",
            "text",
            f"attachment.{n}.model",
            f"Attachment {n} model.",
            s,
            max_length=80,
        )
        add(
            f"{p}_serial",
            "text",
            f"attachment.{n}.serial_number",
            f"Attachment {n} serial.",
            s,
            max_length=80,
        )
        add(
            f"{p}_date_code",
            "text",
            f"attachment.{n}.date_code",
            f"Attachment {n} date code.",
            s,
            max_length=40,
        )
        add(f"{p}_hose_reel", "bool", f"attachment.{n}.hose_reel", "yes or no.", s)
        add(f"{p}_internal_hose", "bool", f"attachment.{n}.internal_hose", "yes or no.", s)
        add(
            f"{p}_reel_number",
            "text",
            f"attachment.{n}.reel_number",
            "Reel number.",
            s,
            max_length=60,
        )
        add(f"{p}_side", "choice", f"attachment.{n}.side", "LH or RH.", s, choices=SIDE)

    s = "Notes"
    add(
        "special_equipment",
        "text",
        "unit.special_equipment",
        "Special equipment, as written.",
        s,
        max_length=5000,
    )
    add(
        "field_modifications",
        "text",
        "unit.field_modifications",
        "Field modifications, as written.",
        s,
        max_length=5000,
    )
    add("notes", "text", "unit.notes", "Any other notes.", s, max_length=5000)

    s = "Stock and pricing"
    add(
        "owner",
        "choice",
        "owner.kind",
        "customer or stock. Blank: customer if customer_name is filled in, otherwise our stock.",
        s,
        choices=OWNER,
    )
    add(
        "stock_status",
        "choice",
        "unit.stock_status",
        "For our stock: available, on hold, in prep or sold.",
        s,
        choices=STOCK_STATUS,
    )
    add("cost", "money", "unit.cost", "What we paid. Admin and sales only; ignored for others.", s)
    add("asking_price", "money", "unit.asking_price", "Asking price. Admin and sales only.", s)
    add("sale_price", "money", "unit.sale_price", "Sold for. Admin and sales only.", s)

    s = "Review and scans"
    add("needs_review", "bool", "unit.needs_review", "yes to flag the card for a second look.", s)
    add("review_note", "text", "unit.review_note", "Why it needs a second look.", s, max_length=300)
    add(
        "source_image_filename",
        "text",
        "scan",
        "File name of the scanned card uploaded with this import, e.g. card-0412.jpg. Several: separate with ;.",
        s,
        max_length=500,
    )
    return cols


COLUMNS: list[Column] = _columns()
BY_NAME: dict[str, Column] = {c.name: c for c in COLUMNS}

# Header spellings people are likely to type, mapped to the real column.
ALIASES: dict[str, str] = {
    "customer": "customer_name",
    "date": "card_date",
    "work_order": "work_order_number",
    "wo": "work_order_number",
    "hours": "hour_meter",
    "hour_meter_reading": "hour_meter",
    "make": "unit_make",
    "model": "unit_model",
    "serial": "unit_serial",
    "serial_number": "unit_serial",
    "unit_serial_number": "unit_serial",
    "fuel": "fuel_type",
    "capacity": "capacity_lbs",
    "lift_cylinder_number": "lift_cylinder",
    "battery_make": "battery_mfg",
    "battery_manufacturer": "battery_mfg",
    "mast_manufacturer": "mast_make",
    "status": "stock_status",
    "image": "source_image_filename",
    "scan": "source_image_filename",
    "image_filename": "source_image_filename",
    **{
        f"attachment_{n}_manufacturer": f"attachment_{n}_mfg" for n in range(1, MAX_ATTACHMENTS + 1)
    },
}

PRICE_COLUMNS = {"cost", "asking_price", "sale_price"}


def normalize_header(header: str) -> str:
    h = header.strip().lstrip("﻿").lower()
    for ch in " -./":
        h = h.replace(ch, "_")
    while "__" in h:
        h = h.replace("__", "_")
    h = h.strip("_")
    return ALIASES.get(h, h)


# Example rows, using values seen on real cards. Used for the sample CSV and the docs.
SAMPLE_ROWS: list[dict[str, str]] = [
    {
        "customer_name": "Penobscot Paper Co.",
        "card_date": "2024-03-12",
        "mechanic": "Sam W.",
        "work_order_number": "WO-4471",
        "condition": "used",
        "hour_meter": "10288",
        "unit_make": "Doosan",
        "unit_model": "G25N-7",
        "unit_serial": "FGA25-71234",
        "year": "2016",
        "fuel_type": "lpg",
        "capacity_lbs": "5000",
        "engine_make": "Nissan",
        "engine_model": "K25",
        "engine_serial": "K25-118734",
        "hydraulic_pump_make": "Kayaba",
        "control_valve_make": "Hydrocontrol",
        "control_valve_spools": "3SP",
        "mast_make": "Doosan",
        "mast_type": "TF470",
        "mast_size": "69MN-T4715",
        "mast_lift_height_in": "188",
        "forks": "1.75 x 4 x 48 STD; 1.75 x 4 x 48 STD",
        "tilt_forward_deg": "6",
        "tilt_back_deg": "10",
        "tire_type": "solid",
        "tire_drive_size": "8.15-15",
        "tire_steer_size": "6.50-10",
        "tire_notes": "7.00 rim on drives",
        "attachment_1_mfg": "Cascade",
        "attachment_1_type": "SS/FP",
        "attachment_1_model": "65K-FPS-8169-C",
        "attachment_1_serial": "CS-77120",
        "attachment_1_hose_reel": "yes",
        "attachment_1_side": "LH",
        "special_equipment": "Blue spot light",
        "notes": "Card is water stained at the bottom.",
        "source_image_filename": "card-0001.jpg",
    },
    {
        "customer_name": "",
        "card_date": "3/2/2025",
        "condition": "new",
        "hour_meter": "4.5",
        "unit_make": "Hyundai",
        "unit_model": "35LN-9A",
        "unit_serial": "HHKHHN04P00999",
        "stock_number": "MMH-2410",
        "year": "2025",
        "fuel_type": "lpg",
        "capacity_lbs": "7000",
        "engine_make": "Hyundai",
        "engine_model": "L4KB",
        "mast_make": "Hyundai",
        "mast_type": "TF470",
        "mast_size": "69MN-T4715",
        "forks": "1.75 x 4 x 48 STD; 1.75 x 4 x 48 STD",
        "tire_type": "pneumatic",
        "tire_drive_size": "8.15-15",
        "tire_steer_size": "6.50-10",
        "owner": "stock",
        "stock_status": "available",
        "asking_price": "38900",
        "source_image_filename": "card-0002.jpg",
    },
    {
        "customer_name": "Katahdin Lumber",
        "card_date": "2023-11-30",
        "mechanic": "Dave",
        "condition": "used",
        "hour_meter": "9033",
        "unit_make": "Hyundai",
        "unit_model": "70D-9",
        "unit_serial": "HHKHFV30K00999",
        "fuel_type": "diesel",
        "battery_mfg": "",
        "needs_review": "yes",
        "review_note": "Serial hard to read on the card",
    },
]
