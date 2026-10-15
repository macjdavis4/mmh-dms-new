"""In-app help is behind the `help` feature flag (on). An admin can switch it
off under Site settings; the Help menu item and button then disappear."""

from django.db import migrations


def add_flag(apps, schema_editor):  # type: ignore[no-untyped-def]
    FeatureFlag = apps.get_model("core", "FeatureFlag")
    if not FeatureFlag.objects.filter(key="help").exists():
        FeatureFlag.objects.create(key="help", description="In-app help articles", enabled=True)


class Migration(migrations.Migration):
    dependencies = [("core", "0003_cache_table")]

    operations = [migrations.RunPython(add_flag, migrations.RunPython.noop)]
