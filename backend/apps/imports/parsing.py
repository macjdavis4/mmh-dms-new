"""Read an import file and turn each row into checked values.

Nothing here touches the database. Values that don't parse cleanly are never
guessed at: they become a warning (the text is kept in the unit's notes) or
an error (the row can't be imported as is).
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from apps.units.models import normalize_serial

from .columns import BY_NAME, COLUMNS, MAX_ATTACHMENTS, PRICE_COLUMNS, Column, normalize_header

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_ROWS = 5000
TRUE = {"yes", "y", "true", "1", "x", "✓"}
FALSE = {"no", "n", "false", "0", ""}


class ImportFileError(Exception):
    """The file as a whole can't be read (wrong type, empty, too big...)."""


@dataclass
class Message:
    column: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"column": self.column, "message": self.message}


@dataclass
class ParsedRow:
    raw: dict[str, str]
    unit: dict[str, Any] = field(default_factory=dict)
    components: dict[str, dict[str, str]] = field(default_factory=dict)
    forks: list[tuple[str, int]] = field(default_factory=list)
    attachments: list[dict[str, Any]] = field(default_factory=list)
    hours: Decimal | None = None
    owner_kind: str = ""  # "customer" | "dealer" | "" (not given)
    owner_name: str = ""
    scans: list[str] = field(default_factory=list)
    as_written: list[str] = field(default_factory=list)  # values kept in notes, not parsed
    errors: list[Message] = field(default_factory=list)
    warnings: list[Message] = field(default_factory=list)

    @property
    def serial(self) -> str:
        return str(self.unit.get("serial_number", ""))

    @property
    def match_serial(self) -> str:
        return normalize_serial(self.serial)

    @property
    def stock_number(self) -> str:
        return str(self.unit.get("stock_number", ""))

    @property
    def label(self) -> str:
        return " ".join(p for p in [self.unit.get("make", ""), self.unit.get("model", "")] if p)


# --- Reading the file -------------------------------------------------------------------


def decode(data: bytes) -> str:
    """UTF-8 (with or without Excel's byte-order mark), else Windows-1252,
    which is what Excel's plain "CSV (Comma delimited)" writes."""
    if not data.strip():
        raise ImportFileError("The file is empty.")
    if data[:4] == b"PK\x03\x04":
        raise ImportFileError(
            "That looks like an Excel workbook (.xlsx). In Excel use File → Save As → "
            "CSV UTF-8 (Comma delimited), then upload the .csv file."
        )
    if b"\x00" in data[:4096]:
        raise ImportFileError("That isn't a CSV text file.")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")


def read_csv(data: bytes) -> tuple[list[dict[str, str]], list[Message]]:
    """Rows keyed by canonical column name, plus problems with the file itself."""
    if len(data) > MAX_FILE_BYTES:
        raise ImportFileError("The file is larger than 10 MB. Split it into smaller files.")
    text = decode(data)
    first_line = text.splitlines()[0] if text.splitlines() else ""
    try:
        dialect: Any = csv.Sniffer().sniff(first_line, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(text), dialect)
    try:
        header = next(reader)
    except StopIteration as exc:
        raise ImportFileError("The file is empty.") from exc

    messages: list[Message] = []
    names: list[str | None] = []
    seen: set[str] = set()
    for original in header:
        name = normalize_header(original)
        if not name:
            names.append(None)
        elif name not in BY_NAME:
            names.append(None)
            messages.append(Message(original, "Column not recognised, so it was ignored."))
        elif name in seen:
            names.append(None)
            messages.append(Message(original, "Column appears twice; only the first one is used."))
        else:
            names.append(name)
            seen.add(name)
    if not seen:
        raise ImportFileError(
            "None of the column names were recognised. Start from the template "
            "(Download template) and keep its first row."
        )
    if "unit_serial" not in seen and "stock_number" not in seen:
        raise ImportFileError(
            "The file needs a unit_serial column (or stock_number) to tell units apart."
        )

    rows: list[dict[str, str]] = []
    for values in reader:
        if not any(v.strip() for v in values):
            continue  # blank line
        if len(rows) >= MAX_ROWS:
            raise ImportFileError(
                f"The file has more than {MAX_ROWS:,} rows. Split it into smaller files."
            )
        row = {
            name: values[i].strip() if i < len(values) else ""
            for i, name in enumerate(names)
            if name is not None
        }
        if len(values) > len(names) and any(v.strip() for v in values[len(names) :]):
            row["__extra__"] = "1"
        rows.append(row)
    if not rows:
        raise ImportFileError("The file has a header row but no units.")
    return rows, messages


