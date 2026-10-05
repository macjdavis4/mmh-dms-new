"""Quote totals. Mirrored in frontend/src/features/sales/totals.ts (keep in step).

subtotal        every line (discounts are negative lines)
trade allowance what the trade-ins are worth to the customer
trade payoff    what the customer still owes on them, which we pay off
taxable amount  taxable lines less the trade allowance (never below zero);
                nothing when the customer is tax exempt
tax             taxable amount x rate, to the cent
total           subtotal - trade allowance + trade payoff + tax
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class LineAmount:
    quantity: Decimal
    unit_price: Decimal
    taxable: bool

    @property
    def amount(self) -> Decimal:
        return money(self.quantity * self.unit_price)


@dataclass(frozen=True)
class TradeAmount:
    allowance: Decimal
    payoff: Decimal | None


@dataclass(frozen=True)
class Totals:
    subtotal: Decimal
    trade_allowance: Decimal
    trade_payoff: Decimal
    taxable_amount: Decimal
    tax_rate: Decimal
    tax: Decimal
    total: Decimal

    def as_dict(self) -> dict[str, str]:
        return {k: str(v) for k, v in self.__dict__.items()}


def compute(
    lines: Iterable[LineAmount],
    trades: Iterable[TradeAmount],
    *,
    tax_rate: Decimal,
    tax_exempt: bool,
) -> Totals:
    lines = list(lines)
    trades = list(trades)
    subtotal = sum((line.amount for line in lines), Decimal("0"))
    allowance = money(sum((t.allowance for t in trades), Decimal("0")))
    payoff = money(sum((t.payoff or Decimal("0") for t in trades), Decimal("0")))
    taxable_lines = sum((line.amount for line in lines if line.taxable), Decimal("0"))
    taxable = Decimal("0") if tax_exempt else max(Decimal("0"), taxable_lines - allowance)
    tax = money(taxable * tax_rate / Decimal("100"))
    return Totals(
        subtotal=money(subtotal),
        trade_allowance=allowance,
        trade_payoff=payoff,
        taxable_amount=money(taxable),
        tax_rate=tax_rate,
        tax=tax,
        total=money(subtotal - allowance + payoff + tax),
    )


def quote_totals(quote: object) -> Totals:
    from .models import Quote

    assert isinstance(quote, Quote)
    return compute(
        (LineAmount(x.quantity, x.unit_price, x.taxable) for x in quote.lines.all()),
        (TradeAmount(t.allowance, t.payoff) for t in quote.trade_ins.all()),
        tax_rate=quote.tax_rate,
        tax_exempt=quote.tax_exempt,
    )
