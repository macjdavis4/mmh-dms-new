"""Work orders are behind the `service` feature flag (on). Development
databases seeded in Phase 1 had it off; seed_dev switches it on."""

from django.db import migrations


def add_flag(apps, schema_editor):  # type: ignore[no-untyped-def]
    FeatureFlag = apps.get_model("core", "FeatureFlag")
    if not FeatureFlag.objects.filter(key="service").exists():
        FeatureFlag.objects.create(key="service", description="Work orders", enabled=True)


class Migration(migrations.Migration):
    dependencies = [("service", "0002_db_guards"), ("core", "0003_cache_table")]

    operations = [migrations.RunPython(add_flag, migrations.RunPython.noop)]
