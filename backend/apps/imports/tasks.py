"""Background jobs for large imports. Both are idempotent: rows already
imported (or undone) are skipped when a job is retried."""

from __future__ import annotations

from procrastinate import RetryStrategy
from procrastinate.contrib.django import app

from . import services


@app.task(queue="imports", retry=RetryStrategy(max_attempts=3, wait=60), pass_context=False)
def apply_import(batch_id: str) -> None:
    services.apply_batch(batch_id)


@app.task(queue="imports", retry=RetryStrategy(max_attempts=3, wait=60), pass_context=False)
def undo_import(batch_id: str) -> None:
    services.undo_batch(batch_id)
