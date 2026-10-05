from __future__ import annotations

from typing import Any

from django.db.models import Count, Prefetch, Q, QuerySet
from rest_framework import viewsets
from rest_framework.permissions import BasePermission

from apps.core.api import RequiresFlag, SoftDeleteViewSetMixin

from .models import Address, Contact, Customer
from .permissions import CanEditCustomers, CanRemoveCustomers
from .serializers import (
    AddressSerializer,
    ContactSerializer,
    CustomerListSerializer,
    CustomerSerializer,
)

FLAG = RequiresFlag("customers-units")
ORDERINGS = {"name": "name", "-name": "-name", "newest": "-created_at", "units": "-unit_count"}


class CustomerViewSet(SoftDeleteViewSetMixin, viewsets.ModelViewSet[Customer]):
    model = Customer
    http_method_names = ["get", "post", "patch", "delete", "options"]

    def get_permissions(self) -> list[BasePermission]:
        if self.action in ("destroy", "restore"):
            return [FLAG(), CanRemoveCustomers()]
        return [FLAG(), CanEditCustomers()]

    def get_serializer_class(self) -> Any:
        return CustomerListSerializer if self.action == "list" else CustomerSerializer

    def get_queryset(self) -> QuerySet[Customer]:
        qs = self.base_queryset().annotate(
            unit_count=Count(
                "ownerships",
                filter=Q(
                    ownerships__end_date__isnull=True,
                    ownerships__deleted_at__isnull=True,
                    ownerships__unit__deleted_at__isnull=True,
                ),
                distinct=True,
            )
        )
        if self.action == "list":
            qs = qs.prefetch_related(
                Prefetch("contacts", queryset=Contact.objects.all()),
                Prefetch("addresses", queryset=Address.objects.all()),
            )
            params = self.request.query_params
            if q := params.get("q", "").strip():
                qs = qs.filter(
                    Q(name__icontains=q)
                    | Q(account_number__icontains=q)
                    | Q(phone__icontains=q)
                    | Q(email__icontains=q)
                    | Q(addresses__city__icontains=q, addresses__deleted_at__isnull=True)
                    | Q(contacts__last_name__icontains=q, contacts__deleted_at__isnull=True)
                    | Q(contacts__first_name__icontains=q, contacts__deleted_at__isnull=True)
                ).distinct()
            if kind := params.get("kind"):
                qs = qs.filter(kind=kind)
            qs = qs.order_by(ORDERINGS.get(params.get("ordering", "name"), "name"), "id")
        return qs


class _ChildViewSet(SoftDeleteViewSetMixin, viewsets.ModelViewSet[Any]):
    http_method_names = ["get", "post", "patch", "delete", "options"]

    def get_permissions(self) -> list[BasePermission]:
        return [FLAG(), CanEditCustomers()]

    def get_queryset(self) -> Any:
        qs = self.base_queryset().filter(customer__deleted_at__isnull=True)
        if customer := self.request.query_params.get("customer"):
            qs = qs.filter(customer_id=customer)
        return qs


class ContactViewSet(_ChildViewSet):
    model = Contact
    serializer_class = ContactSerializer


class AddressViewSet(_ChildViewSet):
    model = Address
    serializer_class = AddressSerializer
