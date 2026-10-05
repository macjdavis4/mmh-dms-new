"""Demo customers and forklift units for development, tests and screenshots.

Photos and the scanned card are drawn here with Pillow: generic placeholder
artwork, no real equipment photos, no trademarks.
"""

from __future__ import annotations

import io
from datetime import date
from decimal import Decimal
from typing import Any

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image, ImageDraw, ImageFont

from apps.customers.models import Address, Contact, Customer

from . import services
from .models import HourMeterReading, Unit, UnitAttachment, UnitComponent, UnitFile, UnitFork

CUSTOMERS: list[dict[str, Any]] = [
    {
        "name": "Penobscot Paper Co.",
        "account_number": "PPC-1001",
        "phone": "207-555-0101",
        "email": "maintenance@penobscotpaper.example",
        "contacts": [
            ("Dana", "Hale", "Plant manager", "207-555-0102", True),
            ("Chris", "Ober", "Maintenance lead", "207-555-0103", False),
        ],
        "address": ("120 Mill Street", "Bangor", "04401"),
    },
    {
        "name": "Bangor Building Supply",
        "account_number": "BBS-1002",
        "phone": "207-555-0110",
        "contacts": [("Jamie", "Roy", "Yard manager", "207-555-0111", True)],
        "address": ("44 Hogan Road", "Bangor", "04401"),
    },
    {
        "name": "Downeast Seafood Distributors",
        "account_number": "DSD-1003",
        "phone": "207-555-0120",
        "contacts": [("Robin", "Gray", "Operations", "207-555-0121", True)],
        "address": ("8 Water Street", "Ellsworth", "04605"),
    },
    {
        "name": "Katahdin Lumber",
        "account_number": "KAT-1004",
        "phone": "207-555-0130",
        "contacts": [("Morgan", "Pelletier", "Mill supervisor", "207-555-0131", True)],
        "address": ("1 Sawmill Lane", "Millinocket", "04462"),
    },
    {
        "name": "Kennebec Cold Storage",
        "account_number": "KCS-1005",
        "phone": "207-555-0140",
        "contacts": [],
        "address": ("300 Riverside Drive", "Augusta", "04330"),
    },
    {
        "name": "Pat Murphy",
        "kind": "individual",
        "phone": "207-555-0150",
        "contacts": [],
        "address": ("17 Main Road", "Hampden", "04444"),
    },
]

