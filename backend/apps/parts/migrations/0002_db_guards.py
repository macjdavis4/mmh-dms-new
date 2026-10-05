from django.db import migrations

from apps.core.migration_ops import PreventHardDelete


class Migration(migrations.Migration):
    dependencies = [("parts", "0001_initial")]

    operations = [
        PreventHardDelete(table) for table in ("parts_bin", "parts_part", "parts_crossreference")
    ]
