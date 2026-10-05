"""Customers and units are behind the `customers-units` feature flag (on).
An admin can switch it off under Site settings if something goes wrong."""

from django.db import migrations


def add_flag(apps, schema_editor):  # type: ignore[no-untyped-def]
    FeatureFlag = apps.get_model("core", "FeatureFlag")
    if not FeatureFlag.objects.filter(key="customers-units").exists():
        FeatureFlag.objects.create(
            key="customers-units", description="Phase 2: customers and forklift units", enabled=True
        )


class Migration(migrations.Migration):
    dependencies = [("units", "0002_db_guards"), ("core", "0003_cache_table")]

    operations = [migrations.RunPython(add_flag, migrations.RunPython.noop)]
