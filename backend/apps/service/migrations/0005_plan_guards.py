from django.db import migrations

from apps.core.migration_ops import PreventHardDelete


class Migration(migrations.Migration):
    dependencies = [("service", "0004_maintenance_plans")]

    operations = [PreventHardDelete("service_maintenanceplan")]
