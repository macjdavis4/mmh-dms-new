"""A made-up supplier invoice, as a PDF (with a text layer, like an emailed
invoice) or a PNG (like a phone photo of a paper one). Used by the tests,
the demo data and the Playwright tests:

    python manage.py make_sample_invoice /tmp/sample-invoice.pdf
"""

from __future__ import annotations

import io
from collections.abc import Sequence
from datetime import date

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

SUPPLIER = "Hyundai parts"
NUMBER = "HMA-558812"
DATE = date(2026, 10, 1)

# ordered, shipped, backordered, part number, description, unit price
LINES: list[tuple[int, int, int, str, str, str]] = [
    (12, 12, 0, "31N4-01050", "ENGINE OIL FILTER", "9.80"),
    (8, 6, 2, "31N4-01060", "FUEL FILTER LPG VAPORIZER", "14.25"),
    (4, 4, 0, "31N4-40020", "BRAKE SHOE SET", "61.00"),
    (2, 2, 0, "XKBH-00117", "HYD RETURN FILTER", "22.40"),
    (1, 1, 0, "99Z9-12345", "SEAT BELT ASSY ORANGE", "38.00"),
]
FREIGHT = "35.00"


def _rows(lines: Sequence[tuple[int, int, int, str, str, str]]) -> list[str]:
    rows = []
    for ordered, shipped, backordered, number, description, price in lines:
        extended = f"{float(price) * shipped:.2f}"
        rows.append(
            f"{ordered:>3} {shipped:>4} {backordered:>3}   {number:<12} {description:<28}"
            f"{price:>9} {extended:>9}"
        )
    return rows


def _totals(lines: Sequence[tuple[int, int, int, str, str, str]]) -> tuple[str, str]:
    subtotal = sum(float(p) * s for _, s, _, _, _, p in lines)
    return f"{subtotal:.2f}", f"{subtotal + float(FREIGHT):.2f}"


def text_lines(
    lines: Sequence[tuple[int, int, int, str, str, str]] = LINES, number: str = NUMBER
) -> list[str]:
    subtotal, total = _totals(lines)
    return [
        "HYUNDAI PARTS - NORTHEAST DISTRIBUTION",
        "INVOICE",
        f"Invoice No: {number}",
        f"Invoice Date: {DATE:%m/%d/%Y}",
        "Sold to: Maine Material Handling, Bangor ME",
        "",
        "ORD SHIP B/O   PART NUMBER  DESCRIPTION                     PRICE  EXTENDED",
        *_rows(lines),
        "",
        f"Subtotal {subtotal}",
        f"Freight {FREIGHT}",
        f"Invoice Total {total}",
    ]


def pdf(
    lines: Sequence[tuple[int, int, int, str, str, str]] = LINES, number: str = NUMBER
) -> bytes:
    buf = io.BytesIO()
    page = canvas.Canvas(buf, pagesize=LETTER)
    page.setTitle(f"Invoice {number}")
    y = LETTER[1] - 0.8 * inch
    for row in text_lines(lines, number):
        page.setFont("Courier-Bold" if row.isupper() and row else "Courier", 9)
        page.drawString(0.6 * inch, y, row)
        y -= 14
    page.showPage()
    page.save()
    return buf.getvalue()


def png(
    lines: Sequence[tuple[int, int, int, str, str, str]] = LINES, number: str = NUMBER
) -> bytes:
    """The same invoice as a picture, for the OCR path."""
    rows = text_lines(lines, number)
    font = ImageFont.load_default(size=30)
    img = Image.new("L", (2000, 80 + 46 * len(rows)), color=255)
    draw = ImageDraw.Draw(img)
    for i, row in enumerate(rows):
        draw.text((50, 40 + 46 * i), row, fill=0, font=font)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def scanned_pdf(
    lines: Sequence[tuple[int, int, int, str, str, str]] = LINES, number: str = NUMBER
) -> bytes:
    """A PDF with only a picture of the invoice in it, as a scanner makes."""
    from reportlab.lib.utils import ImageReader

    picture = Image.open(io.BytesIO(png(lines, number)))
    buf = io.BytesIO()
    page = canvas.Canvas(buf, pagesize=LETTER)
    width = LETTER[0] - inch
    height = width * picture.height / picture.width
    page.drawImage(ImageReader(picture), 0.5 * inch, LETTER[1] - 0.5 * inch - height, width, height)
    page.showPage()
    page.save()
    return buf.getvalue()
