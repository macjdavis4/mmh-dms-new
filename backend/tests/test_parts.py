"""Phase 9: parts catalog (bins, reorder points, supersessions, cross references)."""

from typing import Any

import pytest
from django.db import DatabaseError, transaction
from rest_framework.test import APIClient

from apps.core.models import FeatureFlag
from apps.parts.models import Bin, CrossReference, Part, normalize_number

PARTS = "/api/v1/parts"
BINS = "/api/v1/bins"


def make_part(client: APIClient, **fields: Any) -> dict[str, Any]:
    body = {
        "manufacturer": "Hyundai",
        "part_number": "31N4-01050",
        "description": "Engine oil filter",
        "category": "filters",
        "cost": "9.80",
        "list_price": "18.50",
        "reorder_point": "6",
        "reorder_quantity": "12",
        "fits": "35LN-9A, 30L-9A",
        "cross_references": [{"manufacturer": "Donaldson", "part_number": "P55-0084"}],
        **fields,
    }
    res = client.post(PARTS, body, format="json")
    assert res.status_code == 201, res.json()
    return res.json()  # type: ignore[no-any-return]


def test_normalize_number() -> None:
    assert normalize_number("hy-31n4 01050") == "HY31N401050"
    assert normalize_number("  ") == ""


@pytest.mark.django_db
def test_create_part_with_bin_and_cross_reference(client_for: Any) -> None:
    parts = client_for("parts")
    bin_res = parts.post(BINS, {"code": "a-01-1", "description": "Filters"}, format="json")
    assert bin_res.status_code == 201, bin_res.json()
    assert bin_res.json()["code"] == "A-01-1"  # codes are kept upper case
    part = make_part(parts, bin=bin_res.json()["id"])
    assert part["bin_code"] == "A-01-1"
    assert part["cost"] == "9.80"
    assert part["category_label"] == "Filters"
    assert [c["part_number"] for c in part["cross_references"]] == ["P55-0084"]
    assert parts.get(BINS).json()[0]["part_count"] == 1


@pytest.mark.django_db
def test_duplicate_numbers_refused_ignoring_punctuation(client_for: Any) -> None:
    parts = client_for("parts")
    first = make_part(parts)
    res = parts.post(
        PARTS,
        {"manufacturer": "hyundai", "part_number": "31n4 01050", "description": "Same"},
        format="json",
    )
    assert res.status_code == 400
    assert "already in the catalog" in res.json()["fields"]["part_number"][0]
    # The same number from another maker is a different part.
    other = parts.post(
        PARTS,
        {"manufacturer": "Clark", "part_number": "31N4-01050", "description": "Clark filter"},
        format="json",
    )
    assert other.status_code == 201
    check = parts.get(f"{PARTS}/number-check?manufacturer=Hyundai&number=31n401050").json()
    assert check["duplicate"]["id"] == first["id"]
    assert [x["label"] for x in check["same_number"]] == ["Clark 31N4-01050"]
    # A removed part still holds its number: restore it instead.
    parts.delete(f"{PARTS}/{first['id']}")
    again = parts.post(
        PARTS,
        {"manufacturer": "Hyundai", "part_number": "31N4-01050", "description": "x"},
        format="json",
    )
    assert "restore it instead" in again.json()["fields"]["part_number"][0]


@pytest.mark.django_db
def test_search_by_number_cross_reference_and_words(client_for: Any) -> None:
    parts = client_for("parts")
    make_part(parts, vendor_part_number="VND-777")
    make_part(
        parts,
        part_number="31N4-40020",
        description="Brake shoe set",
        category="brakes",
        fits="50D-9",
        cross_references=[],
    )
    search = lambda q: [p["part_number"] for p in parts.get(f"{PARTS}?q={q}").json()["results"]]  # noqa: E731
    assert search("31n401050") == ["31N4-01050"]
    assert search("p550084") == ["31N4-01050"]  # cross reference, no dash
    assert search("VND-777") == ["31N4-01050"]
    assert search("brake shoe") == ["31N4-40020"]
    assert search("35LN") == ["31N4-01050"]  # what it fits
    assert [p["part_number"] for p in parts.get(f"{PARTS}?category=brakes").json()["results"]] == [
        "31N4-40020"
    ]
    found = client_for("service").get("/api/v1/search?q=P55-0084").json()["groups"]["part"]
    assert found[0]["title"] == "31N4-01050 · Engine oil filter"


