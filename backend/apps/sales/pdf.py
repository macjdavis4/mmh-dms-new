"""Quote printout for the customer: what's offered, trade-ins, totals, terms
and a line to sign. Internal notes and our cost are never printed."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from reportlab.lib.units import inch
from reportlab.platypus import KeepTogether, Spacer, Table, TableStyle

from apps.core.pdf import LINE, NAVY, SHADE, WIDTH, box, date_text, facts, grid, number, p, render

from .models import Quote, QuoteLine
from .totals import quote_totals


def dollars(value: Decimal | None) -> str:
    if value is None:
        return ""
    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value):,.2f}"


def _line_text(line: QuoteLine) -> str:
    unit = line.unit
    if unit is None:
        return line.description
    latest = unit.hour_readings.first()
    title = " ".join(str(x) for x in [unit.year, unit.make, unit.model] if x) or "Unit"
    details = " · ".join(
        x
        for x in [
            unit.get_condition_display(),
            f"Serial {unit.serial_number}" if unit.serial_number else "",
            f"Stock # {unit.stock_number}" if unit.stock_number else "",
            f"{number(latest.hours)} h" if latest else "",
        ]
        if x
    )
    extra = f"\n{line.description}" if line.description else ""
    return f"{title}\n{details}{extra}"


def _totals_table(rows: list[tuple[str, str]], bold_last: bool = True) -> Table:
    data = [[p(label, "right"), p(value, "right")] for label, value in rows]
    if bold_last and data:
        label, value = rows[-1]
        data[-1] = [
            p(f"<b>{label}</b>", "right", raw=True),
            p(f"<b>{value}</b>", "right", raw=True),
        ]
    table = Table(data, colWidths=[WIDTH * 0.25, WIDTH * 0.17], hAlign="RIGHT")
    style: list[tuple[Any, ...]] = [
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]
    if bold_last:
        style += [
            ("LINEABOVE", (0, -1), (-1, -1), 1, NAVY),
            ("BACKGROUND", (0, -1), (-1, -1), SHADE),
        ]
    table.setStyle(TableStyle(style))
    return table


def _acceptance() -> Table:
    labels = [p("Accepted by (name)", "label"), p("Signature", "label"), p("Date", "label")]
    table = Table(
        [[""] * 3, labels],
        colWidths=[WIDTH * 0.38, WIDTH * 0.42, WIDTH * 0.2],
        rowHeights=[0.45 * inch, None],
    )
    table.setStyle(
        TableStyle(
            [
                ("LINEABOVE", (0, 1), (-1, 1), 0.75, LINE),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 14),
            ]
        )
    )
    return table


def quote_pdf(quote: Quote) -> bytes:
    customer = quote.customer
    address = customer.addresses.filter(is_primary=True).first() or customer.addresses.first()
    lines = list(quote.lines.select_related("unit"))
    trades = list(quote.trade_ins.select_related("unit"))
    totals = quote_totals(quote)
    sale = quote.sales.filter(status="completed").first()

    story: list[Any] = [
        p(f"Quote {quote.number}", "title"),
        p(
            " · ".join(
                x
                for x in [
                    f"Date {date_text(quote.quote_date)}",
                    f"Valid until {date_text(quote.valid_until)}" if quote.valid_until else "",
                    f"Salesperson {quote.salesperson.full_name or quote.salesperson.email}"
                    if quote.salesperson
                    else "",
                    f"Sold {date_text(sale.sale_date)} ({sale.number})" if sale else "",
                ]
                if x
            ),
            "subtitle",
        ),
        Spacer(1, 8),
        p("Prepared for", "h2"),
        facts(
            [
                ("Customer", customer.name),
                ("Attention", quote.attention),
                ("Account", customer.account_number),
                ("Phone", customer.phone),
                (
                    "Address",
                    ", ".join(
                        x
                        for x in [
                            address.line1,
                            address.line2,
                            address.city,
                            f"{address.state} {address.postal_code}".strip(),
                        ]
                        if x
                    )
                    if address
                    else "",
                ),
                ("Your PO", quote.customer_po),
            ],
            columns=3,
        ),
        p("Equipment and items", "h2"),
        grid(
            ["Description", "Qty", "Price", "Amount"],
            [
                [
                    _line_text(line) + ("" if line.taxable else "\n(not taxed)"),
                    number(line.quantity),
                    dollars(line.unit_price),
                    dollars(line.amount),
                ]
                for line in lines
            ],
            [0.6, 0.08, 0.16, 0.16],
        ),
    ]
    if trades:
        story += [
            p("Trade-ins", "h2"),
            grid(
                ["Trade-in", "Hours", "Allowance", "Payoff"],
                [
                    [
                        "\n".join(
                            x
                            for x in [
                                " ".join(
                                    str(v)
                                    for v in [
                                        t.unit.year if t.unit else t.year,
                                        t.unit.make if t.unit else t.make,
                                        t.unit.model if t.unit else t.model,
                                    ]
                                    if v
                                ),
                                "Serial " + (t.unit.serial_number if t.unit else t.serial_number)
                                if (t.unit.serial_number if t.unit else t.serial_number)
                                else "",
                                t.description,
                                f"Payoff to {t.payoff_to}" if t.payoff_to else "",
                            ]
                            if x
                        ),
                        number(t.hours) if t.hours is not None else "",
                        dollars(t.allowance),
                        dollars(t.payoff) if t.payoff else "",
                    ]
                    for t in trades
                ],
                [0.6, 0.1, 0.15, 0.15],
            ),
        ]
    rows = [("Subtotal", dollars(totals.subtotal))]
    if trades:
        rows.append(("Trade-in allowance", dollars(-totals.trade_allowance)))
        if totals.trade_payoff:
            rows.append(("Trade-in payoff", dollars(totals.trade_payoff)))
    if quote.tax_exempt:
        rows.append(
            (
                "Sales tax (exempt"
                + (f", {quote.tax_exempt_number}" if quote.tax_exempt_number else "")
                + ")",
                dollars(Decimal("0")),
            )
        )
    else:
        rows.append((f"Sales tax ({number(totals.tax_rate)}%)", dollars(totals.tax)))
    rows.append(("Total", dollars(totals.total)))
    story += [Spacer(1, 6), _totals_table(rows)]
    if quote.terms.strip():
        story += [Spacer(1, 10), box("Terms", quote.terms, 0.3 * inch)]
    story += [
        Spacer(1, 18),
        KeepTogether(
            [p("To accept this quote, sign and return it.", "small"), Spacer(1, 4), _acceptance()]
        ),
    ]
    return render(story, title=f"Quote {quote.number}", label=f"Quote {quote.number}")
