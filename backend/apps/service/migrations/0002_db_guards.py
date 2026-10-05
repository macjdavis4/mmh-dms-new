from django.db import migrations

from apps.core.migration_ops import PreventHardDelete


class Migration(migrations.Migration):
    dependencies = [("service", "0001_initial")]

    operations = [PreventHardDelete(t) for t in ("service_workorder", "service_laborline")]
