"""Write the made-up sample supplier invoice (PDF or PNG) to a file."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from apps.parts import sample_invoice


class Command(BaseCommand):
    help = "Write a sample supplier invoice to PATH (.pdf or .png) for trying the reader."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("path")
        parser.add_argument("--number", default=sample_invoice.NUMBER)

    def handle(self, *args: Any, **options: Any) -> None:
        path = Path(options["path"])
        build = sample_invoice.png if path.suffix.lower() == ".png" else sample_invoice.pdf
        path.write_bytes(build(number=options["number"]))
        self.stdout.write(self.style.SUCCESS(f"Wrote {path}"))
