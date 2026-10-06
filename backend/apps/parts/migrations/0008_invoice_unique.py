"""One supplier invoice number can be entered only once (ignoring case), so
the same invoice can't be received twice. The table is new and empty, so
building the index takes no time. (The migration linter misreads indexes on
expressions; this migration is listed in its ignore_name setting.)"""

import django.db.models.functions.text
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("parts", "0007_supplier_invoices")]

    operations = [
        migrations.AddConstraint(
            model_name="invoice",
            constraint=models.UniqueConstraint(
                django.db.models.functions.text.Upper("supplier"),
                django.db.models.functions.text.Upper("invoice_number"),
                condition=models.Q(
                    ("deleted_at__isnull", True),
                    models.Q(("invoice_number", ""), _negated=True),
                    models.Q(("status", "cancelled"), _negated=True),
                ),
                name="invoice_unique_per_supplier",
            ),
        ),
    ]
