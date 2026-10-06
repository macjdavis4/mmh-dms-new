from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.conf import settings
from django.db import connection
from django.http import HttpRequest, HttpResponse
from django.template import engines
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import generics, serializers
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdmin
from apps.ops.models import BackupRun

from . import health
from .models import AuditLog, FeatureFlag, SiteSettings

_INDEX = Path(settings.BASE_DIR) / "frontend_dist" / "index.html"


@ensure_csrf_cookie
def spa_index(request: HttpRequest) -> HttpResponse:
    """Serve the React app. Client-side routing handles the path."""
    if not _INDEX.exists():
        return HttpResponse(
            "<h1>Frontend not built</h1><p>Run <code>make frontend-build</code> or use the "
            "Vite dev server on port 5173.</p>",
            status=503,
        )
    config = {
        "env": settings.APP_ENV,
        "version": settings.APP_VERSION,
        "sentryDsn": settings.SENTRY_FRONTEND_DSN,
    }
    template = engines["django"].from_string(_INDEX.read_text(encoding="utf-8"))
    return HttpResponse(template.render({"mmh_config": json.dumps(config)}, request))


_SERVICE_WORKER = Path(settings.BASE_DIR) / "frontend_dist" / "sw.js"


def service_worker(request: HttpRequest) -> HttpResponse:
    """The offline service worker (Phase 13), at the site root so it covers
    every page. Never cached, so a new release is picked up straight away."""
    if not _SERVICE_WORKER.exists():
        return HttpResponse("// no service worker in this build\n", content_type="text/javascript")
    response = HttpResponse(
        _SERVICE_WORKER.read_bytes(), content_type="text/javascript; charset=utf-8"
    )
    response["Cache-Control"] = "no-cache, max-age=0"
    response["Service-Worker-Allowed"] = "/"
    return response


# --- System status (banner, read-only flag) -----------------------------------


class SystemStatusView(APIView):
    """Shown on every screen, including the sign-in page, so it is public.
    It only exposes the banner and whether the system is read-only."""

    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        s = SiteSettings.objects.filter(pk=SiteSettings.SINGLETON_ID).first()
        return Response(
            {
                "read_only_mode": bool(s and s.read_only_mode),
                "banner_message": s.banner_message if s else "",
                "banner_level": s.banner_level if s else "info",
                "environment": settings.APP_ENV,
                "version": settings.APP_VERSION,
            }
        )


class SiteSettingsSerializer(serializers.ModelSerializer[SiteSettings]):
    class Meta:
        model = SiteSettings
        fields = ["read_only_mode", "banner_message", "banner_level", "updated_at"]
        read_only_fields = ["updated_at"]


class SiteSettingsView(generics.RetrieveUpdateAPIView[SiteSettings]):
    permission_classes = [IsAdmin]
    serializer_class = SiteSettingsSerializer
    http_method_names = ["get", "patch", "options"]

    def get_object(self) -> SiteSettings:
        return SiteSettings.load()


# --- Feature flags ------------------------------------------------------------


class FeatureFlagsView(APIView):
    def get(self, request: Request) -> Response:
        flags = {f.key: f.is_on_for(request.user) for f in FeatureFlag.objects.all()}
        return Response({"flags": flags})


# --- Audit log (admin) --------------------------------------------------------


class AuditLogSerializer(serializers.ModelSerializer[AuditLog]):
    actor_email = serializers.SerializerMethodField()
    object_type = serializers.SerializerMethodField()
    action_label = serializers.CharField(source="get_action_display")

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "at",
            "actor",
            "actor_email",
            "actor_role",
            "source",
            "action",
            "action_label",
            "object_type",
            "object_id",
            "object_repr",
            "before",
            "after",
            "changed_fields",
            "request_id",
            "ip",
        ]

    def get_actor_email(self, obj: AuditLog) -> str | None:
        return obj.actor.email if obj.actor else None

    def get_object_type(self, obj: AuditLog) -> str | None:
        return obj.content_type.name if obj.content_type else None


class AuditLogListView(generics.ListAPIView[AuditLog]):
    permission_classes = [IsAdmin]
    serializer_class = AuditLogSerializer

    def get_queryset(self) -> Any:
        qs = AuditLog.objects.select_related("actor", "content_type")
        params = self.request.query_params
        if action := params.get("action"):
            qs = qs.filter(action=action)
        if actor := params.get("actor"):
            qs = qs.filter(actor_id=actor)  # type: ignore[misc]
        if object_id := params.get("object_id"):
            qs = qs.filter(object_id=object_id)
        if q := params.get("q"):
            qs = qs.filter(object_repr__icontains=q)
        return qs


# --- Admin health indicator ---------------------------------------------------


class AdminHealthView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request: Request) -> Response:
        db_ok, db_detail = health._check_database()
        _, mig_detail = health._check_migrations() if db_ok else (False, "skipped")
        jobs: dict[str, Any] = {}
        if db_ok:
            with connection.cursor() as cur:
                cur.execute(
                    "SELECT status, count(*) FROM procrastinate_jobs "
                    "WHERE status IN ('todo','doing','failed') GROUP BY status"
                )
                jobs = {row[0]: row[1] for row in cur.fetchall()}
        latest = (
            BackupRun.objects.exclude(kind=BackupRun.Kind.PAPER).order_by("-started_at").first()
        )
        paper = BackupRun.objects.filter(kind=BackupRun.Kind.PAPER).order_by("-started_at").first()
        return Response(
            {
                "database": db_detail,
                "migrations": mig_detail,
                "jobs": jobs,
                "last_backup": {
                    "status": latest.status,
                    "started_at": latest.started_at,
                    "finished_at": latest.finished_at,
                }
                if latest
                else None,
                "last_paper_backup": {
                    "status": paper.status,
                    "started_at": paper.started_at,
                    "finished_at": paper.finished_at,
                }
                if paper
                else None,
                "version": settings.APP_VERSION,
                "environment": settings.APP_ENV,
            }
        )
