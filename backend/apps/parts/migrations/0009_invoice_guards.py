from django.db import migrations

from apps.core.migration_ops import PreventHardDelete


class Migration(migrations.Migration):
    dependencies = [("parts", "0008_invoice_unique")]

    operations = [PreventHardDelete("parts_invoice"), PreventHardDelete("parts_invoiceline")]
