"""Demo bins and parts for development, tests and screenshots. The numbers
look real but are made up; cross references here are not real equivalents."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from . import services
from .models import Bin, Part

BINS = [
    ("A-01-1", "Filters: oil and fuel"),
    ("A-01-2", "Filters: air and hydraulic"),
    ("B-02-1", "Brakes"),
    ("C-01-3", "Electrical: switches and relays"),
    ("C-02-1", "Lights"),
    ("D-01-1", "Mast chain (by the foot)"),
    ("E-FLOOR", "Fluids, on the floor by the door"),
    ("F-03-2", "Attachment parts"),
    ("G-TIRES", "Tire rack"),
]

DEMO_NOTE = "Demo data: made-up number."

# (manufacturer, number, description, category, unit, cost, list, bin,
#  reorder point, reorder qty, vendor, fits, cross refs [(mfr, number)])
PARTS: list[tuple[Any, ...]] = [
    (
        "Hyundai",
        "31N4-01050",
        "Engine oil filter",
        "filters",
        "each",
        "9.80",
        "18.50",
        "A-01-1",
        6,
        12,
        "Hyundai parts",
        "35LN-9A, 30L-9A, 25L-9A",
        [("Donaldson", "P55-0084"), ("Fleetguard", "LF-3345X")],
    ),
    (
        "Hyundai",
        "31N4-01060",
        "Fuel filter, LPG vaporizer",
        "filters",
        "each",
        "14.20",
        "27.00",
        "A-01-1",
        4,
        8,
        "Hyundai parts",
        "35LN-9A, 30L-9A",
        [],
    ),
    (
        "Hyundai",
        "31N4-02100",
        "Air filter element, outer",
        "filters",
        "each",
        "31.00",
        "58.00",
        "A-01-2",
        3,
        6,
        "Hyundai parts",
        "35LN-9A, 30L-9A, 25L-9A",
        [("Donaldson", "P82-7653")],
    ),
    (
        "Hyundai",
        "XKBH-00117",
        "Hydraulic return filter (old style)",
        "filters",
        "each",
        "22.00",
        "41.00",
        "A-01-2",
        None,
        None,
        "Hyundai parts",
        "25L-7A, 30L-7A",
        [],
    ),
    (
        "Hyundai",
        "XKBH-00117A",
        "Hydraulic return filter",
        "filters",
        "each",
        "24.50",
        "45.00",
        "A-01-2",
        2,
        6,
        "Hyundai parts",
        "25L-7A, 30L-7A, 25L-9A",
        [("Baldwin", "PT-9417")],
    ),
    (
        "Hyundai",
        "31N4-40020",
        "Brake shoe set, one wheel",
        "brakes",
        "set",
        "62.00",
        "118.00",
        "B-02-1",
        2,
        4,
        "Hyundai parts",
        "35LN-9A, 30L-9A",
        [],
    ),
    (
        "Impco",
        "RK-CA100",
        "LPG regulator repair kit",
        "engine",
        "kit",
        "38.00",
        "74.00",
        "B-02-1",
        1,
        3,
        "Northeast Propane Supply",
        "Most LPG trucks with a CA100 mixer",
        [],
    ),
    (
        "",
        "BL-634",
        "Leaf chain BL-634 (mast)",
        "mast",
        "foot",
        "11.40",
        "22.00",
        "D-01-1",
        20,
        50,
        "Bangor Chain & Bearing",
        "Hyundai 25-35 class, Doosan G25N",
        [],
    ),
    (
        "Hyundai",
        "31N5-50110",
        "Ignition key switch",
        "electrical",
        "each",
        "26.00",
        "49.00",
        "C-01-3",
        2,
        4,
        "Hyundai parts",
        "35LN-9A, 30L-9A, 50D-9",
        [],
    ),
    (
        "",
        "LED-1280-W",
        "LED work light, 12-80 V",
        "safety",
        "each",
        "34.00",
        "69.00",
        "C-02-1",
        4,
        6,
        "Pine State Lighting",
        "Any truck, 12-80 V",
        [],
    ),
    (
        "",
        "LED-BLUE-SPOT",
        "Blue pedestrian spot light",
        "safety",
        "each",
        "48.00",
        "95.00",
        "C-02-1",
        2,
        4,
        "Pine State Lighting",
        "Any truck, 12-80 V",
        [],
    ),
    (
        "",
        "AW32-5G",
        "Hydraulic oil AW 32, 5 gallon pail",
        "fluids",
        "each",
        "46.00",
        "79.00",
        "E-FLOOR",
        4,
        8,
        "Down East Lubricants",
        "",
        [],
    ),
    (
        "Cascade",
        "SS-BRG-KIT",
        "Side shifter bearing kit",
        "attachments",
        "kit",
        "88.00",
        "165.00",
        "F-03-2",
        1,
        2,
        "Cascade",
        "Cascade SS/FP side shifters",
        [],
    ),
    (
        "",
        "TIRE-815-15-S",
        "Solid tire 8.15-15, black",
        "tires",
        "each",
        "210.00",
        "345.00",
        "G-TIRES",
        2,
        4,
        "Maine Tire Co.",
        "8.15-15 drive",
        [],
    ),
]


def load_demo_parts() -> None:
    """Idempotent: skips bins and parts that already exist."""
    bins: dict[str, Bin] = {}
    for code, description in BINS:
        bins[code] = Bin.all_objects.filter(code=code).first() or Bin.objects.create(
            code=code, description=description
        )
    for row in PARTS:
        mfr, number, desc, cat, uom, cost, price, bin_code, point, qty, vendor, fits, refs = row
        if services.find_duplicate(mfr, number) is not None:
            continue
        part = Part(  # type: ignore[misc]
            manufacturer=mfr,
            part_number=number,
            description=desc,
            category=cat,
            unit_of_measure=uom,
            cost=Decimal(cost),
            list_price=Decimal(price),
            bin=bins[bin_code],
            reorder_point=Decimal(point) if point is not None else None,
            reorder_quantity=Decimal(qty) if qty is not None else None,
            vendor=vendor,
            fits=fits,
            notes=DEMO_NOTE,
        )
        services.save_part(
            part, cross_references=[{"manufacturer": m, "part_number": n} for m, n in refs]
        )
    old = Part.objects.filter(part_number="XKBH-00117").first()
    new = Part.objects.filter(part_number="XKBH-00117A").first()
    if old and new and old.superseded_by_id is None:
        old.superseded_by = new
        services.save_part(old)


# Opening shelf counts. Parts left out (RK-CA100) have never been counted, so
# they show as out of stock; several end up at or below their reorder point.
OPENING = {
    "31N4-01050": "8",
    "31N4-01060": "3",
    "31N4-02100": "7",
    "XKBH-00117A": "4",
    "31N4-40020": "1",
    "BL-634": "120",
    "31N5-50110": "5",
    "LED-1280-W": "6",
    "LED-BLUE-SPOT": "2",
    "AW32-5G": "9",
    "SS-BRG-KIT": "2",
    "TIRE-815-15-S": "2",
}
# (part number, quantity, reference) received after the count.
RECEIVED = [("31N4-01050", "12", "Hyundai invoice 55120 (demo)")]
# (unit serial, work order complaint starts with, part number, quantity)
USED = [
    ("HHKHFV30K00057", "Mast chatters", "BL-634", "12"),
    ("FGA25-70988", "Hydraulic leak", "AW32-5G", "1"),
    ("HHKHHL03P00052", "Prep for delivery", "LED-BLUE-SPOT", "1"),
]


def load_demo_stock() -> None:
    """Counts, a delivery, and parts on the open demo work orders. Safe to run
    again: parts that already have stock history are left alone."""
    from apps.service.models import WorkOrder

    from . import stock
    from .models import StockMovement

    for number, counted in OPENING.items():
        part = Part.objects.filter(part_number=number).first()
        if part is None or StockMovement.objects.filter(part=part).exists():
            continue
        stock.count(part, Decimal(counted), note="Opening count (demo)")
        for rec_number, qty, reference in RECEIVED:
            if rec_number == number:
                stock.receive(part, Decimal(qty), reference=reference)
        for serial, complaint, used_number, used_qty in USED:
            if used_number != number:
                continue
            work_order = WorkOrder.objects.filter(
                unit__serial_number=serial,
                complaint__startswith=complaint,
                status__in=WorkOrder.OPEN_STATUSES,
            ).first()
            if work_order is not None:
                stock.issue(part, work_order, Decimal(used_qty))
