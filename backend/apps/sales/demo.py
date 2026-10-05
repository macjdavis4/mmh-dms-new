"""Demo quotes and one recorded sale, for development, tests and screenshots."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.customers.models import Customer
from apps.units.models import Unit

from . import services
from .models import Quote

QUOTES: list[dict[str, Any]] = [
    {
        "key": "demo-penobscot",
        "customer": "Penobscot Paper Co.",
        "status": "draft",
        "days_ago": 1,
        "attention": "Dana Hale",
        "lines": [
            ("unit", "HHKHHN04P00123", "", "38900", True),
            ("attachment", None, "Cascade side shifter, 4-way hydraulics", "2400", True),
            ("delivery", None, "Delivery to the Bangor mill", "350", False),
        ],
        "trade_ins": [("HHKHHN04L0094", "9500", None, "", "Mast chains worn")],
    },
    {
        "key": "demo-downeast",
        "customer": "Downeast Seafood Distributors",
        "status": "sent",
        "days_ago": 6,
        "attention": "Robin Gray",
        "lines": [
            ("unit", "HHKHBT10P00877", "", "14500", True),
            ("attachment", None, "Onboard charger, 48 V", "1800", True),
            ("discount", None, "Returning customer", "-500", True),
        ],
        "trade_ins": [("HHKHBT08J00221", "2500", "600", "Machias Savings", "")],
    },
    {
        "key": "demo-murphy",
        "customer": "Pat Murphy",
        "status": "accepted",
        "days_ago": 4,
        "lines": [
            ("unit", "FGA25-71522", "", "17900", True),
            ("service", None, "90-day powertrain warranty", "450", True),
        ],
        "trade_ins": [],
    },
    {
        "key": "demo-katahdin",
        "customer": "Katahdin Lumber",
        "status": "sold",
        "days_ago": 12,
        "sold_days_ago": 3,
        "invoice": "INV-10571",
        "attention": "Morgan Pelletier",
        "lines": [
            ("unit", "HHKHFT20E00419", "", "27000", True),
            ("delivery", None, "Delivery to Millinocket", "650", False),
        ],
        # A trade-in we didn't know about: becomes a unit when the sale is recorded.
        "new_trade_in": {
            "make": "Clark",
            "model": "C500-Y60",
            "serial_number": "C500-Y60-4471",
            "year": 2004,
            "hours": Decimal("21500"),
            "allowance": Decimal("3000"),
            "description": "Runs; LPG regulator leaks",
        },
    },
]


def load_demo_quotes() -> None:
    """Idempotent: each demo quote is made once (found again by its marker note)."""
    salesperson = get_user_model().objects.filter(email="sales@mmh.test").first()
    today = timezone.localdate()
    for spec in QUOTES:
        marker = f"[{spec['key']}]"
        if Quote.all_objects.filter(notes__contains=marker).exists():
            continue
        customer = Customer.objects.filter(name=spec["customer"]).first()
        if customer is None:
            continue
        quote_date = today - timedelta(days=spec["days_ago"])
        quote = Quote(
            customer=customer,
            salesperson=salesperson,
            quote_date=quote_date,
            valid_until=quote_date + timedelta(days=30),
            attention=spec.get("attention", ""),
            notes=f"Demo quote {marker}",
        )
        lines = []
        for kind, serial, description, price, taxable in spec["lines"]:
            unit = Unit.objects.filter(serial_number=serial).first() if serial else None
            if serial and unit is None:
                break
            lines.append(
                {
                    "kind": kind,
                    "unit": unit,
                    "description": description,
                    "unit_price": Decimal(price),
                    "taxable": taxable,
                }
            )
        else:
            trades: list[dict[str, Any]] = []
            for serial, allowance, payoff, payoff_to, description in spec.get("trade_ins", []):
                unit = Unit.objects.filter(serial_number=serial).first()
                if unit is not None:
                    trades.append(
                        {
                            "unit": unit,
                            "allowance": Decimal(allowance),
                            "payoff": Decimal(payoff) if payoff else None,
                            "payoff_to": payoff_to,
                            "description": description,
                        }
                    )
            if spec.get("new_trade_in"):
                trades.append(dict(spec["new_trade_in"]))
            services.save_quote(quote, lines=lines, trade_ins=trades)
            if spec["status"] in ("sent", "accepted"):
                services.set_status(quote, "sent")
            if spec["status"] == "accepted":
                services.set_status(quote, "accepted")
            if spec["status"] == "sold":
                services.set_status(quote, "accepted")
                services.record_sale(
                    quote,
                    sale_date=today - timedelta(days=spec["sold_days_ago"]),
                    invoice_number=spec["invoice"],
                )
