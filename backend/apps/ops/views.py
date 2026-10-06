"""Admin > Paper backup: the nightly printable files. Admins only."""

from __future__ import annotations

from typing import Any

from django.http import FileResponse, Http404
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdmin

from . import paper
from .models import BackupRun


def _run_data(run: BackupRun) -> dict[str, Any]:
    ok = run.status == BackupRun.Status.SUCCEEDED
    return {
        "id": str(run.pk),
        "date": run.run_date.isoformat(),
        "status": run.status,
        "status_label": run.get_status_display(),
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "error": run.error,
        "counts": run.row_counts or {},
        "size_bytes": run.size_bytes,
        "folder": f"paper/{paper.storage_location_env()}/{run.object_key}/",
        "files": [
            {"name": name, "content_type": kind, "description": text}
            for name, kind, text in paper.FILES
        ]
        if ok
        else [],
    }


class PaperBackupListView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request: Request) -> Response:
        runs = BackupRun.objects.filter(kind=BackupRun.Kind.PAPER).order_by("-started_at")[:14]
        return Response({"results": [_run_data(r) for r in runs]})

    def post(self, request: Request) -> Response:
        """Make a fresh copy now (replaces today's)."""
        run = paper.run_paper_backup(force=True)
        code = status.HTTP_201_CREATED if run.status == BackupRun.Status.SUCCEEDED else 500
        return Response(_run_data(run), status=code)


class PaperBackupFileView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request: Request, pk: Any, name: str) -> FileResponse:
        run = BackupRun.objects.filter(
            pk=pk, kind=BackupRun.Kind.PAPER, status=BackupRun.Status.SUCCEEDED
        ).first()
        if run is None:
            raise Http404
        try:
            handle = paper.open_file(run, name)
        except (FileNotFoundError, OSError) as exc:
            raise Http404 from exc
        inline = name.endswith(".pdf")
        response = FileResponse(
            handle,
            content_type=paper.CONTENT_TYPES[name],
            as_attachment=not inline,
            filename=f"{run.run_date:%Y-%m-%d}-{name}",
        )
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response
