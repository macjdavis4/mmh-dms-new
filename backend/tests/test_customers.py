from typing import Any

import pytest
from django.db import DatabaseError, transaction
from rest_framework.test import APIClient

from apps.customers.models import Address, Contact, Customer
from apps.search import registry

URL = "/api/v1/customers"


def make_customer(**kw: Any) -> Customer:
    return Customer.objects.create(**{"name": "Penobscot Paper Co.", **kw})


@pytest.mark.django_db
def test_create_customer_with_validation(client_for: Any) -> None:
    client = client_for("sales")
    blank = client.post(URL, {"name": "  "}, format="json")
    assert blank.status_code == 400
    assert "name" in blank.json()["fields"]
    res = client.post(
        URL,
        {"name": "Bangor Building Supply", "account_number": "BBS-001", "phone": "207-555-0100"},
        format="json",
    )
    assert res.status_code == 201, res.json()
    assert res.json()["contacts"] == []


@pytest.mark.django_db
def test_account_numbers_are_unique_ignoring_case(client_for: Any) -> None:
    make_customer(account_number="ACCT-9")
    res = client_for("sales").post(
        URL, {"name": "Other", "account_number": "acct-9"}, format="json"
    )
    assert res.status_code == 400
    assert "account_number" in res.json()["fields"]
    with pytest.raises(DatabaseError), transaction.atomic():
        Customer.objects.create(name="Sneaky", account_number="Acct-9")


@pytest.mark.django_db
def test_one_primary_contact_and_address(client_for: Any) -> None:
    client = client_for("service")
    customer = make_customer()
    first = client.post(
        "/api/v1/contacts",
        {
            "customer": str(customer.pk),
            "first_name": "Dana",
            "last_name": "Hale",
            "is_primary": True,
        },
        format="json",
    ).json()
    second = client.post(
        "/api/v1/contacts",
        {"customer": str(customer.pk), "first_name": "Lee", "is_primary": True},
        format="json",
    )
    assert second.status_code == 201
    assert Contact.objects.get(pk=first["id"]).is_primary is False
    assert Contact.objects.filter(customer=customer, is_primary=True).count() == 1

    nameless = client.post("/api/v1/contacts", {"customer": str(customer.pk)}, format="json")
    assert nameless.status_code == 400

    for city in ("Bangor", "Brewer"):
        res = client.post(
            "/api/v1/addresses",
            {"customer": str(customer.pk), "line1": "1 Mill St", "city": city, "is_primary": True},
            format="json",
        )
        assert res.status_code == 201
    assert Address.objects.get(customer=customer, is_primary=True).city == "Brewer"

    detail = client.get(f"{URL}/{customer.pk}").json()
    assert [c["first_name"] for c in detail["contacts"]][0] == "Lee"
    assert len(detail["addresses"]) == 2


@pytest.mark.django_db
def test_list_search_by_contact_and_city(client_for: Any) -> None:
    a = make_customer(name="Downeast Seafood")
    Contact.objects.create(customer=a, first_name="Robin", last_name="Gray")
    b = make_customer(name="Katahdin Lumber")
    Address.objects.create(customer=b, line1="5 Main", city="Millinocket")
    client = client_for("read_only")
    assert [r["name"] for r in client.get(URL + "?q=gray").json()["results"]] == [
        "Downeast Seafood"
    ]
    rows = client.get(URL + "?q=millinocket").json()["results"]
    assert [r["name"] for r in rows] == ["Katahdin Lumber"]
    assert rows[0]["city"] == "Millinocket, ME"


@pytest.mark.django_db
def test_soft_delete_and_restore(client_for: Any) -> None:
    customer = make_customer()
    sales = client_for("sales")
    assert client_for("service").delete(f"{URL}/{customer.pk}").status_code == 403
    assert sales.delete(f"{URL}/{customer.pk}").status_code == 204
    assert not Customer.objects.filter(pk=customer.pk).exists()
    assert Customer.all_objects.get(pk=customer.pk).is_deleted
    assert sales.get(URL + "?include_deleted=1").json()["count"] == 1
    assert sales.post(f"{URL}/{customer.pk}/restore").status_code == 200
    assert Customer.objects.filter(pk=customer.pk).exists()


@pytest.mark.django_db
def test_global_search_is_typo_tolerant(client_for: Any) -> None:
    make_customer(name="Penobscot Paper Co.", account_number="PPC-7")
    groups = client_for("parts").get("/api/v1/search?q=Penobscott").json()["groups"]
    assert groups["customer"][0]["title"] == "Penobscot Paper Co."
    assert groups["customer"][0]["url"].startswith("/customers/")
    assert "customer" in registry.registered_kinds()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("role", "can_write", "can_remove"),
    [
        ("admin", True, True),
        ("sales", True, True),
        ("service", True, False),
        ("parts", True, False),
        ("read_only", False, False),
    ],
)
def test_customer_role_matrix(
    client_for: Any, role: str, can_write: bool, can_remove: bool
) -> None:
    client: APIClient = client_for(role)
    customer = make_customer()
    assert client.get(URL).status_code == 200
    assert client.get(f"{URL}/{customer.pk}").status_code == 200
    created = client.post(URL, {"name": f"New {role}"}, format="json")
    assert created.status_code == (201 if can_write else 403)
    patched = client.patch(f"{URL}/{customer.pk}", {"phone": "1"}, format="json")
    assert patched.status_code == (200 if can_write else 403)
    removed = client.delete(f"{URL}/{customer.pk}")
    assert removed.status_code == (204 if can_remove else 403)


@pytest.mark.django_db
def test_anonymous_cannot_see_customers(anon_client: APIClient) -> None:
    assert anon_client.get(URL).status_code == 401
    assert anon_client.get("/api/v1/contacts").status_code == 401


@pytest.mark.django_db
def test_feature_flag_off_hides_customers(client_for: Any) -> None:
    from apps.core.models import FeatureFlag

    flag = FeatureFlag.objects.get(key="customers-units")
    flag.enabled = False
    flag.save()
    assert client_for("admin").get(URL).status_code == 404
