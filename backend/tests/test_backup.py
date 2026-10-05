"""Backups run the real pg_dump and age binaries against the test database.
S3 is replaced by a fake that writes to a temp folder."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from django.db import connection

from apps.ops import backup
from apps.ops.models import BackupRun

pytestmark = pytest.mark.skipif(
    not (shutil.which("pg_dump") and shutil.which("age") and shutil.which("pg_restore")),
    reason="pg_dump, pg_restore and age are required",
)


class FakeS3:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.objects: dict[str, bytes] = {}

    def upload_file(self, path: str, bucket: str, key: str) -> None:
        self.objects[f"{bucket}/{key}"] = Path(path).read_bytes()

    def put_object(self, Bucket: str, Key: str, Body: bytes, **kw: Any) -> None:  # noqa: N803
        self.objects[f"{Bucket}/{Key}"] = Body


@pytest.fixture
def db_url(settings: Any) -> None:
    s = connection.settings_dict
    settings.BACKUP_DATABASE_URL = (
        f"postgres://{s['USER']}:{s['PASSWORD']}@{s['HOST'] or 'localhost'}:{s['PORT'] or 5432}/{s['NAME']}"
    )


@pytest.fixture
def age_key(tmp_path: Path) -> tuple[str, Path]:
    key_file = tmp_path / "key.txt"
    subprocess.run(["age-keygen", "-o", str(key_file)], check=True, capture_output=True)
    public = next(
        line.split(": ", 1)[1]
        for line in key_file.read_text().splitlines()
        if line.startswith("# public key")
    )
    return public, key_file


@pytest.mark.django_db
def test_encrypted_backup_round_trip(
    settings: Any, db_url: None, age_key: tuple[str, Path], tmp_path: Path, monkeypatch: Any
) -> None:
    public, key_file = age_key
    settings.BACKUP_AGE_RECIPIENT = public
    fake = FakeS3(tmp_path)
    monkeypatch.setattr(backup, "backup_client", lambda: fake)

    run = backup.run_database_backup()

    assert run.status == BackupRun.Status.SUCCEEDED
    assert run.object_key.endswith(".dump.age")
    assert run.row_counts and "accounts_user" in run.row_counts
    dump_bytes = fake.objects[f"{settings.BACKUP_BUCKET}/{run.object_key}"]
    assert dump_bytes.startswith(b"age-encryption.org/v1")

    enc = tmp_path / "db.dump.age"
    enc.write_bytes(dump_bytes)
    plain = tmp_path / "db.dump"
    subprocess.run(["age", "-d", "-i", str(key_file), "-o", str(plain), str(enc)], check=True)
    listing = subprocess.run(["pg_restore", "--list", str(plain)], check=True, capture_output=True, text=True)
    assert "TABLE DATA public accounts_user" in listing.stdout

    manifest_key = run.object_key.replace(".dump.age", ".counts.json")
    manifest = json.loads(fake.objects[f"{settings.BACKUP_BUCKET}/{manifest_key}"])
    assert manifest["row_counts"] == run.row_counts
    assert manifest["encrypted"] is True

    # Idempotent: a second run on the same day does nothing new.
    again = backup.run_database_backup()
    assert again.pk == run.pk


@pytest.mark.django_db
def test_production_refuses_unencrypted_backup(settings: Any) -> None:
    settings.BACKUP_AGE_RECIPIENT = ""
    settings.APP_ENV = "production"
    with pytest.raises(backup.BackupError, match="BACKUP_AGE_RECIPIENT"):
        backup.run_database_backup()


@pytest.mark.django_db
def test_failed_backup_is_recorded(settings: Any, db_url: None, tmp_path: Path, monkeypatch: Any) -> None:
    settings.BACKUP_AGE_RECIPIENT = ""

    class Broken(FakeS3):
        def upload_file(self, *a: Any, **kw: Any) -> None:
            raise OSError("bucket unreachable")

    monkeypatch.setattr(backup, "backup_client", lambda: Broken(tmp_path))
    with pytest.raises(OSError, match="bucket unreachable"):
        backup.run_database_backup()
    run = BackupRun.objects.get()
    assert run.status == BackupRun.Status.FAILED
    assert "bucket unreachable" in run.error


class FakeListing:
    def __init__(self, contents: list[dict[str, Any]]) -> None:
        self.contents = contents

    def paginate(self, **kw: Any) -> list[dict[str, Any]]:
        return [{"Contents": self.contents}]


@pytest.mark.django_db
def test_media_replication_copies_only_new_or_changed(monkeypatch: Any) -> None:
    from datetime import UTC, datetime

    old = datetime(2026, 1, 1, tzinfo=UTC)
    new = datetime(2026, 2, 1, tzinfo=UTC)
    copied: list[str] = []

    class Src:
        def get_paginator(self, name: str) -> FakeListing:
            return FakeListing(
                [
                    {"Key": "units/a.jpg", "Size": 10, "LastModified": old},
                    {"Key": "units/b.jpg", "Size": 20, "LastModified": new},
                    {"Key": "units/c.jpg", "Size": 30, "LastModified": new},
                ]
            )

        def get_object(self, Bucket: str, Key: str) -> dict[str, Any]:  # noqa: N803
            return {"Body": b"data"}

    class Dest:
        def get_paginator(self, name: str) -> FakeListing:
            return FakeListing(
                [
                    {"Key": "media/test/units/a.jpg", "Size": 10, "LastModified": new},
                    {"Key": "media/test/units/b.jpg", "Size": 20, "LastModified": old},
                ]
            )

        def upload_fileobj(self, body: Any, bucket: str, key: str) -> None:
            copied.append(key)

    monkeypatch.setattr(backup, "media_client", lambda: Src())
    monkeypatch.setattr(backup, "backup_client", lambda: Dest())
    run = backup.run_media_replication()
    assert run.status == BackupRun.Status.SUCCEEDED
    assert run.objects_copied == 2
    assert sorted(copied) == ["media/test/units/b.jpg", "media/test/units/c.jpg"]


@pytest.mark.django_db
def test_backup_rows_cannot_be_hard_deleted() -> None:
    from django.db import DatabaseError, transaction

    BackupRun.objects.create(kind="database")
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cur:
        cur.execute("DELETE FROM ops_backuprun")
