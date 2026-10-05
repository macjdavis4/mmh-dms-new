"""Batch import is behind the `batch-import` feature flag (on). An admin can
switch it off under Site settings."""

from django.db import migrations


def add_flag(apps, schema_editor):  # type: ignore[no-untyped-def]
    FeatureFlag = apps.get_model("core", "FeatureFlag")
    if not FeatureFlag.objects.filter(key="batch-import").exists():
        FeatureFlag.objects.create(
            key="batch-import",
            description="Phase 3: CSV and API import of unit cards",
            enabled=True,
        )


class Migration(migrations.Migration):
    dependencies = [("imports", "0002_db_guards"), ("core", "0003_cache_table")]

    operations = [migrations.RunPython(add_flag, migrations.RunPython.noop)]
