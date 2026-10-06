"""Parts stock (the ledger, parts on work orders, low stock) is behind the
`parts-stock` feature flag (on). An admin can switch it off under Site settings
if something goes wrong; the catalog keeps working."""

from django.db import migrations


def add_flag(apps, schema_editor):  # type: ignore[no-untyped-def]
    FeatureFlag = apps.get_model("core", "FeatureFlag")
    if not FeatureFlag.objects.filter(key="parts-stock").exists():
        FeatureFlag.objects.create(
            key="parts-stock", description="Phase 10: parts stock ledger", enabled=True
        )


class Migration(migrations.Migration):
    dependencies = [("parts", "0005_stock_guards")]

    operations = [migrations.RunPython(add_flag, migrations.RunPython.noop)]
