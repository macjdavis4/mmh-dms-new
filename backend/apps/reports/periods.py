"""Date ranges for reports: presets people use, or any from/to."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from django.utils import timezone
from rest_framework.exceptions import ValidationError

PRESETS = {
    "this_month": "This month",
    "last_month": "Last month",
    "this_year": "This year",
    "last_year": "Last year",
    "last_12_months": "Last 12 months",
}
MAX_DAYS = 366 * 5


@dataclass(frozen=True)
class Period:
    start: date
    end: date
    preset: str = ""

    @property
    def label(self) -> str:
        if self.preset:
            return PRESETS[self.preset]
        return f"{self.start:%b %-d, %Y} to {self.end:%b %-d, %Y}"


def preset(name: str, today: date | None = None) -> Period:
    today = today or timezone.localdate()
    first = today.replace(day=1)
    if name == "this_month":
        return Period(first, today, name)
    if name == "last_month":
        end = first - timedelta(days=1)
        return Period(end.replace(day=1), end, name)
    if name == "this_year":
        return Period(today.replace(month=1, day=1), today, name)
    if name == "last_year":
        return Period(date(today.year - 1, 1, 1), date(today.year - 1, 12, 31), name)
    if name == "last_12_months":
        # This month and the 11 before it.
        year, month = today.year, today.month - 11
        if month <= 0:
            year, month = year - 1, month + 12
        return Period(date(year, month, 1), today, name)
    raise ValidationError({"period": "Unknown period."})


def from_params(params: dict[str, str], today: date | None = None) -> Period:
    """`?period=last_month`, or `?from=2026-01-01&to=2026-03-31`. Default: this month."""
    start, end = params.get("from"), params.get("to")
    if start or end:
        try:
            s = date.fromisoformat(start or "")
            e = date.fromisoformat(end or "")
        except ValueError as exc:
            raise ValidationError({"from": "Use dates like 2026-01-31."}) from exc
        if e < s:
            raise ValidationError({"to": "The end date is before the start date."})
        if (e - s).days > MAX_DAYS:
            raise ValidationError({"to": "Pick five years or less."})
        return Period(s, e)
    return preset(params.get("period") or "this_month", today)
