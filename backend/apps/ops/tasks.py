"""Scheduled background jobs (Procrastinate, Postgres-backed).

Times are UTC. 06:30 UTC is 1:30-2:30 AM in Bangor depending on DST.
Every job is idempotent and safe to retry.
"""

from __future__ import annotations

from procrastinate import RetryStrategy, builtin_tasks
from procrastinate.contrib.django import app

from apps.core.context import acting_as

from . import backup

_RETRY = RetryStrategy(max_attempts=3, wait=600)


@app.periodic(cron="30 6 * * *", periodic_id="nightly-db-backup")
@app.task(
    queue="maintenance",
    queueing_lock="db-backup",
    lock="db-backup",
    retry=_RETRY,
    pass_context=False,
)
def nightly_database_backup(timestamp: int) -> None:
    with acting_as(source="job"):
        backup.run_database_backup()


@app.periodic(cron="15 7 * * *", periodic_id="nightly-media-replication")
@app.task(
    queue="maintenance", queueing_lock="media-replication", lock="media-replication", retry=_RETRY
)
def nightly_media_replication(timestamp: int) -> None:
    with acting_as(source="job"):
        backup.run_media_replication()


@app.periodic(cron="0 8 * * 0", periodic_id="weekly-job-cleanup")
@app.task(queue="maintenance", queueing_lock="job-cleanup", pass_context=True)
async def weekly_job_cleanup(context, timestamp: int) -> None:  # type: ignore[no-untyped-def]
    """Trim the job queue: finished jobs older than 60 days (queue bookkeeping
    only; business data is never deleted)."""
    await builtin_tasks.remove_old_jobs(context, max_hours=24 * 60, remove_failed=False)
