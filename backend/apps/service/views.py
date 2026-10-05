from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model
from django.db.models import DecimalField, Q, QuerySet, Sum, Value
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.permissions import HasRole
from apps.accounts.roles import Role
from apps.core.api import RequiresFlag, SoftDeleteViewSetMixin
from apps.core.pdf import pdf_response
from apps.units.models import OwnershipRecord

from . import maintenance, services
from .models import LaborLine, MaintenancePlan, WorkOrder
from .pdf import work_order_pdf
from .serializers import (
    LaborCreateSerializer,
    LaborSerializer,
    MaintenancePlanSerializer,
    StatusSerializer,
    WorkOrderListSerializer,
    WorkOrderSerializer,
)

FLAG = RequiresFlag("service")

# Who may do what (enforced here; tested in tests/test_service.py).
CanEditWorkOrders = HasRole(
    Role.ADMIN, Role.SERVICE, read_roles=(Role.SALES, Role.PARTS, Role.READ_ONLY)
)
CanRemoveWorkOrders = HasRole(Role.ADMIN)

SCOPES = {
    "open": Q(status__in=WorkOrder.OPEN_STATUSES),
    "completed": Q(status=WorkOrder.Status.COMPLETED),
    "cancelled": Q(status=WorkOrder.Status.CANCELLED),
    "all": Q(),
}
ORDERINGS = {
    "newest": ["-opened_on", "-number"],
    "oldest": ["opened_on", "number"],
    "due": ["due_on", "opened_on"],
    "number": ["-number"],
}


