"""Failed background jobs and backups go into the audit log, so there's a
dated record of what failed and when (the health panel only shows a count).

Swept every few minutes rather than hooked into the failure itself: a job
can die without running any of our code (worker killed, out of memory), and
a sweep is idempotent. Each failure is recorded once."""

from __future__ import annotations

import logging

from django.contrib.contenttypes.models import ContentType
from procrastinate.contrib.django.models import ProcrastinateEvent, ProcrastinateJob

from apps.core.models import AuditLog

from .models import BackupRun

logger = logging.getLogger(__name__)
A = AuditLog.Action


def _recorded(action: str, model: type, ids: list[str]) -> set[str]:
    return set(
        AuditLog.objects.filter(
            action=action,
            content_type=ContentType.objects.get_for_model(model),
            object_id__in=ids,
        ).values_list("object_id", flat=True)
    )


def job_label(task_name: str) -> str:
    """'apps.parts.tasks.read_parts_invoice' -> 'Read parts invoice'."""
    return task_name.rsplit(".", 1)[-1].replace("_", " ").strip().capitalize()


def record_failed_jobs() -> int:
    jobs = list(ProcrastinateJob.objects.filter(status="failed").order_by("id")[:500])
    done = _recorded(A.JOB_FAILED, ProcrastinateJob, [str(j.pk) for j in jobs])
    count = 0
    for job in jobs:
        if str(job.pk) in done:
            continue
        failed_at = (
            ProcrastinateEvent.objects.filter(job_id=job.pk, type="failed")
            .order_by("-at")
            .values_list("at", flat=True)
            .first()
        )
        AuditLog.record(
            A.JOB_FAILED,
            job,
            object_repr=f"{job_label(job.task_name)} (job {job.pk})",
            after={
                "task": job.task_name,
                "queue": job.queue_name,
                "attempts": job.attempts,
                "args": job.args,
                "failed_at": failed_at,
            },
        )
        count += 1
    return count


def record_failed_backups() -> int:
    runs = list(BackupRun.objects.filter(status=BackupRun.Status.FAILED).order_by("started_at"))
    done = _recorded(A.BACKUP_FAILED, BackupRun, [str(r.pk) for r in runs])
    count = 0
    for run in runs:
        if str(run.pk) in done:
            continue
        AuditLog.record(
            A.BACKUP_FAILED,
            run,
            object_repr=f"{run.get_kind_display()} {run.run_date:%Y-%m-%d}",
            after={
                "kind": run.kind,
                "started_at": run.started_at,
                "finished_at": run.finished_at,
                "error": run.error[:500],
            },
        )
        count += 1
    return count


def record_failures() -> int:
    count = record_failed_jobs() + record_failed_backups()
    if count:
        logger.warning("failures recorded in the audit log", extra={"count": count})
    return count
