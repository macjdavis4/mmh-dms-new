"""Supplier invoices are behind the `parts-invoices` feature flag (on). An
admin can switch it off under Site settings; receiving by hand on the part
page keeps working."""

from django.db import migrations


def add_flag(apps, schema_editor):  # type: ignore[no-untyped-def]
    FeatureFlag = apps.get_model("core", "FeatureFlag")
    if not FeatureFlag.objects.filter(key="parts-invoices").exists():
        FeatureFlag.objects.create(
            key="parts-invoices", description="Phase 11: supplier invoices", enabled=True
        )


class Migration(migrations.Migration):
    dependencies = [("parts", "0009_invoice_guards")]

    operations = [migrations.RunPython(add_flag, migrations.RunPython.noop)]
