"""Create the media and backup buckets in local MinIO (development only).
In staging and production the buckets are created by Terraform."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.ops.backup import backup_client, media_client


class Command(BaseCommand):
    help = "Create local S3 buckets if missing (development only)."

    def handle(self, *args: Any, **opts: Any) -> None:
        if settings.APP_ENV in {"staging", "production"}:
            raise CommandError("Buckets are managed by Terraform outside development.")
        for client, bucket in (
            (media_client(), settings.S3_MEDIA_OPTIONS["bucket_name"]),
            (backup_client(), settings.BACKUP_BUCKET),
        ):
            existing = {b["Name"] for b in client.list_buckets().get("Buckets", [])}
            if bucket not in existing:
                client.create_bucket(Bucket=bucket)
                self.stdout.write(f"created bucket {bucket}")
