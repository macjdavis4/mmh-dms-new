from django.db import migrations

from apps.core.migration_ops import AppendOnly, PreventHardDelete


class Migration(migrations.Migration):
    dependencies = [("sales", "0001_initial")]

    operations = [
        *(
            PreventHardDelete(table)
            for table in ("sales_quote", "sales_quoteline", "sales_tradein", "sales_sale")
        ),
        AppendOnly("sales_saleunitchange"),
    ]
