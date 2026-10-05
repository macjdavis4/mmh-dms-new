"""Nightly off-site backups.

Database: pg_dump (custom format) of a consistent snapshot, encrypted with
`age` to a public key, uploaded to the backup bucket in a second region. Row
counts are taken inside the same snapshot and stored next to the dump, so
the monthly restore test can prove the restore is complete.

Media: copies new or changed objects from the media bucket to the backup
bucket (second region). The media bucket also has versioning turned on.

Both are idempotent: a day that already has a successful run is skipped,
and re-running after a failure simply tries again.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote, urlparse

import boto3
import psycopg
from django.conf import settings
from django.utils import timezone
from psycopg import sql

from .models import BackupRun

logger = logging.getLogger("mmh.backup")


class BackupError(RuntimeError):
    pass


def backup_client() -> Any:
    return boto3.client(
        "s3",
        endpoint_url=settings.BACKUP_S3_ENDPOINT_URL,
        region_name=settings.BACKUP_S3_REGION,
        aws_access_key_id=settings.BACKUP_S3_ACCESS_KEY_ID,
        aws_secret_access_key=settings.BACKUP_S3_SECRET_ACCESS_KEY,
    )


def media_client() -> Any:
    opts = settings.STORAGES["default"]["OPTIONS"]
    return boto3.client(
        "s3",
        endpoint_url=opts["endpoint_url"],
        region_name=opts["region_name"],
        aws_access_key_id=opts["access_key"],
        aws_secret_access_key=opts["secret_key"],
    )


@dataclass
class PgParams:
    conninfo: str
    env: dict[str, str]


def _pg_params() -> PgParams:
    """Connection settings for pg_dump, from BACKUP_DATABASE_URL (a direct,
    non-pooled connection: snapshots cannot be shared through PgBouncer)."""
    url = urlparse(settings.BACKUP_DATABASE_URL)
    env = {
        "PGHOST": url.hostname or "localhost",
        "PGPORT": str(url.port or 5432),
        "PGUSER": unquote(url.username or ""),
        "PGPASSWORD": unquote(url.password or ""),
        "PGDATABASE": url.path.lstrip("/"),
    }
    if root := os.environ.get("DATABASE_SSLROOTCERT"):
        env["PGSSLMODE"] = os.environ.get("DATABASE_SSLMODE", "require")
        env["PGSSLROOTCERT"] = root
    conninfo = " ".join(
        f"{k}={v!r}"
        for k, v in {
            "host": env["PGHOST"],
            "port": env["PGPORT"],
            "user": env["PGUSER"],
            "password": env["PGPASSWORD"],
            "dbname": env["PGDATABASE"],
            **({"sslmode": env["PGSSLMODE"], "sslrootcert": env["PGSSLROOTCERT"]} if root else {}),
        }.items()
    )
    return PgParams(conninfo=conninfo, env=env)


def _count_rows(cur: psycopg.Cursor[Any]) -> dict[str, int]:
    cur.execute(
        "SELECT schemaname, relname FROM pg_stat_user_tables "
        "WHERE schemaname = 'public' ORDER BY relname"
    )
    tables = [row[1] for row in cur.fetchall()]
    counts: dict[str, int] = {}
    for table in tables:
        cur.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier("public", table)))
        row = cur.fetchone()
        counts[table] = int(row[0]) if row else 0
    return counts


def run_database_backup(force: bool = False) -> BackupRun:
    today = timezone.localdate()
    if (
        not force
        and BackupRun.objects.filter(
            kind=BackupRun.Kind.DATABASE, run_date=today, status=BackupRun.Status.SUCCEEDED
        ).exists()
    ):
        logger.info("database backup already done today; skipping")
        return BackupRun.objects.filter(
            kind=BackupRun.Kind.DATABASE, run_date=today, status=BackupRun.Status.SUCCEEDED
        ).get()

    recipient = settings.BACKUP_AGE_RECIPIENT
    encrypted = bool(recipient)
    if not encrypted and settings.APP_ENV in {"staging", "production"}:
        raise BackupError(
            "BACKUP_AGE_RECIPIENT is required: refusing to write an unencrypted backup"
        )

    run = BackupRun.objects.create(kind=BackupRun.Kind.DATABASE, run_date=today)
    stamp = timezone.now().strftime("%Y%m%dT%H%M%SZ")
    prefix = f"db/{settings.APP_ENV}/{today:%Y/%m/%d}"
    dump_key = f"{prefix}/mmh-{settings.APP_ENV}-{stamp}.dump" + (".age" if encrypted else "")
    counts_key = f"{prefix}/mmh-{settings.APP_ENV}-{stamp}.counts.json"
    params = _pg_params()

    try:
        with tempfile.TemporaryDirectory(prefix="mmh-backup-") as tmp:
            out_path = os.path.join(tmp, "dump")
            # Hold a repeatable-read snapshot open; count rows in it and have
            # pg_dump read the very same snapshot.
            with psycopg.connect(params.conninfo, autocommit=False) as conn, conn.cursor() as cur:
                cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                cur.execute("SELECT pg_export_snapshot()")
                snap_row = cur.fetchone()
                assert snap_row is not None
                snapshot = snap_row[0]
                counts = _count_rows(cur)
                env = {**os.environ, **params.env}
                dump_cmd = [
                    "pg_dump",
                    "--format=custom",
                    "--no-owner",
                    "--no-privileges",
                    f"--snapshot={snapshot}",
                ]
                with open(out_path, "wb") as out:
                    if encrypted:
                        dump = subprocess.Popen(dump_cmd, env=env, stdout=subprocess.PIPE)
                        enc = subprocess.run(
                            ["age", "--encrypt", "--recipient", recipient],
                            stdin=dump.stdout,
                            stdout=out,
                            check=False,
                        )
                        assert dump.stdout is not None
                        dump.stdout.close()
                        dump_rc = dump.wait()
                        if dump_rc != 0 or enc.returncode != 0:
                            raise BackupError(f"pg_dump exit {dump_rc}, age exit {enc.returncode}")
                    else:
                        result = subprocess.run(dump_cmd, env=env, stdout=out, check=False)
                        if result.returncode != 0:
                            raise BackupError(f"pg_dump exit {result.returncode}")
                conn.rollback()

            size = os.path.getsize(out_path)
            if size == 0:
                raise BackupError("pg_dump produced an empty file")
            client = backup_client()
            client.upload_file(out_path, settings.BACKUP_BUCKET, dump_key)
            manifest = {
                "dump_key": dump_key,
                "encrypted": encrypted,
                "environment": settings.APP_ENV,
                "created_at": timezone.now().isoformat(),
                "row_counts": counts,
            }
            client.put_object(
                Bucket=settings.BACKUP_BUCKET,
                Key=counts_key,
                Body=json.dumps(manifest, indent=2).encode(),
                ContentType="application/json",
            )
    except Exception as exc:
        run.status = BackupRun.Status.FAILED
        run.error = str(exc)[:2000]
        run.finished_at = timezone.now()
        run.save()
        logger.exception("database backup failed")
        raise

    run.status = BackupRun.Status.SUCCEEDED
    run.object_key = dump_key
    run.size_bytes = size
    run.row_counts = counts
    run.finished_at = timezone.now()
    run.save()
    logger.info("database backup done", extra={"key": dump_key, "bytes": size})
    return run


def run_media_replication() -> BackupRun:
    """Copy new or changed media objects to the second-region backup bucket."""
    today = timezone.localdate()
    run = BackupRun.objects.create(kind=BackupRun.Kind.MEDIA, run_date=today)
    src_bucket = settings.STORAGES["default"]["OPTIONS"]["bucket_name"]
    dest_prefix = f"media/{settings.APP_ENV}/"
    src = media_client()
    dest = backup_client()
    copied = 0
    total = 0
    try:
        existing: dict[str, Any] = {}
        for page in dest.get_paginator("list_objects_v2").paginate(
            Bucket=settings.BACKUP_BUCKET, Prefix=dest_prefix
        ):
            for obj in page.get("Contents", []):
                existing[obj["Key"][len(dest_prefix) :]] = obj
        for page in src.get_paginator("list_objects_v2").paginate(Bucket=src_bucket):
            for obj in page.get("Contents", []):
                total += 1
                key = obj["Key"]
                have = existing.get(key)
                if (
                    have
                    and have["Size"] == obj["Size"]
                    and have["LastModified"] >= obj["LastModified"]
                ):
                    continue
                body = src.get_object(Bucket=src_bucket, Key=key)["Body"]
                dest.upload_fileobj(body, settings.BACKUP_BUCKET, dest_prefix + key)
                copied += 1
    except Exception as exc:
        run.status = BackupRun.Status.FAILED
        run.error = str(exc)[:2000]
        run.finished_at = timezone.now()
        run.save()
        logger.exception("media replication failed")
        raise
    run.status = (
        BackupRun.Status.SUCCEEDED
        if not BackupRun.objects.filter(
            kind=BackupRun.Kind.MEDIA, run_date=today, status=BackupRun.Status.SUCCEEDED
        ).exists()
        else BackupRun.Status.SKIPPED
    )
    run.objects_copied = copied
    run.finished_at = timezone.now()
    run.save()
    logger.info("media replication done", extra={"copied": copied, "total": total})
    return run
