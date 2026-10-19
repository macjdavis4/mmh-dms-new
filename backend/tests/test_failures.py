"""Failed background jobs and backups are written to the audit log once."""

from __future__ import annotations

from typing import Any

import pytest
from django.db import connection
from django.utils import timezone

from apps.core.models import AuditLog
from apps.ops import failures
from apps.ops.models import BackupRun

pytestmark = pytest.mark.django_db
URL = "/api/v1/admin/audit-log"


def failed_job(task: str = "apps.parts.tasks.read_parts_invoice", status: str = "failed") -> int:
    with connection.cursor() as cur:
        cur.execute(
            "INSERT INTO procrastinate_jobs (queue_name, task_name, args, status, attempts)"
            " VALUES ('default', %s, %s, %s, 3) RETURNING id",
            [task, '{"invoice_id": "abc"}', status],
        )
        job_id = int(cur.fetchone()[0])
        cur.execute(
            "INSERT INTO procrastinate_events (job_id, type) VALUES (%s, 'failed')", [job_id]
        )
    return job_id


def test_failed_jobs_and_backups_are_recorded_once(client_for: Any) -> None:
    job_id = failed_job()
    failed_job(task="apps.ops.tasks.nightly_paper_backup", status="succeeded")
    run = BackupRun.objects.create(
        kind=BackupRun.Kind.MEDIA,
        status=BackupRun.Status.FAILED,
        finished_at=timezone.now(),
        error="Access denied",
    )
    BackupRun.objects.create(kind=BackupRun.Kind.DATABASE, status=BackupRun.Status.SUCCEEDED)

    assert failures.record_failures() == 2
    assert failures.record_failures() == 0  # safe to run again

    job = AuditLog.objects.get(action="job_failed")
    assert job.object_id == str(job_id)
    assert job.object_repr == f"Read parts invoice (job {job_id})"
    assert job.after is not None
    assert job.after["attempts"] == 3 and job.after["args"] == {"invoice_id": "abc"}
    assert job.after["failed_at"] is not None
    backup = AuditLog.objects.get(action="backup_failed")
    assert backup.object_id == str(run.pk)
    assert backup.after is not None and backup.after["error"] == "Access denied"

    # Admins find them in the audit log; nobody else can read it.
    res = client_for("admin").get(f"{URL}?action=job_failed")
    assert res.status_code == 200
    assert [e["object_repr"] for e in res.json()["results"]] == [job.object_repr]
    assert client_for("parts").get(URL).status_code == 403


def test_job_label() -> None:
    assert failures.job_label("apps.ops.tasks.nightly_database_backup") == (
        "Nightly database backup"
    )
