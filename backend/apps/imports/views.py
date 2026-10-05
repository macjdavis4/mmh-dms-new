from __future__ import annotations

from typing import Any

from django.db.models import Q, QuerySet
from django.http import FileResponse, Http404, HttpResponse
from django.utils import timezone
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.api import RequiresFlag
from apps.core.context import acting_as

from . import formats, services
from .authentication import ApiKeyAuthentication, ApiKeyThrottle, HasApiKey
from .models import ApiKey, ImportBatch, ImportRow
from .permissions import CanImport, CanManageApiKeys
from .serializers import (
    ApiImportSerializer,
    ApiKeySerializer,
    ApplySerializer,
    ImportBatchListSerializer,
    ImportBatchSerializer,
    ImportFileSerializer,
    ImportRowSerializer,
)

FLAG = RequiresFlag("batch-import")

ROW_FILTERS = {
    "errors": Q(status=ImportRow.Check.ERROR),
    "warnings": Q(status=ImportRow.Check.WARNING),
    "create": Q(plan=ImportRow.Plan.CREATE),
    "update": Q(plan=ImportRow.Plan.UPDATE),
    "unchanged": Q(plan=ImportRow.Plan.UNCHANGED),
    "skip": Q(plan=ImportRow.Plan.SKIP),
    "kept": ~Q(undo_result="") & ~Q(undo_result="Undone"),
}


