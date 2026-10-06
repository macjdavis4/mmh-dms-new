"""Nightly stock ledger check (Procrastinate). Read-only and safe to retry."""

from __future__ import annotations

from procrastinate.contrib.django import app

from apps.core.context import acting_as

from . import stock


@app.periodic(cron="0 7 * * *", periodic_id="nightly-stock-check")
@app.task(queue="maintenance", queueing_lock="stock-check", lock="stock-check")
def nightly_stock_check(timestamp: int) -> None:
    with acting_as(source="job"):
        stock.check_drift()
