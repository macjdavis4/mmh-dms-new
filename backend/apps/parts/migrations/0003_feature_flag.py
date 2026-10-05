"""The parts catalog is behind the `parts` feature flag (on). An admin can
switch it off under Site settings if something goes wrong."""

from django.db import migrations


def add_flag(apps, schema_editor):  # type: ignore[no-untyped-def]
    FeatureFlag = apps.get_model("core", "FeatureFlag")
    if not FeatureFlag.objects.filter(key="parts").exists():
        FeatureFlag.objects.create(key="parts", description="Phase 9: parts catalog", enabled=True)


class Migration(migrations.Migration):
    dependencies = [("parts", "0002_db_guards"), ("core", "0003_cache_table")]

    operations = [migrations.RunPython(add_flag, migrations.RunPython.noop)]
