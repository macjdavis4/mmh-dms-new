from django.db import migrations

from apps.core.migration_ops import AppendOnly, PreventHardDelete


class Migration(migrations.Migration):
    dependencies = [("parts", "0004_stock_ledger")]

    operations = [
        # The ledger is never edited or deleted; mistakes get a reversing line.
        AppendOnly("parts_stockmovement"),
        PreventHardDelete("parts_partstock"),
    ]
