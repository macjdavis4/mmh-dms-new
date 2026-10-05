from __future__ import annotations

from typing import Any

from django.db import transaction
from rest_framework import serializers

from .models import Address, Contact, Customer


def _clear_primary(model: Any, customer: Any, instance: Any) -> None:
    """Only one primary contact/address per customer (also a DB constraint)."""
    customer = customer or getattr(instance, "customer", None)
    others = model.objects.filter(customer=customer, is_primary=True)
    if instance is not None:
        others = others.exclude(pk=instance.pk)
    for other in others:
        other.is_primary = False
        other.save()


class ContactSerializer(serializers.ModelSerializer[Contact]):
    full_name = serializers.CharField(source="__str__", read_only=True)

    class Meta:
        model = Contact
        fields = [
            "id",
            "customer",
            "first_name",
            "last_name",
            "full_name",
            "title",
            "phone",
            "mobile",
            "email",
            "is_primary",
            "notes",
            "is_deleted",
        ]
        read_only_fields = ["id", "is_deleted"]

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        first = attrs.get("first_name", getattr(self.instance, "first_name", ""))
        last = attrs.get("last_name", getattr(self.instance, "last_name", ""))
        if not (first or "").strip() and not (last or "").strip():
            raise serializers.ValidationError({"first_name": ["Enter a first or last name."]})
        return attrs

    def save(self, **kwargs: Any) -> Contact:
        with transaction.atomic():
            if self.validated_data.get("is_primary"):
                _clear_primary(Contact, self.validated_data.get("customer"), self.instance)
            return super().save(**kwargs)


class AddressSerializer(serializers.ModelSerializer[Address]):
    one_line = serializers.CharField(source="__str__", read_only=True)

    class Meta:
        model = Address
        fields = [
            "id",
            "customer",
            "kind",
            "label",
            "line1",
            "line2",
            "city",
            "state",
            "postal_code",
            "country",
            "is_primary",
            "notes",
            "one_line",
            "is_deleted",
        ]
        read_only_fields = ["id", "is_deleted"]

    def save(self, **kwargs: Any) -> Address:
        with transaction.atomic():
            if self.validated_data.get("is_primary"):
                _clear_primary(Address, self.validated_data.get("customer"), self.instance)
            return super().save(**kwargs)


class CustomerListSerializer(serializers.ModelSerializer[Customer]):
    primary_contact = serializers.SerializerMethodField()
    city = serializers.SerializerMethodField()
    unit_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Customer
        fields = [
            "id",
            "name",
            "kind",
            "account_number",
            "phone",
            "email",
            "primary_contact",
            "city",
            "unit_count",
            "is_deleted",
        ]

    def get_primary_contact(self, obj: Customer) -> str | None:
        contacts = [c for c in obj.contacts.all() if c.deleted_at is None]
        primary = next((c for c in contacts if c.is_primary), contacts[0] if contacts else None)
        return str(primary) if primary else None

    def get_city(self, obj: Customer) -> str | None:
        addresses = [a for a in obj.addresses.all() if a.deleted_at is None]
        primary = next((a for a in addresses if a.is_primary), addresses[0] if addresses else None)
        return f"{primary.city}, {primary.state}" if primary else None


class CustomerSerializer(serializers.ModelSerializer[Customer]):
    contacts = serializers.SerializerMethodField()
    addresses = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = [
            "id",
            "name",
            "kind",
            "account_number",
            "phone",
            "email",
            "website",
            "notes",
            "contacts",
            "addresses",
            "is_deleted",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "is_deleted", "created_at", "updated_at"]

    def get_contacts(self, obj: Customer) -> list[dict[str, Any]]:
        return ContactSerializer(obj.contacts.filter(deleted_at__isnull=True), many=True).data  # type: ignore[return-value]

    def get_addresses(self, obj: Customer) -> list[dict[str, Any]]:
        return AddressSerializer(obj.addresses.filter(deleted_at__isnull=True), many=True).data  # type: ignore[return-value]

    def validate_name(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Enter the customer's name.")
        return value

    def validate_account_number(self, value: str) -> str:
        value = value.strip()
        if value:
            qs = Customer.objects.filter(account_number__iexact=value)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    f"Account number {value} is already used by {qs.first()}."
                )
        return value