def from_json(item: dict[str, Any]) -> dict[str, str]:
    """A JSON unit uses the same keys as the CSV; values may be numbers or
    booleans, and `forks` / `source_image_filename` may be lists."""
    row: dict[str, str] = {}
    for key, value in item.items():
        name = normalize_header(str(key))
        if value is None:
            value = ""
        elif isinstance(value, bool):
            value = "yes" if value else "no"
        elif isinstance(value, list):
            value = "; ".join(str(v) for v in value)
        row[name] = str(value).strip()
    return row


# --- Parsing values ---------------------------------------------------------------------

_NUMBER_JUNK = re.compile(
    r"(?i)\s*(lbs?|pounds?|in(ches)?|\"|v|volts?|ah|hrs?|hours?|h|°|deg(rees)?)\.?\s*$"
)


def _number(raw: str, decimal_ok: bool) -> Decimal | None:
    cleaned = _NUMBER_JUNK.sub("", raw.replace(",", "")).strip()
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        return None
    if not value.is_finite() or (not decimal_ok and value != value.to_integral_value()):
        return None
    return value


def _money(raw: str) -> Decimal | None:
    cleaned = raw.replace("$", "").replace(",", "").strip()
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        return None
    if not value.is_finite() or value < 0 or value.as_tuple().exponent < -2:  # type: ignore[operator]
        return None
    return value.quantize(Decimal("0.01"))


def parse_date(raw: str) -> date | None:
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y", "%Y/%m/%d"):
        try:
            parsed = datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
        if 1940 <= parsed.year <= 2100:
            return parsed
    return None


def looks_mangled_by_excel(raw: str) -> bool:
    """Excel turns long numeric serials into 1.23E+12."""
    return bool(re.fullmatch(r"\d(\.\d+)?E\+\d+", raw, flags=re.IGNORECASE))


def _set(parsed: ParsedRow, col: Column, value: Any) -> None:
    target = col.target.split(".")
    if target[0] == "unit":
        parsed.unit[target[1]] = value
    elif target[0] == "component":
        parsed.components.setdefault(target[1], {})[target[2]] = value
    elif target[0] == "attachment":
        n = int(target[1])
        while len(parsed.attachments) < n:
            parsed.attachments.append({})
        parsed.attachments[n - 1][target[2]] = value
    elif target[0] == "owner":
        if target[1] == "name":
            parsed.owner_name = value
            parsed.unit["card_customer_name"] = value  # kept exactly as written
        else:
            parsed.owner_kind = value
    elif target[0] == "hours":
        parsed.hours = value
    elif target[0] == "scan":
        parsed.scans = [s.strip() for s in str(value).split(";") if s.strip()]


def _keep_as_written(parsed: ParsedRow, col: Column, raw: str, why: str) -> None:
    parsed.warnings.append(Message(col.name, f"{why} Kept “{raw}” in the notes instead."))
    parsed.as_written.append(f"{col.name} as written: {raw}")


