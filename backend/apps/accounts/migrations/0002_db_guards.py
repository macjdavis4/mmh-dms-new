from django.db import migrations

from apps.core.migration_ops import PreventHardDelete


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial")]

    operations = [PreventHardDelete("accounts_user")]
