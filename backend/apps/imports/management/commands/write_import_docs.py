"""Write docs/IMPORT_FORMAT.md and docs/import/* from apps/imports/columns.py.
A test fails when the committed files are out of date."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.imports import formats


def generated_files() -> dict[Path, str]:
    docs = Path(settings.BASE_DIR).parent / "docs"
    return {
        docs / "IMPORT_FORMAT.md": formats.markdown(),
        docs / "import" / "unit-import-template.csv": formats.template_csv(),
        docs / "import" / "unit-import-sample.csv": formats.sample_csv(),
        docs / "import" / "unit-import.schema.json": formats.json_dump(formats.json_schema()),
        docs / "import" / "unit-import-sample.json": formats.json_dump(formats.sample_json()),
    }


class Command(BaseCommand):
    help = "Regenerate the import format docs, template and sample files."

    def handle(self, *args: Any, **options: Any) -> None:
        for path, content in generated_files().items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="")
            self.stdout.write(f"wrote {path}")
