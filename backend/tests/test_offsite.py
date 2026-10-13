"""The locked off-site copy (apps/ops/offsite.py). The real thing was also
checked against an S3 server with Object Lock: uploads without Content-MD5
are refused there, and locked versions can't be deleted.

The fake off-site store refuses listing and reading, like the write-only key."""

from __future__ import annotations

import base64
import hashlib
import io
from typing import Any

import pytest
from django.utils import timezone

from apps.ops import offsite
from apps.ops.models import OffsiteCopy


class Listing:
    def __init__(self, store: dict[str, bytes]) -> None:
        self.store = store

    def paginate(self, Bucket: str, Prefix: str = "") -> list[dict[str, Any]]:  # noqa: N803
        return [{"Contents": [{"Key": k} for k in sorted(self.store) if k.startswith(Prefix)]}]


class Body:
    def __init__(self, data: bytes) -> None:
        self.data = data

    def read(self) -> bytes:
        return self.data

    def iter_chunks(self, size: int) -> list[bytes]:
        return [self.data[i : i + size] for i in range(0, len(self.data), size)] or [b""]


class Store:
    def __init__(self, store: dict[str, bytes], *, write_only: bool = False) -> None:
        self.write_only = write_only
        self.store = store
        self.puts: list[dict[str, Any]] = []

    def get_paginator(self, name: str) -> Listing:
        assert not self.write_only, "the off-site key can't list"
        return Listing(self.store)

    def get_object(self, Bucket: str, Key: str) -> dict[str, Any]:  # noqa: N803
        assert not self.write_only, "the off-site key can't read"
        return {"Body": Body(self.store[Key])}

    def put_object(self, **kw: Any) -> None:
        data = kw["Body"].read()
        assert kw["ContentMD5"] == base64.b64encode(hashlib.md5(data).digest()).decode()  # noqa: S324
        self.puts.append(kw)
        self.store[kw["Key"]] = data


@pytest.fixture
def stores(settings: Any, monkeypatch: Any, db: Any) -> dict[str, Store]:
    settings.OFFSITE_BUCKET = "mmh-offsite"
    settings.OFFSITE_ENDPOINT_URL = "https://s3.us-east-005.backblazeb2.com"
    settings.OFFSITE_ACCESS_KEY_ID = "key"
    settings.OFFSITE_SECRET_ACCESS_KEY = "secret"
    day = timezone.localdate()
    old = day.replace(year=day.year - 1)
    s = {
        "backup": Store(
            {
                f"db/test/{day:%Y/%m/%d}/mmh-test-1.dump.age": b"dump" * 1000,
                f"db/test/{day:%Y/%m/%d}/mmh-test-1.counts.json": b"{}",
                f"db/test/{old:%Y/%m/%d}/mmh-test-0.dump.age": b"too old",
            }
        ),
        "media": Store({"units/a.jpg": b"a", "units/b.jpg": b"b"}),
        "offsite": Store({"test/media/units/a.jpg": b"a (copied before)"}, write_only=True),
    }
    OffsiteCopy.objects.create(key="test/media/units/a.jpg", size_bytes=1, md5="x")
    monkeypatch.setattr(offsite, "backup_client", lambda: s["backup"])
    monkeypatch.setattr(offsite, "media_client", lambda: s["media"])
    monkeypatch.setattr(offsite, "offsite_client", lambda: s["offsite"])
    return s


@pytest.mark.django_db
def test_copies_recent_dumps_and_new_media_only(stores: dict[str, Store]) -> None:
    result = offsite.run_offsite_copy()
    day = timezone.localdate()
    assert result.dumps_copied == 2
    assert result.media_copied == 1
    assert sorted(p["Key"] for p in stores["offsite"].puts) == [
        f"test/db/{day:%Y/%m/%d}/mmh-test-1.counts.json",
        f"test/db/{day:%Y/%m/%d}/mmh-test-1.dump.age",
        "test/media/units/b.jpg",
    ]
    # A file already copied is never sent again (the locked first copy stays).
    assert stores["offsite"].store["test/media/units/a.jpg"] == b"a (copied before)"
    # Each copy is recorded, with its size and checksum.
    copy = OffsiteCopy.objects.get(key="test/media/units/b.jpg")
    assert (copy.size_bytes, copy.md5) == (1, hashlib.md5(b"b").hexdigest())  # noqa: S324


@pytest.mark.django_db
def test_running_again_copies_nothing(stores: dict[str, Store]) -> None:
    offsite.run_offsite_copy()
    stores["offsite"].puts.clear()
    result = offsite.run_offsite_copy()
    assert (result.dumps_copied, result.media_copied) == (0, 0)
    assert stores["offsite"].puts == []


@pytest.mark.django_db
def test_does_nothing_until_set_up(settings: Any) -> None:
    settings.OFFSITE_BUCKET = ""
    assert offsite.run_offsite_copy() == offsite.OffsiteResult()


def test_region_comes_from_the_b2_endpoint(settings: Any) -> None:
    settings.OFFSITE_ENDPOINT_URL = "https://s3.us-west-004.backblazeb2.com"
    settings.OFFSITE_ACCESS_KEY_ID = "key"
    settings.OFFSITE_SECRET_ACCESS_KEY = "secret"
    assert offsite.offsite_client().meta.region_name == "us-west-004"


@pytest.mark.django_db
def test_copy_records_cannot_be_changed_or_deleted(stores: Any) -> None:
    from django.db import DatabaseError, transaction

    with pytest.raises(DatabaseError), transaction.atomic():
        OffsiteCopy.objects.all().delete()
    with pytest.raises(DatabaseError), transaction.atomic():
        OffsiteCopy.objects.update(md5="changed")


@pytest.mark.django_db
def test_md5_is_sent_for_a_large_spooled_body(stores: Any) -> None:
    offsite._put(stores["offsite"], "test/big", io.BytesIO(b"x" * 3_000_000))
    assert stores["offsite"].store["test/big"] == b"x" * 3_000_000


@pytest.mark.django_db
def test_admin_health_shows_the_off_site_copy(settings: Any, admin_client: Any) -> None:
    settings.OFFSITE_BUCKET = ""
    assert admin_client.get("/api/v1/admin/health").json()["offsite"] == {
        "enabled": False,
        "last_copied_at": None,
    }
    OffsiteCopy.objects.create(key="test/media/x.jpg", size_bytes=1, md5="x")
    assert admin_client.get("/api/v1/admin/health").json()["offsite"]["last_copied_at"]
