"""The "Bought and sold" list is behind the `units-changing-hands` feature
flag (on). An admin can switch it off under Site settings."""

from django.db import migrations


def add_flag(apps, schema_editor):  # type: ignore[no-untyped-def]
    FeatureFlag = apps.get_model("core", "FeatureFlag")
    if not FeatureFlag.objects.filter(key="units-changing-hands").exists():
        FeatureFlag.objects.create(
            key="units-changing-hands",
            description="Phase 7: units changing hands (sales, trade-ins, repos)",
            enabled=True,
        )


class Migration(migrations.Migration):
    dependencies = [("units", "0004_ownership_deals"), ("core", "0003_cache_table")]

    operations = [migrations.RunPython(add_flag, migrations.RunPython.noop)]
