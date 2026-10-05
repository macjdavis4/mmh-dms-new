from django.contrib import admin

from apps.core.admin import NoDeleteAdmin

from .models import ApiKey, ImportBatch


@admin.register(ImportBatch)
class ImportBatchAdmin(NoDeleteAdmin):
    list_display = ["created_at", "source", "filename", "status", "row_count"]
    list_filter = ["status", "source"]
    readonly_fields = [f.name for f in ImportBatch._meta.fields]


@admin.register(ApiKey)
class ApiKeyAdmin(NoDeleteAdmin):
    list_display = ["name", "prefix", "created_at", "last_used_at", "revoked_at"]
    readonly_fields = ["prefix", "key_hash", "last_used_at"]
