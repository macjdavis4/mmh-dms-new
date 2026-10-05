"""Quotes and sales are behind the `sales` feature flag (on). An admin can
switch it off under Site settings if something goes wrong."""

from django.db import migrations


def add_flag(apps, schema_editor):  # type: ignore[no-untyped-def]
    FeatureFlag = apps.get_model("core", "FeatureFlag")
    if not FeatureFlag.objects.filter(key="sales").exists():
        FeatureFlag.objects.create(
            key="sales", description="Phase 8: quotes and sales with trade-ins", enabled=True
        )


class Migration(migrations.Migration):
    dependencies = [("sales", "0002_db_guards"), ("core", "0003_cache_table")]

    operations = [migrations.RunPython(add_flag, migrations.RunPython.noop)]
