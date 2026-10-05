from django.db import migrations

from apps.core.migration_ops import PreventHardDelete


class Migration(migrations.Migration):
    dependencies = [("units", "0001_initial")]

    operations = [
        PreventHardDelete(table)
        for table in (
            "units_unit",
            "units_unitcomponent",
            "units_unitfork",
            "units_unitattachment",
            "units_hourmeterreading",
            "units_ownershiprecord",
            "units_unitfile",
        )
    ]
