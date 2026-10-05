from django.db import migrations

from apps.core.migration_ops import AppendOnly


class Migration(migrations.Migration):
    dependencies = [("core", "0001_initial")]

    operations = [AppendOnly("core_auditlog")]
