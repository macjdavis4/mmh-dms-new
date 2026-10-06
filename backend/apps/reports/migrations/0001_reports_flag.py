"""The dashboard tiles and reports are behind the `reports` feature flag (on).
An admin can switch the reports off under Site settings; the dashboard keeps
its basic tiles."""

from django.db import migrations


def add_flag(apps, schema_editor):  # type: ignore[no-untyped-def]
    FeatureFlag = apps.get_model("core", "FeatureFlag")
    if not FeatureFlag.objects.filter(key="reports").exists():
        FeatureFlag.objects.create(key="reports", description="Phase 12: reports", enabled=True)


class Migration(migrations.Migration):
    dependencies = [("core", "0003_cache_table")]

    operations = [migrations.RunPython(add_flag, migrations.RunPython.noop)]