class WorkOrderViewSet(SoftDeleteViewSetMixin, viewsets.ModelViewSet[WorkOrder]):
    model = WorkOrder
    http_method_names = ["get", "post", "patch", "delete", "options"]

    def get_permissions(self) -> list[BasePermission]:
        if self.action in ("destroy", "restore"):
            return [FLAG(), CanRemoveWorkOrders()]
        return [FLAG(), CanEditWorkOrders()]

    def get_serializer_class(self) -> Any:
        return WorkOrderListSerializer if self.action == "list" else WorkOrderSerializer

    def get_queryset(self) -> QuerySet[WorkOrder]:
        qs = (
            self.base_queryset()
            .select_related("unit", "customer", "assigned_to", "hour_reading", "created_by")
            .annotate(
                labor_hours=Coalesce(
                    Sum("labor__hours", filter=Q(labor__deleted_at__isnull=True)),
                    Value(0),
                    output_field=DecimalField(max_digits=8, decimal_places=2),
                )
            )
        )
        if self.action != "list":
            return qs
        p = self.request.query_params
        qs = qs.filter(SCOPES.get(p.get("scope", "open"), SCOPES["open"]))
        if unit := p.get("unit"):
            qs = qs.filter(unit_id=unit)
        if customer := p.get("customer"):
            qs = qs.filter(customer_id=customer)
        if kind := p.get("kind"):
            qs = qs.filter(kind=kind)
        if assigned := p.get("assigned"):
            qs = qs.filter(assigned_to=self.request.user if assigned == "me" else assigned)
        if q := p.get("q", "").strip():
            qs = qs.filter(
                Q(number__icontains=q)
                | Q(unit__serial_number__icontains=q)
                | Q(unit__model__icontains=q)
                | Q(customer__name__icontains=q)
                | Q(complaint__icontains=q)
            )
        return qs.order_by(*ORDERINGS.get(p.get("ordering", "newest"), ORDERINGS["newest"]))

    def _respond(
        self, work_order: WorkOrder, warning: str | None, code: int = status.HTTP_200_OK
    ) -> Response:
        fresh = self.get_queryset().get(pk=work_order.pk)
        body = dict(WorkOrderSerializer(fresh, context=self.get_serializer_context()).data)
        body["warning"] = warning
        return Response(body, status=code)

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        data = WorkOrderSerializer(data=request.data, context=self.get_serializer_context())
        data.is_valid(raise_exception=True)
        values = dict(data.validated_data)
        hours_given = "hours" in values
        hours = values.pop("hours", None)
        work_order = WorkOrder(**values)
        warning = services.save_work_order(work_order, hours=hours, hours_given=hours_given)
        return self._respond(work_order, warning, status.HTTP_201_CREATED)

    def partial_update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        work_order = self.get_object()
        if work_order.status == WorkOrder.Status.CANCELLED:
            raise serializers.ValidationError({"status": ["Reopen the work order to change it."]})
        data = WorkOrderSerializer(
            work_order, data=request.data, partial=True, context=self.get_serializer_context()
        )
        data.is_valid(raise_exception=True)
        values = dict(data.validated_data)
        hours_given = "hours" in values
        hours = values.pop("hours", None)
        for name, value in values.items():
            setattr(work_order, name, value)
        if work_order.status == WorkOrder.Status.COMPLETED and not work_order.correction.strip():
            raise serializers.ValidationError(
                {"correction": ["A completed work order needs the correction."]}
            )
        warning = services.save_work_order(work_order, hours=hours, hours_given=hours_given)
        return self._respond(work_order, warning)

    @action(detail=True, methods=["post"], url_path="status")
    def set_status(self, request: Request, pk: str | None = None) -> Response:
        work_order = self.get_object()
        data = StatusSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        updated = services.change_status(
            work_order, data.validated_data["status"], reason=data.validated_data["reason"]
        )
        return self._respond(updated, None)

    @action(detail=True, methods=["get", "post"])
    def labor(self, request: Request, pk: str | None = None) -> Response:
        work_order = self.get_object()
        if request.method == "GET":
            return Response(
                LaborSerializer(work_order.labor.select_related("mechanic"), many=True).data
            )
        data = LaborCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        line = services.add_labor(work_order, **data.validated_data)
        return Response(LaborSerializer(line).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def pdf(self, request: Request, pk: str | None = None) -> HttpResponse:
        """The printable work order (opens in the browser's PDF viewer)."""
        work_order = self.get_object()
        return pdf_response(work_order_pdf(work_order), f"{work_order.number}.pdf")

    @action(detail=False, methods=["get"])
    def mechanics(self, request: Request) -> Response:
        """People a work order can be assigned to, or labor logged for."""
        users = (
            get_user_model()
            .objects.filter(is_active=True, role__in=services.MECHANIC_ROLES)
            .order_by("first_name", "last_name")
        )
        return Response(
            [{"id": str(u.pk), "name": u.full_name or u.email, "role": u.role} for u in users]
        )

    @action(detail=False, methods=["get"])
    def counts(self, request: Request) -> Response:
        base = WorkOrder.objects.all()
        return Response(
            {
                "open": base.filter(SCOPES["open"]).count(),
                "mine": base.filter(SCOPES["open"], assigned_to=request.user).count(),
                "on_hold": base.filter(status=WorkOrder.Status.ON_HOLD).count(),
            }
        )


class LaborViewSet(
    SoftDeleteViewSetMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet[LaborLine],
):
    """Correct or remove a labor line (listing and adding happen per work order)."""

    model = LaborLine
    serializer_class = LaborSerializer
    http_method_names = ["patch", "delete", "post", "options"]

    def get_permissions(self) -> list[BasePermission]:
        return [FLAG(), HasRole(Role.ADMIN, Role.SERVICE)()]

    def get_queryset(self) -> QuerySet[LaborLine]:
        return self.base_queryset().select_related("mechanic", "work_order")

    def perform_update(self, serializer: Any) -> None:
        mechanic = serializer.validated_data.get("mechanic")
        if mechanic is not None:
            services.check_mechanic(mechanic)
        if serializer.instance.work_order.status == WorkOrder.Status.CANCELLED:
            raise serializers.ValidationError({"work_order": ["This work order is cancelled."]})
        serializer.save()


def _owners(unit_ids: set[Any]) -> dict[Any, str]:
    """Current owner's name per unit (blank for our stock)."""
    records = OwnershipRecord.objects.filter(
        unit_id__in=unit_ids, end_date__isnull=True
    ).select_related("customer")
    return {r.unit_id: (r.customer.name if r.customer else "") for r in records}


class MaintenancePlanViewSet(SoftDeleteViewSetMixin, viewsets.ModelViewSet[MaintenancePlan]):
    model = MaintenancePlan
    serializer_class = MaintenancePlanSerializer
    pagination_class = None
    http_method_names = ["get", "post", "patch", "delete", "options"]

    def get_permissions(self) -> list[BasePermission]:
        return [FLAG(), CanEditWorkOrders()]

    def get_queryset(self) -> QuerySet[MaintenancePlan]:
        qs = self.base_queryset().select_related("unit")
        if self.action == "list":
            unit = self.request.query_params.get("unit")
            if not unit:
                raise serializers.ValidationError({"unit": ["Say which unit."]})
            qs = qs.filter(unit_id=unit)
        return qs

    def get_serializer_context(self) -> dict[str, Any]:
        context = super().get_serializer_context()
        context.update(getattr(self, "_extra_context", {}))
        return context

    def _with_status(self, plans: list[MaintenancePlan]) -> dict[str, Any]:
        items = maintenance.statuses(plans)
        return {
            "statuses": {p.pk: st for p, st in items},
            "owners": _owners({p.unit_id for p in plans}),
        }

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        plans = list(self.get_queryset())
        self._extra_context = self._with_status(plans)
        return Response(self.get_serializer(plans, many=True).data)

    def retrieve(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        plan = self.get_object()
        self._extra_context = self._with_status([plan])
        return Response(self.get_serializer(plan).data)

    def perform_create(self, serializer: Any) -> None:
        serializer.save()
        self._extra_context = self._with_status([serializer.instance])

    def perform_update(self, serializer: Any) -> None:
        serializer.save()
        self._extra_context = self._with_status([serializer.instance])

    @action(detail=False, methods=["get"])
    def due(self, request: Request) -> Response:
        """Everything overdue or due within 30 days / 50 hours, most urgent first."""
        items = maintenance.due_list(include_ok=request.query_params.get("all") == "1")[:500]
        plans = [p for p, _ in items]
        self._extra_context = {
            "statuses": {p.pk: st for p, st in items},
            "owners": _owners({p.unit_id for p in plans}),
        }
        counts = {"overdue": 0, "due_soon": 0}
        for _, st in items:
            if st.state in counts:
                counts[st.state] += 1
        return Response({"counts": counts, "results": self.get_serializer(plans, many=True).data})

    @action(detail=True, methods=["post"], url_path="work-order")
    def work_order(self, request: Request, pk: str | None = None) -> Response:
        plan = self.get_object()
        if request.user.role not in ("admin", "service"):  # type: ignore[union-attr]
            raise PermissionDenied()
        work_order = maintenance.work_order_for(plan)
        return Response(
            WorkOrderSerializer(
                WorkOrder.objects.get(pk=work_order.pk), context=self.get_serializer_context()
            ).data,
            status=status.HTTP_201_CREATED,
        )
