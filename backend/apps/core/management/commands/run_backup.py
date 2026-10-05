from typing import Any

from django.core.management.base import BaseCommand

from apps.core.context import acting_as
from apps.ops import backup


class Command(BaseCommand):
    help = "Run the database backup (and optionally the media copy) right now."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--force", action="store_true", help="Run even if today's backup exists."
        )
        parser.add_argument("--media", action="store_true", help="Also copy media files.")

    def handle(self, *args: Any, force: bool = False, media: bool = False, **opts: Any) -> None:
        with acting_as(source="cli"):
            run = backup.run_database_backup(force=force)
            self.stdout.write(f"database: {run.status} {run.object_key} ({run.size_bytes} bytes)")
            if media:
                mrun = backup.run_media_replication()
                self.stdout.write(f"media: {mrun.status}, {mrun.objects_copied} copied")