# (unit fields, extras). Owner None = our stock.
UNITS: list[tuple[dict[str, Any], dict[str, Any]]] = [
    (
        {
            "make": "Hyundai",
            "model": "35LN-9A",
            "serial_number": "HHKHHN04P00123",
            "year": 2026,
            "stock_number": "MMH-2401",
            "condition": "new",
            "fuel_type": "lpg",
            "capacity_lbs": 7000,
            "mast_make": "Hyundai",
            "mast_type": "TF470",
            "mast_size": "69MN-T4715",
            "mast_lift_height_in": 189,
            "tire_type": "pneumatic",
            "tire_drive_size": "8.15-15",
            "tire_steer_size": "6.50-10",
            "stock_status": "available",
            "cost": Decimal("31200"),
            "asking_price": Decimal("38900"),
        },
        {
            "owner": None,
            "hours": [(date(2026, 8, 20), "4.5", "manual")],
            "photo": (234, 120, 34),
            "components": [("engine", "Hyundai", "L4KB", "L4KB-26-11873")],
            "forks": ["1.75 x 4 x 48 STD"],
        },
    ),
    (
        {
            "make": "Doosan",
            "model": "G25N-7",
            "serial_number": "FGA25-71522",
            "year": 2017,
            "stock_number": "MMH-2388",
            "condition": "used",
            "fuel_type": "lpg",
            "capacity_lbs": 5000,
            "mast_make": "Doosan",
            "mast_type": "Triple",
            "mast_size": "V188",
            "mast_lift_height_in": 188,
            "tire_type": "solid",
            "tire_drive_size": "7.00-12",
            "tire_steer_size": "6.00-9",
            "stock_status": "in_prep",
            "cost": Decimal("11800"),
            "asking_price": Decimal("18500"),
            "review_note": "",
        },
        {
            "owner": None,
            "hours": [(date(2025, 11, 2), "8890", "sale"), (date(2026, 9, 14), "8902", "service")],
            "photo": (245, 190, 30),
            "components": [("engine", "Nissan", "K25", "K25-334190")],
        },
    ),
    (
        {
            "make": "Hyundai",
            "model": "50D-9",
            "serial_number": "HHKHFT20E00419",
            "year": 2020,
            "stock_number": "MMH-2391",
            "condition": "used",
            "fuel_type": "diesel",
            "capacity_lbs": 10000,
            "mast_lift_height_in": 157,
            "tire_type": "pneumatic",
            "tire_drive_size": "8.25-15",
            "tire_steer_size": "8.25-15",
            "stock_status": "available",
            "cost": Decimal("21000"),
            "asking_price": Decimal("27500"),
        },
        {"owner": None, "hours": [(date(2026, 7, 1), "5104", "sale")], "photo": (228, 110, 40)},
    ),
    (
        {
            "make": "Hyundai",
            "model": "20BT-9",
            "serial_number": "HHKHBT10P00877",
            "year": 2021,
            "stock_number": "MMH-2395",
            "condition": "used",
            "fuel_type": "electric",
            "capacity_lbs": 4000,
            "mast_lift_height_in": 210,
            "tire_type": "cushion",
            "battery_make": "EnerSys",
            "battery_model": "18-125-17",
            "battery_volts": 36,
            "battery_amp_hours": 750,
            "battery_size": "38.4 x 31.1 x 22.6",
            "battery_weight_lbs": 2150,
            "charger_make": "Hobart",
            "charger_model": "TR1-36",
            "stock_status": "available",
            "cost": Decimal("9800"),
            "asking_price": Decimal("14900"),
        },
        {"owner": None, "hours": [(date(2026, 6, 10), "3120", "sale")], "photo": (60, 130, 200)},
    ),
    (
        {
            "make": "Hyundai",
            "model": "30L-9A",
            "serial_number": "HHKHHL03P00052",
            "year": 2026,
            "stock_number": "MMH-2403",
            "condition": "new",
            "fuel_type": "lpg",
            "capacity_lbs": 6000,
            "mast_lift_height_in": 189,
            "stock_status": "on_hold",
            "cost": Decimal("28400"),
            "asking_price": Decimal("34900"),
        },
        {"owner": None, "hours": [], "photo": (234, 120, 34)},
    ),
    (
        {
            "make": "Hyundai",
            "model": "25LC-7A",
            "serial_number": "HHKHHC52C00316",
            "year": 2015,
            "stock_number": "MMH-2350",
            "condition": "used",
            "fuel_type": "lpg",
            "capacity_lbs": 5000,
            "stock_status": "sold",
            "cost": Decimal("7200"),
            "asking_price": Decimal("11900"),
            "sale_price": Decimal("11400"),
        },
        {
            "owner": None,
            "sold_to": "Bangor Building Supply",
            "hours": [(date(2026, 3, 3), "11870", "sale")],
        },
    ),
    # Customer units (service only)
    (
        {
            "make": "Doosan",
            "model": "G25N-7",
            "serial_number": "FGA25-70988",
            "year": 2016,
            "condition": "used",
            "fuel_type": "lpg",
            "capacity_lbs": 5000,
            "card_date": date(2024, 3, 12),
            "card_customer_name": "Penobscot Paper",
            "mechanic": "Sam W.",
            "work_order_number": "WO-4471",
            "mast_make": "Doosan",
            "mast_type": "TF470",
            "mast_size": "69MN-T4715",
            "mast_lift_height_in": 188,
            "lift_cylinder_number": "LC-2231",
            "carriage": "Class II, 40 in",
            "backrest_height": "48 in",
            "backrest_width": "40 in",
            "tilt_forward_deg": Decimal("6"),
            "tilt_back_deg": Decimal("10"),
            "tilt_reference": "TR-9",
            "tire_type": "solid",
            "tire_drive_size": "8.15-15",
            "tire_steer_size": "6.50-10",
            "tire_notes": "7.00 rim on drives",
            "special_equipment": "Blue spot light, rear work light",
            "field_modifications": "Fire extinguisher bracket added 2022",
            "notes": "Card is water stained at the bottom.",
        },
        {
            "owner": "Penobscot Paper Co.",
            "hours": [(date(2024, 3, 12), "9412", "card"), (date(2025, 9, 30), "10288", "service")],
            "components": [
                ("engine", "Nissan", "K25", "K25-118734"),
                ("alternator", "Hitachi", "LR160-741", ""),
                ("ignition", "Nissan", "Distributorless", ""),
                ("fuel_system", "Impco", "Cobra", "IMP-55103"),
                ("hydraulic_pump", "Kayaba", "KFP2316", "KP-9910"),
                ("control_valve", "Hydrocontrol", "HC-D12", "", "3SP"),
                ("transmission", "Doosan", "Powershift 1-spd", ""),
            ],
            "forks": ["1.75 x 4 x 48 STD"],
            "attachments": [
                (
                    "Cascade",
                    "SS/FP",
                    "65K-FPS-8169-C",
                    "CS-77120",
                    "0619",
                    True,
                    False,
                    "R-12",
                    "LH",
                )
            ],
            "card": True,
            "photo": (245, 190, 30),
        },
    ),
    (
        {
            "make": "Hyundai",
            "model": "35LN-9A",
            "serial_number": "HHKHHN04L0094",
            "year": 2018,
            "condition": "used",
            "fuel_type": "lpg",
            "capacity_lbs": 7000,
            "needs_review": True,
            "review_note": "Last two digits of the serial are hard to read on the card.",
            "card_date": date(2023, 10, 4),
            "card_customer_name": "Penobscot Paper",
            "mechanic": "J. Theriault",
        },
        {
            "owner": "Penobscot Paper Co.",
            "hours": [(date(2023, 10, 4), "6610", "card")],
            "components": [("engine", "Hyundai", "L4KB", "")],
        },
    ),
    (
        {
            "make": "Hyundai",
            "model": "18BT-9",
            "serial_number": "HHKHBT08J00221",
            "year": 2019,
            "condition": "used",
            "fuel_type": "electric",
            "capacity_lbs": 3500,
            "battery_make": "Crown",
            "battery_volts": 36,
            "battery_amp_hours": 625,
        },
        {
            "owner": "Downeast Seafood Distributors",
            "hours": [(date(2026, 5, 18), "7421", "service")],
        },
    ),
    (
        {
            "make": "Hyundai",
            "model": "70D-9",
            "serial_number": "HHKHFV30K00057",
            "year": 2019,
            "condition": "used",
            "fuel_type": "diesel",
            "capacity_lbs": 15500,
            "mast_lift_height_in": 157,
        },
        {"owner": "Katahdin Lumber", "hours": [(date(2026, 8, 2), "9033", "service")]},
    ),
]


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return ImageFont.load_default(size=size)


