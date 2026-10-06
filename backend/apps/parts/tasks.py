"""Parts jobs (Procrastinate): the nightly stock check, and reading supplier
invoices. Both are safe to retry."""

from __future__ import annotations

from procrastinate import RetryStrategy
from procrastinate.contrib.django import app

from apps.core.context import acting_as

from . import invoices, stock


@app.periodic(cron="0 7 * * *", periodic_id="nightly-stock-check")
@app.task(queue="maintenance", queueing_lock="stock-check", lock="stock-check")
def nightly_stock_check(timestamp: int) -> None:
    with acting_as(source="job"):
        stock.check_drift()


@app.task(queue="default", retry=RetryStrategy(max_attempts=3, wait=30), pass_context=False)
def read_parts_invoice(invoice_id: str) -> None:
    """OCR can take a while, so it runs here rather than in the web request.
    Only acts on an invoice still marked as reading."""
    with acting_as(source="job"):
        invoices.read_invoice(invoice_id)
