"""Shared look for printouts: letterhead, footer with page numbers, tables.

Built with ReportLab's standard Helvetica (no font files to ship). Colors
follow the app: deep navy primary, one bright accent.
"""

from __future__ import annotations

import io
import re
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any
from xml.sax.saxutils import escape

from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Flowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

NAVY = colors.HexColor("#0b2a4a")
ACCENT = colors.HexColor("#f5b400")
MUTED = colors.HexColor("#5b6675")
LINE = colors.HexColor("#c9d1db")
SHADE = colors.HexColor("#eef2f6")
MARGIN = 0.6 * inch
WIDTH = LETTER[0] - 2 * MARGIN - 12  # the frame keeps 6 pt of padding on each side

_base = getSampleStyleSheet()
STYLES = {
    "title": ParagraphStyle(
        "title",
        parent=_base["Title"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        alignment=0,
        textColor=NAVY,
        spaceAfter=2,
    ),
    "subtitle": ParagraphStyle(
        "subtitle", parent=_base["Normal"], fontSize=10, leading=13, textColor=MUTED
    ),
    "h2": ParagraphStyle(
        "h2",
        parent=_base["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11.5,
        leading=14,
        textColor=NAVY,
        spaceBefore=10,
        spaceAfter=4,
    ),
    "body": ParagraphStyle("body", parent=_base["Normal"], fontSize=9.5, leading=12.5),
    "small": ParagraphStyle(
        "small", parent=_base["Normal"], fontSize=8, leading=10, textColor=MUTED
    ),
    "label": ParagraphStyle(
        "label",
        parent=_base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7,
        leading=9,
        textColor=MUTED,
    ),
    "value": ParagraphStyle("value", parent=_base["Normal"], fontSize=9.5, leading=12),
    "right": ParagraphStyle(
        "right", parent=_base["Normal"], fontSize=9.5, leading=12, alignment=TA_RIGHT
    ),
}


def text(value: Any) -> str:
    """Escape for Paragraph markup; keep line breaks; dash for blanks."""
    if value is None or value == "":
        return "—"
    return escape(str(value)).replace("\n", "<br/>")


def p(value: Any, style: str = "body", raw: bool = False) -> Paragraph:
    return Paragraph(value if raw else text(value), STYLES[style])


def facts(pairs: Sequence[tuple[str, Any]], columns: int = 4, width: float = WIDTH) -> Table:
    """A grid of LABEL / value cells; empty values are left out."""
    shown = [(k, v) for k, v in pairs if v not in (None, "", "—")]
    cells = [[p(k.upper(), "label"), p(v, "value")] for k, v in shown]
    rows = []
    for i in range(0, len(cells), columns):
        chunk = cells[i : i + columns]
        chunk += [["", ""]] * (columns - len(chunk))
        rows.append(
            [
                Table(
                    [[c[0]], [c[1]]],
                    style=[
                        ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ],
                )
                for c in chunk
            ]
        )
    if not rows:
        return Table([[p("Nothing recorded.", "small")]])
    table = Table(rows, colWidths=[width / columns] * columns)
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return table


def grid(
    header: Sequence[str],
    rows: Sequence[Sequence[Any]],
    widths: Sequence[float],
    blank_rows: int = 0,
) -> Table:
    """A ruled table with a shaded header row; `blank_rows` adds lines to write on."""
    data: list[list[Any]] = [[p(h.upper(), "label") for h in header]]
    data += [[c if isinstance(c, Flowable) else p(c) for c in row] for row in rows]
    data += [[""] * len(header) for _ in range(blank_rows)]
    table = Table(
        data,
        colWidths=[WIDTH * w for w in widths],
        repeatRows=1,
        rowHeights=[None] * (1 + len(rows)) + [0.32 * inch] * blank_rows,
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), SHADE),
                ("LINEBELOW", (0, 0), (-1, -1), 0.5, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def box(title: str, body: str, min_height: float = 0.9 * inch) -> Table:
    """A labelled box; tall enough to write in when it's empty."""
    content = p(body) if body.strip() else Spacer(1, min_height)
    table = Table([[p(title.upper(), "label")], [content]], colWidths=[WIDTH])
    table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.75, LINE),
                ("BACKGROUND", (0, 0), (-1, 0), SHADE),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def _letterhead(canvas: Canvas, doc: Any, label: str) -> None:
    canvas.saveState()
    width, height = LETTER
    canvas.setFillColor(NAVY)
    canvas.rect(0, height - 0.75 * inch, width, 0.75 * inch, stroke=0, fill=1)
    canvas.setFillColor(ACCENT)
    canvas.rect(0, height - 0.79 * inch, width, 0.04 * inch, stroke=0, fill=1)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 15)
    canvas.drawString(MARGIN, height - 0.42 * inch, settings.COMPANY_NAME)
    canvas.setFont("Helvetica", 8.5)
    contact = "  ·  ".join(
        x for x in [settings.COMPANY_ADDRESS, settings.COMPANY_PHONE, settings.COMPANY_WEBSITE] if x
    )
    canvas.drawString(MARGIN, height - 0.6 * inch, contact)
    # Slot for the "Authorized Hyundai Dealer" badge (artwork to be supplied).
    canvas.setStrokeColor(colors.white)
    canvas.setDash(2, 2)
    canvas.roundRect(
        width - MARGIN - 1.65 * inch,
        height - 0.62 * inch,
        1.65 * inch,
        0.4 * inch,
        4,
        stroke=1,
        fill=0,
    )
    canvas.setFont("Helvetica-Bold", 7)
    canvas.drawCentredString(
        width - MARGIN - 0.825 * inch, height - 0.45 * inch, "AUTHORIZED HYUNDAI DEALER"
    )
    canvas.setDash()
    # Footer.
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 7.5)
    printed = date_text(timezone.now())
    canvas.drawString(MARGIN, 0.4 * inch, f"{label}  ·  printed {printed}")
    canvas.drawRightString(width - MARGIN, 0.4 * inch, f"Page {doc.page}")
    canvas.restoreState()


def render(story: list[Any], *, title: str, label: str) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=LETTER,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=1.05 * inch,
        bottomMargin=0.7 * inch,
        title=title,
        author=settings.COMPANY_NAME,
        pageCompression=1 if settings.PDF_COMPRESS else 0,
    )

    def draw(canvas: Canvas, d: Any) -> None:
        _letterhead(canvas, d, label)

    doc.build(story, onFirstPage=draw, onLaterPages=draw)
    return buf.getvalue()


def date_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        value = timezone.localtime(value)
        return f"{value:%b} {value.day}, {value.year} {value:%I:%M %p}".replace(" 0", " ")
    return f"{value:%b} {value.day}, {value.year}"


def number(value: Any) -> str:
    """9120.0 -> "9,120"; 2.50 -> "2.5"."""
    if value is None:
        return ""
    d = Decimal(value).normalize()
    return f"{d:,f}" if d == d.to_integral() else f"{d:,}"


def pdf_response(data: bytes, filename: str) -> HttpResponse:
    response = HttpResponse(data, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    response["Cache-Control"] = "private, no-store"
    return response


def safe_filename(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-") or "document.pdf"
