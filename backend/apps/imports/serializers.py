from __future__ import annotations

from typing import Any

from rest_framework import serializers

from .columns import BY_NAME, normalize_header
from .models import ApiKey, ImportBatch, ImportFile, ImportRow


def _name(user: Any) -> str:
    if user is None:
        return ""
    return getattr(user, "full_name", "") or getattr(user, "email", "")


class ImportFileSerializer(serializers.ModelSerializer):  # type: ignore[type-arg]
    class Meta:
        model = ImportFile
        fields = ["id", "original_name", "content_type", "size_bytes", "created_at"]


class ImportBatchSerializer(serializers.ModelSerializer):  # type: ignore[type-arg]
    source_label = serializers.CharField(source="get_source_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    created_by_name = serializers.SerializerMethodField()
    undone_by_name = serializers.SerializerMethodField()
    api_key_name = serializers.SerializerMethodField()
    files = ImportFileSerializer(many=True, read_only=True)
    can_undo = serializers.SerializerMethodField()

    class Meta:
        model = ImportBatch
        fields = [
            "id",
            "source",
            "source_label",
            "status",
            "status_label",
            "filename",
            "reference",
            "on_existing",
            "skip_invalid",
            "file_messages",
            "counts",
            "row_count",
            "created_at",
            "created_by_name",
            "validated_at",
            "started_at",
            "finished_at",
            "undone_at",
            "undone_by_name",
            "api_key_name",
            "error",
            "files",
            "can_undo",
        ]
        read_only_fields = fields

    def get_created_by_name(self, obj: ImportBatch) -> str:
        return _name(obj.created_by)  # type: ignore[attr-defined]

    def get_undone_by_name(self, obj: ImportBatch) -> str:
        return _name(obj.undone_by)

    def get_api_key_name(self, obj: ImportBatch) -> str:
        return obj.api_key.name if obj.api_key else ""

    def get_can_undo(self, obj: ImportBatch) -> bool:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if (
            obj.status not in (ImportBatch.Status.IMPORTED, ImportBatch.Status.FAILED)
            or user is None
        ):
            return False
        return getattr(user, "role", "") == "admin" or obj.created_by_id == user.pk  # type: ignore[attr-defined]


class ImportBatchListSerializer(ImportBatchSerializer):
    class Meta(ImportBatchSerializer.Meta):
        fields = [
            f for f in ImportBatchSerializer.Meta.fields if f not in ("files", "file_messages")
        ]
        read_only_fields = fields


class ImportRowSerializer(serializers.ModelSerializer):  # type: ignore[type-arg]
    plan_label = serializers.CharField(source="get_plan_display", read_only=True)
    result_label = serializers.CharField(source="get_result_display", read_only=True)

    class Meta:
        model = ImportRow
        fields = [
            "id",
            "row_number",
            "status",
            "plan",
            "plan_label",
            "errors",
            "warnings",
            "changes",
            "serial",
            "label",
            "customer_name",
            "unit",
            "result",
            "result_label",
            "undo_result",
        ]
        read_only_fields = fields


class ApplySerializer(serializers.Serializer):  # type: ignore[type-arg]
    on_existing = serializers.ChoiceField(choices=ImportBatch.OnExisting.choices, required=False)
    skip_invalid = serializers.BooleanField(required=False)


class ApiImportSerializer(ApplySerializer):
    units = serializers.ListField(child=serializers.DictField(), min_length=1, max_length=1000)
    reference = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    dry_run = serializers.BooleanField(required=False, default=False)

    def validate_units(self, units: list[dict[str, Any]]) -> list[dict[str, Any]]:
        unknown = sorted(
            {k for unit in units for k in unit if normalize_header(str(k)) not in BY_NAME}
        )
        if unknown:
            raise serializers.ValidationError(
                f"Unknown keys: {', '.join(unknown[:20])}. See the import schema."
            )
        return units


class ApiKeySerializer(serializers.ModelSerializer):  # type: ignore[type-arg]
    created_by_name = serializers.SerializerMethodField()
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = ApiKey
        fields = [
            "id",
            "name",
            "prefix",
            "created_at",
            "created_by_name",
            "last_used_at",
            "revoked_at",
            "is_active",
        ]
        read_only_fields = [
            "id",
            "prefix",
            "created_at",
            "created_by_name",
            "last_used_at",
            "revoked_at",
            "is_active",
        ]

    def get_created_by_name(self, obj: ApiKey) -> str:
        return _name(obj.created_by)  # type: ignore[attr-defined]

    def validate_name(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Give the key a name, e.g. “Card scanner tablet”.")
        return value