def parse_row(raw: dict[str, str], *, can_price: bool) -> ParsedRow:
    parsed = ParsedRow(raw=raw)
    if raw.get("__extra__"):
        parsed.warnings.append(
            Message("", "Row has more values than there are columns; the extras were ignored.")
        )
    for col in COLUMNS:
        value = raw.get(col.name, "")
        if value == "":
            continue
        if col.name in PRICE_COLUMNS and not can_price:
            parsed.warnings.append(
                Message(col.name, "Only admin and sales can import prices; ignored.")
            )
            continue
        kind = col.kind
        if kind == "text":
            if col.max_length and len(value) > col.max_length:
                parsed.errors.append(
                    Message(
                        col.name,
                        f"Too long: {len(value)} characters (the limit is {col.max_length}).",
                    )
                )
                continue
            if col.name.endswith("serial") and looks_mangled_by_excel(value):
                parsed.errors.append(
                    Message(
                        col.name,
                        f"“{value}” looks like Excel turned the serial into a number. Format the column as Text and type it again.",
                    )
                )
                continue
            _set(parsed, col, value)
        elif kind in ("int", "decimal", "hours"):
            number = _number(value, decimal_ok=kind != "int")
            if number is None:
                _keep_as_written(parsed, col, value, "Not a number.")
                continue
            if (col.minimum is not None and number < col.minimum) or (
                col.maximum is not None and number > col.maximum
            ):
                _keep_as_written(parsed, col, value, f"Outside {col.minimum}–{col.maximum}.")
                continue
            if kind == "hours":
                if number < 0 or number >= Decimal("100000000"):
                    _keep_as_written(parsed, col, value, "Not a sensible hour meter reading.")
                    continue
                _set(parsed, col, number.quantize(Decimal("0.1")))
            else:
                _set(parsed, col, int(number) if kind == "int" else number.quantize(Decimal("0.1")))
        elif kind == "money":
            money = _money(value)
            if money is None:
                _keep_as_written(parsed, col, value, "Not an amount of money.")
                continue
            _set(parsed, col, money)
        elif kind == "date":
            parsed_date = parse_date(value)
            if parsed_date is None:
                _keep_as_written(
                    parsed, col, value, "Not a date we can read (use 2024-03-12 or 3/12/2024)."
                )
                continue
            _set(parsed, col, parsed_date)
        elif kind == "choice":
            choice = col.choices.get(value.lower().strip())
            if choice is None:
                options = ", ".join(sorted(set(col.choices)))
                if col.name in {"condition", "owner"}:
                    parsed.errors.append(Message(col.name, f"“{value}” isn't one of: {options}."))
                else:
                    _keep_as_written(parsed, col, value, f"Not one of: {options}.")
                continue
            _set(parsed, col, choice)
        elif kind == "bool":
            lowered = value.lower()
            if lowered in TRUE:
                _set(parsed, col, True)
            elif lowered in FALSE:
                _set(parsed, col, False)
            else:
                _keep_as_written(parsed, col, value, "Not yes or no.")
        elif kind == "forks":
            counts: dict[str, int] = {}
            for entry in (e.strip() for e in value.split(";")):
                if entry:
                    if len(entry) > 80:
                        parsed.errors.append(
                            Message(col.name, f"Fork entry too long: “{entry[:40]}…”.")
                        )
                        continue
                    counts[entry] = counts.get(entry, 0) + 1
            for dims, qty in counts.items():
                if qty > 8:
                    parsed.errors.append(
                        Message(col.name, f"{qty} forks of “{dims}” is more than 8.")
                    )
                else:
                    parsed.forks.append((dims, qty))

    # A unit has to be recognisable when the same card is imported again.
    if not parsed.serial and not parsed.stock_number:
        parsed.errors.append(Message("unit_serial", "Needs a unit serial (or a stock number)."))

    # Spools only describe a control valve that has some details.
    attachments: list[dict[str, Any]] = []
    for n, att in enumerate(parsed.attachments, start=1):
        if not att:
            continue
        if not (att.get("manufacturer") or att.get("type") or att.get("model")):
            parsed.errors.append(
                Message(
                    f"attachment_{n}_mfg", f"Attachment {n} needs a manufacturer, type or model."
                )
            )
            continue
        attachments.append(att)
    parsed.attachments = attachments[:MAX_ATTACHMENTS]

    if parsed.owner_kind == "customer" and not parsed.owner_name:
        parsed.errors.append(
            Message("customer_name", "owner is “customer” but customer_name is blank.")
        )
    if not parsed.owner_kind:
        parsed.owner_kind = "customer" if parsed.owner_name else "dealer"
    if parsed.unit.get("stock_status") and parsed.owner_kind == "customer":
        parsed.warnings.append(
            Message("stock_status", "A customer's unit isn't our stock; stock_status ignored.")
        )
        parsed.unit.pop("stock_status")
    return parsed
