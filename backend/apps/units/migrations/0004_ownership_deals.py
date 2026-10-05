"""Phase 7: why a unit changed hands, and each sale or acquisition keeps its
own price and cost. Expand only: new nullable or defaulted columns, and checks
that every existing row already passes (existing records have no reason)."""

from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("customers", "0002_db_guards"),
        ("units", "0003_feature_flag"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="ownershiprecord",
            name="cost",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=12,
                null=True,
                validators=[django.core.validators.MinValueValidator(Decimal("0"))],
            ),
        ),
        migrations.AddField(
            model_name="ownershiprecord",
            name="hour_reading",
            field=models.ForeignKey(
                blank=True,
                db_index=False,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="units.hourmeterreading",
            ),
        ),
        migrations.AddField(
            model_name="ownershiprecord",
            name="price",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=12,
                null=True,
                validators=[django.core.validators.MinValueValidator(Decimal("0"))],
            ),
        ),
        migrations.AddField(
            model_name="ownershiprecord",
            name="reason",
            field=models.CharField(
                blank=True,
                choices=[
                    ("sold", "Sold"),
                    ("private_sale", "Sold between customers"),
                    ("trade_in", "Trade-in"),
                    ("repossession", "Repossession"),
                    ("buy_back", "Bought back"),
                    ("lease_return", "Lease return"),
                    ("bought_used", "Bought used"),
                    ("other", "Other"),
                ],
                db_default="",
                default="",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="ownershiprecord",
            name="reference",
            field=models.CharField(blank=True, db_default="", default="", max_length=60),
        ),
        migrations.AddField(
            model_name="ownershiprecord",
            name="unit_changes",
            field=models.JSONField(blank=True, editable=False, null=True),
        ),
        migrations.AddConstraint(
            model_name="ownershiprecord",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    (
                        "reason__in",
                        [
                            "",
                            "sold",
                            "private_sale",
                            "trade_in",
                            "repossession",
                            "buy_back",
                            "lease_return",
                            "bought_used",
                            "other",
                        ],
                    )
                ),
                name="ownership_reason_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="ownershiprecord",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("reason", ""),
                    models.Q(
                        ("owner_kind", "customer"),
                        ("reason__in", ("sold", "private_sale", "other")),
                    ),
                    models.Q(
                        ("owner_kind", "dealer"),
                        (
                            "reason__in",
                            (
                                "trade_in",
                                "repossession",
                                "buy_back",
                                "lease_return",
                                "bought_used",
                                "other",
                            ),
                        ),
                    ),
                    _connector="OR",
                ),
                name="ownership_reason_fits_owner",
            ),
        ),
        migrations.AddConstraint(
            model_name="ownershiprecord",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(("price__isnull", True), ("price__gte", 0), _connector="OR"),
                    models.Q(("cost__isnull", True), ("cost__gte", 0), _connector="OR"),
                ),
                name="ownership_money_not_negative",
            ),
        ),
    ]
