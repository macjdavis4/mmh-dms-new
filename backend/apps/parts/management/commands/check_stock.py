from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand

from apps.parts import stock


class Command(BaseCommand):
    help = "Check every part's on-hand count against the stock ledger (also runs nightly)."

    def handle(self, *args: Any, **options: Any) -> None:
        run = stock.check_drift()
        if run.drift:
            for row in run.drift:
                self.stdout.write(
                    self.style.ERROR(
                        f"{row['part_number']}: ledger {row['ledger']}, stored {row['stored']}"
                    )
                )
            raise SystemExit(1)
        self.stdout.write(self.style.SUCCESS(f"{run.parts_checked} parts match the ledger."))
