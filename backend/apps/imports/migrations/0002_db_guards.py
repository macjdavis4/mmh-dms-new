from django.db import migrations

from apps.core.migration_ops import PreventHardDelete


class Migration(migrations.Migration):
    dependencies = [("imports", "0001_initial")]

    operations = [
        PreventHardDelete(table)
        for table in (
            "imports_importbatch",
            "imports_importrow",
            "imports_importfile",
            "imports_apikey",
        )
    ]
