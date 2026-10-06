"""Reports: each is a title, who may run it, which feature flags it needs,
its columns, and a function that returns rows and totals for a period.

Rows are plain dicts. A row's `_to` is the app page it links to. Money
columns marked `sensitive` are left out for roles that may not see them."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from .periods import Period

Kind = Literal["text", "date", "money", "qty", "int", "days"]
Row = dict[str, Any]


@dataclass(frozen=True)
class Column:
    key: str
    label: str
    kind: Kind = "text"
    # Only these roles see the column (None: everyone who can run the report).
    roles: frozenset[str] | None = None
    # Shown on phones (the first column always is).
    primary: bool = False


@dataclass
class Result:
    rows: list[Row]
    totals: Row = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Report:
    key: str
    title: str
    description: str
    group: str
    roles: frozenset[str]
    flags: tuple[str, ...]
    columns: tuple[Column, ...]
    run: Callable[[Period, str], Result]
    # False: a snapshot of today (no date range).
    uses_period: bool = True

    def columns_for(self, role: str) -> list[Column]:
        return [c for c in self.columns if c.roles is None or role in c.roles]


REPORTS: dict[str, Report] = {}


def register(report: Report) -> Report:
    REPORTS[report.key] = report
    return report


def cell(value: Any, kind: Kind) -> Any:
    """A value as JSON: money and quantities as strings, dates as ISO."""
    if value is None:
        return None
    if kind == "money":
        return f"{Decimal(value):.2f}"
    if kind == "qty":
        return f"{Decimal(value).normalize():f}"
    if isinstance(value, date):
        return value.isoformat()
    return value


def csv_text(value: Any) -> str:
    """A cell for a spreadsheet. Text that a spreadsheet would run as a
    formula (=, +, -, @ at the start) gets a leading apostrophe."""
    if value is None:
        return ""
    text = str(value)
    if text and text[0] in "=+-@\t\r" and not _is_number(text):
        return "'" + text
    return text


def _is_number(text: str) -> bool:
    try:
        Decimal(text)
    except ArithmeticError:
        return False
    return True
