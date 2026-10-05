from django.db import migrations

from apps.core.migration_ops import PreventHardDelete


class Migration(migrations.Migration):
    dependencies = [("customers", "0001_initial")]

    operations = [
        PreventHardDelete("customers_customer"),
        PreventHardDelete("customers_contact"),
        PreventHardDelete("customers_address"),
    ]