def _download(
    content: str, filename: str, content_type: str = "text/csv; charset=utf-8"
) -> HttpResponse:
    response = HttpResponse(content, content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


class ImportBatchViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,  # type: ignore[type-arg]
):
    """CSV imports from the app. Everything here is also tested per role."""

    permission_classes = [FLAG, CanImport]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_queryset(self) -> QuerySet[ImportBatch]:
        qs = ImportBatch.objects.select_related("created_by", "undone_by", "api_key")
        if self.action == "retrieve" or self.action not in ("list",):
            qs = qs.prefetch_related("files")
        if self.action == "list" and self.request.query_params.get("include_discarded") != "1":
            qs = qs.exclude(status=ImportBatch.Status.DISCARDED)
        return qs

    def get_serializer_class(self) -> type[serializers.Serializer]:  # type: ignore[type-arg]
        return ImportBatchListSerializer if self.action == "list" else ImportBatchSerializer

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        upload = request.FILES.get("file")
        if upload is None:
            raise serializers.ValidationError({"file": ["Choose a CSV file."]})
        batch = services.create_csv_batch(upload, filename=upload.name or "")
        return Response(self._detail(batch), status=status.HTTP_201_CREATED)

    def _detail(self, batch: ImportBatch) -> dict[str, Any]:
        batch = self.get_queryset().get(pk=batch.pk)
        return ImportBatchSerializer(batch, context={"request": self.request}).data  # type: ignore[return-value]

    @action(detail=True, methods=["get"])
    def rows(self, request: Request, pk: str | None = None) -> Response:
        batch = self.get_object()
        rows = batch.rows.select_related("unit")
        show = request.query_params.get("show", "")
        if show in ROW_FILTERS:
            rows = rows.filter(ROW_FILTERS[show])
        if q := request.query_params.get("q", "").strip():
            rows = rows.filter(
                Q(serial__icontains=q) | Q(label__icontains=q) | Q(customer_name__icontains=q)
            )
        page = self.paginate_queryset(rows)
        return self.get_paginated_response(ImportRowSerializer(page, many=True).data)

    @action(detail=True, methods=["get", "post"], parser_classes=[MultiPartParser, FormParser])
    def files(self, request: Request, pk: str | None = None) -> Response:
        batch = self.get_object()
        if request.method == "GET":
            return Response(ImportFileSerializer(batch.files.all(), many=True).data)
        upload = request.FILES.get("file")
        if upload is None:
            raise serializers.ValidationError({"file": ["Choose a scanned card to upload."]})
        scan = services.add_scan(batch, upload)
        return Response(ImportFileSerializer(scan).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def validate(self, request: Request, pk: str | None = None) -> Response:
        batch = self.get_object()
        if batch.status != ImportBatch.Status.DRAFT:
            raise serializers.ValidationError({"status": ["This import has already run."]})
        services.validate_batch(batch)
        return Response(self._detail(batch))

    @action(detail=True, methods=["post"])
    def apply(self, request: Request, pk: str | None = None) -> Response:
        batch = self.get_object()
        options = ApplySerializer(data=request.data)
        options.is_valid(raise_exception=True)
        batch = services.start_apply(batch, **options.validated_data)
        return Response(self._detail(batch))

    @action(detail=True, methods=["post"])
    def undo(self, request: Request, pk: str | None = None) -> Response:
        batch = self.get_object()
        if request.user.role != "admin" and batch.created_by_id != request.user.pk:  # type: ignore[attr-defined, union-attr]
            raise PermissionDenied("Only an admin or the person who ran this import can undo it.")
        batch = services.start_undo(batch, request.user)
        return Response(self._detail(batch))

    @action(detail=True, methods=["post"])
    def discard(self, request: Request, pk: str | None = None) -> Response:
        batch = services.discard(self.get_object())
        return Response(self._detail(batch))

    @action(detail=True, methods=["get"])
    def original(self, request: Request, pk: str | None = None) -> FileResponse:
        batch = self.get_object()
        if not batch.original:
            raise Http404
        response = FileResponse(batch.original.open("rb"), content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{batch.filename or "import.csv"}"'
        return response

    @action(detail=False, methods=["get"], url_path="template.csv")
    def template(self, request: Request) -> HttpResponse:
        return _download(formats.template_csv(), "unit-import-template.csv")

    @action(detail=False, methods=["get"], url_path="sample.csv")
    def sample(self, request: Request) -> HttpResponse:
        return _download(formats.sample_csv(), "unit-import-sample.csv")


class ApiKeyViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):  # type: ignore[type-arg]
    permission_classes = [FLAG, CanManageApiKeys]
    serializer_class = ApiKeySerializer
    pagination_class = None
    queryset = ApiKey.objects.select_related("created_by")

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        data = ApiKeySerializer(data=request.data)
        data.is_valid(raise_exception=True)
        key, raw = ApiKey.generate(data.validated_data["name"])
        body = dict(ApiKeySerializer(key).data)
        body["key"] = raw  # shown once, never stored
        return Response(body, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def revoke(self, request: Request, pk: str | None = None) -> Response:
        key = self.get_object()
        if key.revoked_at is None:
            key.revoked_at = timezone.now()
            key.save()
        return Response(ApiKeySerializer(key).data)


# --- Versioned JSON API for the scanning app ------------------------------------------------


def _report(batch: ImportBatch) -> dict[str, Any]:
    batch.refresh_from_db()
    rows = [
        {
            "row": r.row_number,
            "unit_serial": r.serial,
            "status": r.status,
            "plan": r.plan,
            "result": r.result,
            "unit_id": str(r.unit_id) if r.unit_id else None,
            "errors": r.errors,
            "warnings": r.warnings,
        }
        for r in batch.rows.all()
    ]
    return {
        "id": str(batch.pk),
        "status": batch.status,
        "reference": batch.reference,
        "counts": batch.counts,
        "rows": rows,
    }


class ApiView(APIView):
    authentication_classes = [ApiKeyAuthentication]
    permission_classes = [FLAG, HasApiKey]
    throttle_classes = [ApiKeyThrottle]

    def batch_for(self, request: Request, pk: str) -> ImportBatch:
        batch = ImportBatch.objects.filter(pk=pk, api_key=request.auth).first()
        if batch is None:
            raise Http404
        return batch


class ApiImportUnitsView(ApiView):
    def post(self, request: Request) -> Response:
        data = ApiImportSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        opts = data.validated_data
        with acting_as(user=request.user, source="api"):
            batch = services.create_json_batch(
                opts["units"],
                api_key=request.auth,
                reference=opts["reference"],
                on_existing=opts.get("on_existing", ImportBatch.OnExisting.UPDATE),
                skip_invalid=opts.get("skip_invalid", False),
            )
            if opts["dry_run"]:
                return Response(_report(batch), status=status.HTTP_200_OK)
            if batch.counts.get("error") and not batch.skip_invalid:
                services.discard(batch)
                return Response(_report(batch), status=status.HTTP_422_UNPROCESSABLE_ENTITY)
            batch = services.start_apply(batch)
        code = (
            status.HTTP_201_CREATED
            if batch.status == ImportBatch.Status.IMPORTED
            else status.HTTP_202_ACCEPTED
        )
        return Response(_report(batch), status=code)


class ApiBatchView(ApiView):
    def get(self, request: Request, pk: str) -> Response:
        return Response(_report(self.batch_for(request, pk)))


class ApiBatchFilesView(ApiView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request: Request, pk: str) -> Response:
        batch = self.batch_for(request, pk)
        upload = request.FILES.get("file")
        if upload is None:
            raise serializers.ValidationError(
                {"file": ["Send the scan in a multipart field named file."]}
            )
        with acting_as(user=request.user, source="api"):
            scan = services.add_scan(batch, upload)
        return Response(ImportFileSerializer(scan).data, status=status.HTTP_201_CREATED)


class ApiBatchApplyView(ApiView):
    def post(self, request: Request, pk: str) -> Response:
        batch = self.batch_for(request, pk)
        options = ApplySerializer(data=request.data)
        options.is_valid(raise_exception=True)
        with acting_as(user=request.user, source="api"):
            batch = services.start_apply(batch, **options.validated_data)
        code = (
            status.HTTP_201_CREATED
            if batch.status == ImportBatch.Status.IMPORTED
            else status.HTTP_202_ACCEPTED
        )
        return Response(_report(batch), status=code)


class ApiSchemaView(APIView):
    """Public: the format itself is no secret."""

    authentication_classes: list[Any] = []
    permission_classes: list[Any] = []

    def get(self, request: Request) -> Response:
        return Response(formats.json_schema())
