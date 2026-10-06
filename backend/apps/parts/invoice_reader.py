"""Read a supplier invoice into text, then suggest its header and lines.

Text comes from the PDF itself when it has a text layer (most emailed
invoices), or from Tesseract OCR for scans and phone photos. Everything runs
on our server; nothing is sent anywhere. The parser only *suggests*: a
person checks every line before stock changes, and the raw text of each
line is kept as read."""

from __future__ import annotations

import io
import logging
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation

from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

OCR_TIMEOUT_SECONDS = 120
MAX_PAGES = 20
# A PDF page with less text than this is treated as a scan and OCR'd.
MIN_TEXT_CHARS = 40
MIN_OCR_EDGE = 1800  # small photos are scaled up; Tesseract likes ~300 dpi


class ReadError(Exception):
    """The file couldn't be read; the message is shown to the user."""


@dataclass
class ReadResult:
    text: str
    method: str  # "pdf-text" or "ocr"


# --- Getting text --------------------------------------------------------------------------


def ocr_available() -> bool:
    return shutil.which("tesseract") is not None


def _prepare(img: Image.Image) -> bytes:
    img = ImageOps.exif_transpose(img).convert("L")
    longest = max(img.size)
    if longest < MIN_OCR_EDGE:
        scale = MIN_OCR_EDGE / longest
        img = img.resize(
            (round(img.width * scale), round(img.height * scale)), Image.Resampling.LANCZOS
        )
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def ocr_image(data: bytes) -> str:
    """Tesseract on one image. `--psm 6` reads it as one block of text, which
    keeps each table row on one line."""
    if not ocr_available():
        logger.error("tesseract is not installed; can't read scanned invoices")
        raise ReadError("The invoice reader isn't installed on the server. Type the lines in.")
    try:
        with Image.open(io.BytesIO(data)) as img:
            png = _prepare(img)
    except (OSError, Image.DecompressionBombError) as exc:
        raise ReadError("That picture couldn't be opened.") from exc
    try:
        done = subprocess.run(
            ["tesseract", "stdin", "stdout", "--psm", "6", "-l", "eng"],  # noqa: S607
            input=png,
            capture_output=True,
            timeout=OCR_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ReadError(
            "Reading the picture took too long. Try a smaller or clearer photo."
        ) from exc
    if done.returncode != 0:
        logger.error(
            "tesseract failed", extra={"stderr": done.stderr.decode(errors="replace")[:500]}
        )
        raise ReadError("The picture couldn't be read. Type the lines in.")
    return done.stdout.decode("utf-8", errors="replace")


def read_pdf(data: bytes) -> ReadResult:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise ReadError("The PDF is password protected. Save it without a password first.")
        pages = list(reader.pages)[:MAX_PAGES]
        texts: list[str] = []
        used_ocr = False
        for page in pages:
            text = page.extract_text(extraction_mode="layout") or ""
            if len(re.sub(r"\s", "", text)) >= MIN_TEXT_CHARS:
                texts.append(text)
                continue
            # A scanned page: OCR the pictures on it.
            for image in page.images:
                texts.append(ocr_image(image.data))
                used_ocr = True
    except ReadError:
        raise
    except (PdfReadError, ValueError, KeyError, TypeError, OSError) as exc:
        raise ReadError("That PDF couldn't be opened. It may be damaged.") from exc
    text = "\n".join(texts)
    if not text.strip():
        raise ReadError("No text was found in the PDF. Type the lines in.")
    return ReadResult(text, "ocr" if used_ocr else "pdf-text")


def read_file(data: bytes, content_type: str) -> ReadResult:
    if content_type == "application/pdf":
        return read_pdf(data)
    text = ocr_image(data)
    if not text.strip():
        raise ReadError(
            "No text was found in the picture. Try a clearer photo, or type the lines in."
        )
    return ReadResult(text, "ocr")


# --- Suggesting fields ---------------------------------------------------------------------

MONEY_RE = re.compile(r"^\(?\$?(\d{1,3}(?:,\d{3})+|\d+)\.(\d{2})\)?$")
QTY_RE = re.compile(r"^\d{1,5}(?:\.\d{1,2})?$")
PART_RE = re.compile(r"^(?=.*\d)[A-Z0-9][A-Z0-9\-./]{2,39}$", re.IGNORECASE)
# "Invoice No: HMA-558812": on one line, and the number has a digit in it.
INVOICE_NO_RE = re.compile(
    r"\binvoice[ \t]*(?:no\.?|number|num|#)?[ \t]*[:#]?[ \t]*"
    r"((?=[A-Z0-9\-/]*\d)[A-Z0-9][A-Z0-9\-/]{2,30})\b",
    re.IGNORECASE,
)
DATE_WORD_RE = re.compile(r"\b(?:invoice\s+)?date\b\s*[:.]?\s*(.{6,20})", re.IGNORECASE)
TOTAL_RE = re.compile(
    r"\b(?:invoice\s+total|total\s+due|amount\s+due|balance\s+due|total)\b\s*[:$]*\s*\$?\s*"
    r"(\d{1,3}(?:,\d{3})+\.\d{2}|\d+\.\d{2})",
    re.IGNORECASE,
)
FREIGHT_RE = re.compile(
    r"\b(?:freight|shipping)\b\s*[:$]*\s*\$?\s*(\d[\d,]*\.\d{2})", re.IGNORECASE
)
TAX_RE = re.compile(r"\b(?:sales\s+)?tax\b\s*[:$]*\s*\$?\s*(\d[\d,]*\.\d{2})", re.IGNORECASE)
NOT_STOCK_WORDS = re.compile(
    r"\b(freight|shipping|core\s+charge|hazmat|handling|fuel\s+surcharge|restocking)\b",
    re.IGNORECASE,
)
MONTH_NAMES = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
MONTHS = {m: i for i, m in enumerate(MONTH_NAMES, 1)}


@dataclass
class SuggestedLine:
    raw_text: str
    part_number: str = ""
    description: str = ""
    quantity_shipped: Decimal = Decimal("0")
    quantity_backordered: Decimal = Decimal("0")
    unit_cost: Decimal | None = None
    not_stocked: bool = False
    check_reason: str = ""


@dataclass
class Suggestion:
    invoice_number: str = ""
    invoice_date: date | None = None
    total: Decimal | None = None
    freight: Decimal | None = None
    tax: Decimal | None = None
    lines: list[SuggestedLine] = field(default_factory=list)


def money(token: str) -> Decimal | None:
    m = MONEY_RE.match(token.strip())
    if not m:
        return None
    try:
        return Decimal(f"{m.group(1).replace(',', '')}.{m.group(2)}")
    except InvalidOperation:
        return None


def parse_date(text: str) -> date | None:
    """First date in the text: 10/05/2026, 2026-10-05, Oct 5, 2026, 5 Oct 2026."""
    candidates = [
        (r"(\d{4})-(\d{1,2})-(\d{1,2})", "ymd"),
        (r"(\d{1,2})/(\d{1,2})/(\d{2,4})", "mdy"),
        (r"(\d{1,2})-(\d{1,2})-(\d{2,4})", "mdy"),
        (r"([A-Za-z]{3})[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})", "Mdy"),
        (r"(\d{1,2})\s+([A-Za-z]{3})[a-z]*\.?,?\s+(\d{4})", "dMy"),
    ]
    found: list[tuple[int, date]] = []
    for pattern, order in candidates:
        for m in re.finditer(pattern, text):
            a, b, c = m.groups()
            try:
                if order == "ymd":
                    d = date(int(a), int(b), int(c))
                elif order == "mdy":
                    year = int(c) + (2000 if len(c) == 2 else 0)
                    d = date(year, int(a), int(b))
                elif order == "Mdy":
                    d = date(int(c), MONTHS[a.lower()[:3]], int(b))
                else:
                    d = date(int(c), MONTHS[b.lower()[:3]], int(a))
            except (ValueError, KeyError):
                continue
            found.append((m.start(), d))
    return min(found)[1] if found else None


def _qty(token: str) -> Decimal | None:
    return Decimal(token) if QTY_RE.match(token) else None


def parse_line(raw: str) -> SuggestedLine | None:
    """One table row: part number, description, quantities, unit price and
    extended price, in either of the two usual orders:

        31N4-01050  ENGINE OIL FILTER   12   9.80   117.60
        12  10  2  31N4-01050  ENGINE OIL FILTER  9.80  98.00   (ordered, shipped, b/o)
    """
    tokens = raw.replace("$", " ").split()
    if len(tokens) < 3:
        return None
    # Money at the end: unit price and extended price (or just one of them).
    prices: list[Decimal] = []
    while tokens and len(prices) < 2 and (value := money(tokens[-1])) is not None:
        prices.insert(0, value)
        tokens.pop()
    if not prices:
        return None
    # Quantities just before the prices, or at the start of the line.
    trailing: list[Decimal] = []
    while tokens and len(trailing) < 3 and (q := _qty(tokens[-1])) is not None:
        trailing.insert(0, q)
        tokens.pop()
    leading: list[Decimal] = []
    while tokens and len(leading) < 3 and (q := _qty(tokens[0])) is not None:
        leading.append(q)
        tokens.pop(0)
    qtys = trailing or leading
    if not tokens:
        return None
    first = tokens[0].strip(",;:")
    if PART_RE.match(first):
        part_number, words = first, tokens[1:]
    else:
        part_number, words = "", tokens
    line = SuggestedLine(raw_text=raw.strip()[:500], part_number=part_number[:60])
    line.description = " ".join(words)[:200]
    line.not_stocked = bool(NOT_STOCK_WORDS.search(raw))
    reasons: list[str] = []

    # Quantities: [shipped], [ordered, shipped] or [ordered, shipped, backordered].
    if len(qtys) == 3:
        ordered, shipped, backordered = qtys
    elif len(qtys) == 2:
        ordered, shipped = qtys
        backordered = max(ordered - shipped, Decimal("0"))
    elif len(qtys) == 1:
        ordered = shipped = qtys[0]
        backordered = Decimal("0")
    else:
        ordered = shipped = Decimal("1") if line.not_stocked else Decimal("0")
        backordered = Decimal("0")
        if not line.not_stocked:
            reasons.append("No quantity found")
    line.quantity_shipped = shipped
    line.quantity_backordered = backordered
    if len(qtys) == 3 and ordered != shipped + backordered:
        reasons.append("Ordered isn't shipped plus backordered")

    # Prices: unit then extended. Check one against the other.
    if len(prices) == 2:
        unit, extended = prices
        line.unit_cost = unit
        # Some invoices extend on the quantity ordered, so either may match.
        off_shipped = abs(unit * shipped - extended) > Decimal("0.02")
        if shipped and off_shipped and abs(unit * ordered - extended) > Decimal("0.02"):
            reasons.append("Quantity times price doesn't match the line total")
    else:
        (only,) = prices
        line.unit_cost = (only / shipped).quantize(Decimal("0.01")) if shipped else only
        reasons.append("Only one price found")
    if not part_number and not line.not_stocked:
        reasons.append("No part number found")
    line.check_reason = "; ".join(reasons)[:200]
    return line


def _header_money(pattern: re.Pattern[str], text: str, last: bool = False) -> Decimal | None:
    matches = pattern.findall(text)
    if not matches:
        return None
    value = matches[-1] if last else matches[0]
    return money(value)


def suggest(text: str) -> Suggestion:
    result = Suggestion()
    if m := INVOICE_NO_RE.search(text):
        result.invoice_number = m.group(1)[:60]
    if m := DATE_WORD_RE.search(text):
        result.invoice_date = parse_date(m.group(1))
    if result.invoice_date is None:
        result.invoice_date = parse_date(text)
    result.total = _header_money(TOTAL_RE, text, last=True)
    result.freight = _header_money(FREIGHT_RE, text)
    result.tax = _header_money(TAX_RE, text)
    for raw in text.splitlines():
        if not raw.strip() or (TOTAL_RE.search(raw) and not PART_RE.match(raw.split()[0])):
            continue
        line = parse_line(raw)
        if line is None:
            continue
        # Freight and tax on their own lines are header amounts, not lines.
        if not line.part_number and (FREIGHT_RE.search(raw) or TAX_RE.search(raw)):
            continue
        if re.search(r"\bsub\s*-?total\b", raw, re.IGNORECASE):
            continue
        result.lines.append(line)
    return result
