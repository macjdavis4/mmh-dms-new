"""/api/v1/dashboard and /api/v1/reports. Tested in tests/test_reports.py."""

from __future__ import annotations

import csv
import io
from typing import Any

from django.http import HttpResponse
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAuthenticatedAndVerified
from apps.core.api import flag_enabled

from . import definitions  # noqa: F401  (registers the reports)
from .dashboard import as_json, tiles_for
from .periods import PRESETS, from_params
from .registry import REPORTS, Report, cell, csv_text


def _available(report: Report, user: Any) -> bool:
    return all(flag_enabled(f, user) for f in report.flags)


def _summary(report: Report) -> dict[str, Any]:
    return {
        "key": report.key,
        "title": report.title,
        "description": report.description,
        "group": report.group,
        "uses_period": report.uses_period,
    }


class DashboardView(APIView):
    permission_classes = [IsAuthenticatedAndVerified]

    def get(self, request: Request) -> Response:
        return Response({"tiles": as_json(tiles_for(request.user))})


class ReportListView(APIView):
    """The reports this person may run."""

    permission_classes = [IsAuthenticatedAndVerified]

    def get(self, request: Request) -> Response:
        if not flag_enabled("reports", request.user):
            raise NotFound("This feature is turned off.")
        role = getattr(request.user, "role", "")
        reports = [
            _summary(r) for r in REPORTS.values() if role in r.roles and _available(r, request.user)
        ]
        return Response(
            {"reports": reports, "periods": [{"value": k, "label": v} for k, v in PRESETS.items()]}
        )


class ReportView(APIView):
    """One report: `?period=last_month` or `?from=...&to=...`. `?download=csv`
    downloads it (DRF keeps `?format=` for itself)."""

    permission_classes = [IsAuthenticatedAndVerified]

    def get(self, request: Request, key: str) -> Response | HttpResponse:
        report = REPORTS.get(key)
        if (
            report is None
            or not flag_enabled("reports", request.user)
            or not _available(report, request.user)
        ):
            raise NotFound("No such report.")
        role = getattr(request.user, "role", "")
        if role not in report.roles:
            raise PermissionDenied("You don't have access to this report.")
        period = from_params(request.query_params)
        result = report.run(period, role)
        columns = report.columns_for(role)
        keys = {c.key for c in columns}
        if request.query_params.get("download") == "csv":
            return _csv(report, period, columns, result)
        return Response(
            {
                **_summary(report),
                "period": {
                    "from": period.start.isoformat() if report.uses_period else None,
                    "to": period.end.isoformat() if report.uses_period else None,
                    "preset": period.preset if report.uses_period else "",
                    "label": period.label if report.uses_period else "Today",
                },
                "generated_at": timezone.now().isoformat(),
                "columns": [
                    {"key": c.key, "label": c.label, "kind": c.kind, "primary": c.primary}
                    for c in columns
                ],
                "rows": [
                    {
                        **{c.key: cell(row.get(c.key), c.kind) for c in columns},
                        "_to": row.get("_to", ""),
                    }
                    for row in result.rows
                ],
                "totals": {
                    k: cell(v, next(c.kind for c in columns if c.key == k))
                    for k, v in result.totals.items()
                    if k in keys and v is not None
                },
                "notes": result.notes,
            }
        )


def _csv(report: Report, period: Any, columns: list[Any], result: Any) -> HttpResponse:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([c.label for c in columns])
    for row in result.rows:
        writer.writerow([csv_text(cell(row.get(c.key), c.kind)) for c in columns])
    if result.totals:
        writer.writerow(
            [
                csv_text(cell(result.totals.get(c.key), c.kind)) if c.key in result.totals else ""
                for c in columns
            ]
        )
    stamp = f"{period.start}-to-{period.end}" if report.uses_period else f"{timezone.localdate()}"
    response = HttpResponse("﻿" + buf.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{report.key}-{stamp}.csv"'
    response["Cache-Control"] = "private, no-store"
    return response