def placeholder_photo(color: tuple[int, int, int]) -> bytes:
    """A generic forklift illustration, clearly marked as a placeholder."""
    w, h = 1600, 1200
    img = Image.new("RGB", (w, h), (226, 232, 240))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 840, w, h], fill=(148, 163, 184))  # floor
    for x in range(0, w, 160):
        d.line([x, 840, x - 200, h], fill=(160, 174, 192), width=4)
    dark = (40, 44, 52)
    d.rectangle([1090, 220, 1130, 900], fill=dark)  # mast
    d.rectangle([1160, 220, 1200, 900], fill=dark)
    d.rectangle([1200, 700, 1250, 900], fill=dark)  # carriage
    d.rectangle([1250, 880, 1520, 905], fill=(80, 84, 92))  # forks
    d.rounded_rectangle([380, 560, 1100, 860], radius=40, fill=color)  # body
    d.rounded_rectangle(
        [300, 600, 460, 860], radius=30, fill=tuple(int(c * 0.75) for c in color)
    )  # weight
    d.line([620, 560, 700, 300, 1060, 300, 1080, 560], fill=dark, width=26)  # overhead guard
    d.rectangle([700, 470, 840, 560], fill=dark)  # seat
    for cx, r in ((560, 120), (980, 105)):
        d.ellipse([cx - r, 900 - r, cx + r, 900 + r], fill=(30, 30, 30))
        d.ellipse([cx - r // 2, 900 - r // 2, cx + r // 2, 900 + r // 2], fill=(120, 120, 120))
    d.rectangle([0, h - 90, w, h], fill=(11, 42, 74))
    d.text((40, h - 68), "PLACEHOLDER PHOTO · demo data", fill=(255, 255, 255), font=_font(44))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=82)
    return buf.getvalue()


def scanned_card(unit: Unit) -> bytes:
    """An imitation of a filled-in paper unit card, for demos only."""
    w, h = 1700, 1100
    img = Image.new("RGB", (w, h), (250, 246, 232))
    d = ImageDraw.Draw(img)
    label, value = _font(26), _font(30)
    ink = (28, 52, 120)
    d.text((60, 40), "UNIT CARD  (sample scan, demo data)", fill=(60, 60, 60), font=_font(40))
    rows = [
        (
            "Customer",
            unit.card_customer_name,
            "Date",
            f"{unit.card_date:%m/%d/%y}" if unit.card_date else "",
        ),
        ("Mechanic", unit.mechanic, "W.O. #", unit.work_order_number),
        ("Unit make", unit.make, "Model", unit.model),
        ("Serial", unit.serial_number, "Condition", unit.get_condition_display()),
        ("Mast", f"{unit.mast_make} {unit.mast_type}", "Size", unit.mast_size),
        ("Tires drive", unit.tire_drive_size, "Steer", unit.tire_steer_size),
        (
            "Tilt fwd/back",
            f"{unit.tilt_forward_deg or ''} / {unit.tilt_back_deg or ''}",
            "Ref #",
            unit.tilt_reference,
        ),
        ("Special equip.", unit.special_equipment, "", ""),
        ("Field mods", unit.field_modifications, "", ""),
    ]
    y = 130
    for left_label, left_value, right_label, right_value in rows:
        d.line([60, y + 70, w - 60, y + 70], fill=(170, 190, 210), width=2)
        d.text((60, y + 10), left_label, fill=(90, 90, 90), font=label)
        d.text((290, y + 22), str(left_value), fill=ink, font=value)
        if right_label:
            d.text((960, y + 10), right_label, fill=(90, 90, 90), font=label)
            d.text((1140, y + 22), str(right_value), fill=ink, font=value)
        y += 95
    img = img.rotate(-0.8, expand=False, fillcolor=(250, 246, 232))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=80)
    return buf.getvalue()


