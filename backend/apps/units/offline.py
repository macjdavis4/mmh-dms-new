"""The offline copy each phone or tablet keeps (Phase 13): our stock and
recently worked-on units, with their full spec cards. No costs, prices or
customer contact details; stock status follows the usual role rule. The app
stores it on the device for the signed-in person and wipes it at sign-out.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.db.models import Exists, OuterRef, Q
from django.utils import timezone
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.api import RequiresFlag
from apps.service.models import WorkOrder

from .models import HourMeterReading, Unit
from .serializers import UnitSerializer
from .views import FLAG, CanEditUnits, annotate_units

OFFLINE_FLAG = RequiresFlag("offline")
RECENT_DAYS = 90
MAX_UNITS = 600
# A saved copy older than this is not shown (the app deletes it).
KEEP_DAYS = 14
NO_MONEY = ("cost", "asking_price", "sale_price")


def offline_units() -> list[Unit]:
    since = timezone.now() - timedelta(days=RECENT_DAYS)
    recent_wo = WorkOrder.objects.filter(unit=OuterRef("pk")).filter(
        Q(opened_on__gte=since.date()) | Q(status__in=WorkOrder.OPEN_STATUSES)
    )
    recent_reading = HourMeterReading.objects.filter(
        unit=OuterRef("pk"), reading_date__gte=since.date()
    )
    qs = (
        annotate_units(Unit.objects.all())
        .annotate(has_wo=Exists(recent_wo), has_reading=Exists(recent_reading))
        .filter(
            Q(owner_kind="dealer")
            | Q(stock_status__in=("available", "on_hold", "in_prep"))
            | Q(updated_at__gte=since)
            | Q(has_wo=True)
            | Q(has_reading=True)
        )
        .prefetch_related("components", "forks", "attachments")
        .order_by("-updated_at")
    )
    return list(qs[:MAX_UNITS])


class OfflineUnitsView(APIView):
    """GET /api/v1/offline/units: the copy to keep on this device."""

    def get_permissions(self) -> list[BasePermission]:
        return [FLAG(), OFFLINE_FLAG(), CanEditUnits()]

    def get(self, request: Request) -> Response:
        context: dict[str, Any] = {"request": request}
        units = []
        for unit in offline_units():
            data = dict(UnitSerializer(unit, context=context).data)
            for name in NO_MONEY:
                data.pop(name, None)
            data["in_stock"] = getattr(unit, "owner_kind", None) == "dealer"
            units.append(data)
        response = Response(
            {
                "generated_at": timezone.now().isoformat(),
                "user_id": str(request.user.pk),
                "keep_days": KEEP_DAYS,
                "units": units,
            }
        )
        response["Cache-Control"] = "private, no-store"
        return response
