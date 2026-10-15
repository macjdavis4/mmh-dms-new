"""The locked off-site copy: Backblaze B2, outside our DigitalOcean account.

Everything else (the database, its backups, the photos and their backup
copy) lives in one DigitalOcean account, so a single stolen key could delete
it all. This copy can't be deleted that way:

* The B2 bucket has Object Lock on (compliance mode, 30 days): nobody can
  delete or overwrite a file for 30 days, not even with the account password.
* The key the server holds can only add files: it can't list, read or
  delete them. What has been sent is recorded here instead (OffsiteCopy).

Each night (after the database backup and the media copy) this job copies:

* every encrypted database dump (and its row-count manifest) from the last
  few days that isn't there yet: `<env>/db/YYYY/MM/DD/...`
* every photo or scan not sent before: `<env>/media/<name>`.
  Files already copied are never sent again: uploads always get new names,
  so a "changed" file is more likely ransomware than a real edit, and the
  locked first copy is the one worth keeping.

Idempotent and safe to retry: it only ever adds what hasn't been sent. (If
the database is ever restored to an older copy, some files are sent again;
the bucket then simply holds another locked version.)
"""

from __future__ import annotations

import base64
import hashlib
import io
import logging
import re
import tempfile
from dataclasses import dataclass
from datetime import timedelta
from typing import IO, Any

import boto3
from botocore.config import Config
from django.conf import settings
from django.utils import timezone

from .backup import backup_client, media_client
from .models import OffsiteCopy

logger = logging.getLogger("mmh.backup")

DB_DAYS = 7  # catch up on this many days of dumps after a failure


class OffsiteError(RuntimeError):
    pass


def enabled() -> bool:
    return bool(
        settings.OFFSITE_BUCKET
        and settings.OFFSITE_ENDPOINT_URL
        and settings.OFFSITE_ACCESS_KEY_ID
        and settings.OFFSITE_SECRET_ACCESS_KEY
    )


def offsite_client() -> Any:
    endpoint = settings.OFFSITE_ENDPOINT_URL
    # B2's S3 endpoints name their region: https://s3.us-east-005.backblazeb2.com
    match = re.match(r"https?://s3\.([a-z0-9-]+)\.", endpoint)
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name=match.group(1) if match else "us-east-1",
        aws_access_key_id=settings.OFFSITE_ACCESS_KEY_ID,
        aws_secret_access_key=settings.OFFSITE_SECRET_ACCESS_KEY,
        # A bucket with Object Lock needs Content-MD5 on every upload; we send
        # it ourselves rather than the newer checksum headers.
        config=Config(
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
            retries={"max_attempts": 5, "mode": "standard"},
        ),
    )


def _prefix() -> str:
    return f"{settings.APP_ENV}/"


def _sent() -> set[str]:
    return set(OffsiteCopy.objects.filter(key__startswith=_prefix()).values_list("key", flat=True))


def _keys(client: Any, bucket: str, prefix: str) -> set[str]:
    found: set[str] = set()
    for page in client.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            found.add(obj["Key"])
    return found


def _put(client: Any, key: str, body: IO[bytes]) -> None:
    md5 = hashlib.md5(usedforsecurity=False)
    size = 0
    for chunk in iter(lambda: body.read(1024 * 1024), b""):
        md5.update(chunk)
        size += len(chunk)
    body.seek(0)
    client.put_object(
        Bucket=settings.OFFSITE_BUCKET,
        Key=key,
        Body=body,
        ContentMD5=base64.b64encode(md5.digest()).decode(),
    )
    OffsiteCopy.objects.create(key=key, size_bytes=size, md5=md5.hexdigest())


@dataclass
class OffsiteResult:
    dumps_copied: int = 0
    media_copied: int = 0


def run_offsite_copy() -> OffsiteResult:
    if not enabled():
        logger.info("off-site copy not set up (OFFSITE_* settings empty); skipping")
        return OffsiteResult()
    dest = offsite_client()
    there = _sent()
    result = OffsiteResult()
    _copy_dumps(dest, there, result)
    _copy_media(dest, there, result)
    logger.info(
        "off-site copy done",
        extra={
            "dumps_copied": result.dumps_copied,
            "media_copied": result.media_copied,
        },
    )
    return result


def _copy_dumps(dest: Any, there: set[str], result: OffsiteResult) -> None:
    """db/<env>/YYYY/MM/DD/file in the backup bucket -> <env>/db/YYYY/MM/DD/file."""
    src = backup_client()
    source_prefix = f"db/{settings.APP_ENV}/"
    today = timezone.localdate()
    for back in range(DB_DAYS):
        day = today - timedelta(days=back)
        day_prefix = f"{source_prefix}{day:%Y/%m/%d}/"
        for key in sorted(_keys(src, settings.BACKUP_BUCKET, day_prefix)):
            target = _prefix() + "db/" + key[len(source_prefix) :]
            if target in there:
                continue
            obj = src.get_object(Bucket=settings.BACKUP_BUCKET, Key=key)
            # Spool to memory or disk (dumps can be large) so the MD5 can be
            # computed before the upload starts.
            with tempfile.SpooledTemporaryFile(max_size=64 * 1024 * 1024) as buf:
                for chunk in obj["Body"].iter_chunks(1024 * 1024):
                    buf.write(chunk)
                buf.seek(0)
                _put(dest, target, buf)  # type: ignore[arg-type]
            there.add(target)
            result.dumps_copied += 1


def _copy_media(dest: Any, there: set[str], result: OffsiteResult) -> None:
    src = media_client()
    bucket = settings.S3_MEDIA_OPTIONS["bucket_name"]
    for page in src.get_paginator("list_objects_v2").paginate(Bucket=bucket):
        for obj in page.get("Contents", []):
            target = _prefix() + "media/" + obj["Key"]
            if target in there:
                continue
            body = src.get_object(Bucket=bucket, Key=obj["Key"])["Body"].read()
            _put(dest, target, io.BytesIO(body))
            there.add(target)
            result.media_copied += 1