@pytest.mark.django_db
def test_supersession_chain(client_for: Any) -> None:
    parts = client_for("parts")
    old = make_part(parts, part_number="XKBH-00117", cross_references=[])
    mid = make_part(parts, part_number="XKBH-00117A", cross_references=[])
    new = make_part(parts, part_number="XKBH-00117B", cross_references=[])
    res = parts.patch(f"{PARTS}/{old['id']}", {"superseded_by": mid["id"]}, format="json")
    assert res.status_code == 200, res.json()
    assert res.json()["superseded_on"]  # dated today
    parts.patch(f"{PARTS}/{mid['id']}", {"superseded_by": new["id"]}, format="json")
    detail = parts.get(f"{PARTS}/{old['id']}").json()
    assert detail["superseded_by_summary"]["part_number"] == "XKBH-00117A"
    assert detail["current_part"]["part_number"] == "XKBH-00117B"  # end of the chain
    assert [s["part_number"] for s in parts.get(f"{PARTS}/{mid['id']}").json()["supersedes"]] == [
        "XKBH-00117"
    ]
    # Replaced parts are hidden from the list unless asked for.
    listed = [p["part_number"] for p in parts.get(f"{PARTS}?q=XKBH").json()["results"]]
    assert listed == ["XKBH-00117B"]
    assert parts.get(f"{PARTS}?q=XKBH&replaced=1").json()["count"] == 3
    # No circles, no replacing itself.
    circle = parts.patch(f"{PARTS}/{new['id']}", {"superseded_by": old["id"]}, format="json")
    assert circle.status_code == 400
    assert "circle" in circle.json()["fields"]["superseded_by"][0]
    itself = parts.patch(f"{PARTS}/{new['id']}", {"superseded_by": new["id"]}, format="json")
    assert itself.status_code == 400
    # A part others point to can't be removed.
    assert parts.delete(f"{PARTS}/{new['id']}").status_code == 400
    # Clearing the replacement clears the date.
    cleared = parts.patch(f"{PARTS}/{old['id']}", {"superseded_by": None}, format="json").json()
    assert cleared["superseded_on"] is None


@pytest.mark.django_db
def test_cross_references_sync(client_for: Any) -> None:
    parts = client_for("parts")
    part = make_part(parts)
    keep = part["cross_references"][0]
    res = parts.patch(
        f"{PARTS}/{part['id']}",
        {"cross_references": [keep, {"manufacturer": "Fleetguard", "part_number": "LF-3345X"}]},
        format="json",
    )
    assert [c["part_number"] for c in res.json()["cross_references"]] == ["P55-0084", "LF-3345X"]
    twice = parts.patch(
        f"{PARTS}/{part['id']}",
        {"cross_references": [{"part_number": "AB-1"}, {"part_number": "ab1"}]},
        format="json",
    )
    assert twice.status_code == 400
    parts.patch(f"{PARTS}/{part['id']}", {"cross_references": []}, format="json")
    assert CrossReference.objects.filter(part_id=part["id"]).count() == 0
    assert CrossReference.all_objects.filter(part_id=part["id"]).count() == 2  # soft deleted


@pytest.mark.django_db
def test_reorder_validation(client_for: Any) -> None:
    parts = client_for("parts")
    no_qty = parts.post(
        PARTS,
        {"part_number": "X1", "description": "x", "reorder_point": "2"},
        format="json",
    )
    assert "reorder_quantity" in no_qty.json()["fields"]
    zero = parts.post(
        PARTS,
        {"part_number": "X1", "description": "x", "reorder_point": "2", "reorder_quantity": "0"},
        format="json",
    )
    assert "reorder_quantity" in zero.json()["fields"]
    negative = parts.post(
        PARTS, {"part_number": "X1", "description": "x", "list_price": "-1"}, format="json"
    )
    assert "list_price" in negative.json()["fields"]
    blank = parts.post(PARTS, {"part_number": " - ", "description": "x"}, format="json")
    assert "part_number" in blank.json()["fields"]


