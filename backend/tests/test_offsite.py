"""The locked off-site copy (apps/ops/offsite.py). The real thing was also
checked against an S3 server with Object Lock: uploads without Content-MD5
are refused there, and locked versions can't be deleted."""

from __future__ import annotations

import base64
import hashlib
import io
from typing import Any

import pytest
from django.utils import timezone

from apps.ops import offsite


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
    def __init__(self, store: dict[str, bytes]) -> None:
        self.store = store
        self.puts: list[dict[str, Any]] = []

    def get_paginator(self, name: str) -> Listing:
        return Listing(self.store)

    def get_object(self, Bucket: str, Key: str) -> dict[str, Any]:  # noqa: N803
        return {"Body": Body(self.store[Key])}

    def put_object(self, **kw: Any) -> None:
        data = kw["Body"].read()
        assert kw["ContentMD5"] == base64.b64encode(hashlib.md5(data).digest()).decode()  # noqa: S324
        self.puts.append(kw)
        self.store[kw["Key"]] = data


@pytest.fixture
def stores(settings: Any, monkeypatch: Any) -> dict[str, Store]:
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
        "offsite": Store({"test/media/units/a.jpg": b"a (copied before)"}),
    }
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


def test_md5_is_sent_for_a_large_spooled_body(stores: Any) -> None:
    offsite._put(stores["offsite"], "test/big", io.BytesIO(b"x" * 3_000_000))
    assert stores["offsite"].store["test/big"] == b"x" * 3_000_000
