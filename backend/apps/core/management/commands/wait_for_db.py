import time
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import OperationalError, connection


class Command(BaseCommand):
    help = "Wait until the database accepts connections (used by container start-up)."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--timeout", type=int, default=60)

    def handle(self, *args: Any, timeout: int = 60, **opts: Any) -> None:
        deadline = time.monotonic() + timeout
        while True:
            try:
                connection.ensure_connection()
                self.stdout.write("database is ready")
                return
            except OperationalError as exc:
                if time.monotonic() > deadline:
                    raise CommandError(f"database not reachable after {timeout}s: {exc}") from exc
                time.sleep(1)
                connection.close()