@pytest.mark.django_db
def test_database_refuses_bad_parts() -> None:
    bin_ = Bin.objects.create(code="A-1")
    with pytest.raises(DatabaseError), transaction.atomic():
        Bin.objects.create(code="a-1")  # unique ignoring case
    part = Part.objects.create(part_number="P-1", description="x", bin=bin_)
    for field, value in (
        ("category", "nope"),
        ("cost", -1),
        ("reorder_quantity", 0),
        ("description", ""),
    ):
        fresh = Part.objects.get(pk=part.pk)
        setattr(fresh, field, value)
        with pytest.raises(DatabaseError), transaction.atomic():
            fresh.save()
    with pytest.raises(DatabaseError), transaction.atomic():
        part.superseded_by = part
        part.save()


@pytest.mark.django_db
def test_bins(client_for: Any) -> None:
    parts = client_for("parts")
    b = parts.post(BINS, {"code": "B-1"}, format="json").json()
    assert parts.post(BINS, {"code": "b-1"}, format="json").status_code == 400
    make_part(parts, bin=b["id"])
    assert parts.delete(f"{BINS}/{b['id']}").status_code == 400  # still has parts
    empty = parts.post(BINS, {"code": "B-2"}, format="json").json()
    assert parts.delete(f"{BINS}/{empty['id']}").status_code == 204
    assert parts.post(f"{BINS}/{empty['id']}/restore").status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("role", "can_edit", "sees_cost"),
    [
        ("admin", True, True),
        ("parts", True, True),
        ("sales", False, True),
        ("service", False, False),
        ("read_only", False, False),
    ],
)
def test_parts_role_matrix(client_for: Any, role: str, can_edit: bool, sees_cost: bool) -> None:
    part = make_part(client_for("parts"))
    client = client_for(role)
    listed = client.get(PARTS)
    assert listed.status_code == 200
    assert ("cost" in listed.json()["results"][0]) is sees_cost
    detail = client.get(f"{PARTS}/{part['id']}").json()
    assert ("cost" in detail) is sees_cost
    assert detail["list_price"] == "18.50"  # list prices are for everyone
    assert client.get(BINS).status_code == 200
    assert client.get(f"{PARTS}/facets").json()["can_see_cost"] is sees_cost
    created = client.post(PARTS, {"part_number": f"N-{role}", "description": "x"}, format="json")
    assert created.status_code == (201 if can_edit else 403)
    edit = client.patch(f"{PARTS}/{part['id']}", {"notes": role}, format="json")
    assert edit.status_code == (200 if can_edit else 403)
    assert client.post(BINS, {"code": f"Z-{role}"}, format="json").status_code == (
        201 if can_edit else 403
    )
    assert client.delete(f"{PARTS}/{part['id']}").status_code == (204 if can_edit else 403)


@pytest.mark.django_db
def test_cost_is_dropped_for_roles_that_cant_see_it(make_user: Any) -> None:
    """Belt and braces: even if such a role could write, cost would be ignored."""
    from apps.parts.serializers import PartSerializer

    class Request:
        user = make_user("service")

    data = PartSerializer(
        data={"part_number": "Q1", "description": "x", "cost": "5"},
        context={"request": Request()},
    )
    assert data.is_valid(), data.errors
    assert "cost" not in data.validated_data


@pytest.mark.django_db
def test_anonymous_and_flag(client_for: Any, anon_client: APIClient) -> None:
    assert anon_client.get(PARTS).status_code == 401
    flag = FeatureFlag.objects.get(key="parts")
    flag.enabled = False
    flag.save()
    assert client_for("admin").get(PARTS).status_code == 404
    assert client_for("admin").get("/api/v1/search?q=31N4").json()["groups"]["part"] == []


@pytest.mark.django_db
def test_demo_parts_load_once() -> None:
    from apps.parts.demo import load_demo_parts

    load_demo_parts()
    load_demo_parts()
    assert Part.objects.count() == 14
    old = Part.objects.get(part_number="XKBH-00117")
    assert old.superseded_by is not None
    assert old.current().part_number == "XKBH-00117A"