def load_demo_data(with_files: bool = True) -> None:
    """Idempotent: skips customers and units that already exist."""
    by_name: dict[str, Customer] = {}
    for spec in CUSTOMERS:
        customer = Customer.all_objects.filter(name=spec["name"]).first()
        if customer is None:
            customer = Customer.objects.create(
                name=spec["name"],
                kind=spec.get("kind", "business"),
                account_number=spec.get("account_number", ""),
                phone=spec.get("phone", ""),
                email=spec.get("email", ""),
            )
            for first, last, title, phone, primary in spec["contacts"]:
                Contact.objects.create(
                    customer=customer,
                    first_name=first,
                    last_name=last,
                    title=title,
                    phone=phone,
                    is_primary=primary,
                )
            line1, city, postal = spec["address"]
            Address.objects.create(
                customer=customer, line1=line1, city=city, postal_code=postal, is_primary=True
            )
        by_name[customer.name] = customer

    for fields, extra in UNITS:
        if Unit.all_objects.filter(serial_number=fields["serial_number"]).exists():
            continue
        unit = Unit.objects.create(**fields)
        for comp in extra.get("components", []):
            kind, make, model, serial, *spools = comp
            UnitComponent.objects.create(
                unit=unit,
                kind=kind,
                make=make,
                model=model,
                serial_number=serial,
                spools=spools[0] if spools else "",
            )
        for dims in extra.get("forks", []):
            UnitFork.objects.create(unit=unit, dimensions=dims)
        for att in extra.get("attachments", []):
            mfr, typ, model, serial, date_code, reel, internal, reel_no, side = att
            UnitAttachment.objects.create(
                unit=unit,
                manufacturer=mfr,
                type=typ,
                model=model,
                serial_number=serial,
                date_code=date_code,
                hose_reel=reel,
                internal_hose=internal,
                reel_number=reel_no,
                side=side,
            )
        start = unit.card_date or date(2025, 1, 15)
        owner = by_name.get(extra["owner"]) if extra.get("owner") else None
        services.transfer_ownership(
            unit, owner_kind="customer" if owner else "dealer", customer=owner, start_date=start
        )
        if extra.get("sold_to"):
            services.transfer_ownership(
                unit,
                owner_kind="customer",
                customer=by_name[extra["sold_to"]],
                start_date=date(2026, 3, 3),
            )
        for when, hours, source in extra.get("hours", []):
            HourMeterReading.objects.create(
                unit=unit, reading_date=when, hours=Decimal(hours), source=source
            )
        if with_files and extra.get("photo"):
            services.add_file(
                unit,
                SimpleUploadedFile(
                    "photo.jpg", placeholder_photo(extra["photo"]), content_type="image/jpeg"
                ),
                kind=UnitFile.Kind.PHOTO,
                caption="Placeholder photo",
            )
        if with_files and extra.get("card"):
            services.add_file(
                unit,
                SimpleUploadedFile("card.jpg", scanned_card(unit), content_type="image/jpeg"),
                kind=UnitFile.Kind.SCANNED_CARD,
                caption="Original unit card",
            )
