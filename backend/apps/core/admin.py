from django.contrib import admin

from .models import AuditLog, FeatureFlag, SiteSettings


class NoDeleteAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """Soft-delete tables: the database refuses real deletes anyway."""

    def has_delete_permission(self, request, obj=None):  # type: ignore[no-untyped-def]
        return False


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin[AuditLog]):
    list_display = ["at", "action", "actor", "object_repr", "ip"]
    list_filter = ["action"]
    search_fields = ["object_repr", "object_id", "request_id"]

    def has_add_permission(self, request):  # type: ignore[no-untyped-def]
        return False

    def has_change_permission(self, request, obj=None):  # type: ignore[no-untyped-def]
        return False

    def has_delete_permission(self, request, obj=None):  # type: ignore[no-untyped-def]
        return False


@admin.register(FeatureFlag)
class FeatureFlagAdmin(admin.ModelAdmin[FeatureFlag]):
    list_display = ["key", "enabled", "roles", "description"]

    def has_delete_permission(self, request, obj=None):  # type: ignore[no-untyped-def]
        return False


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin[SiteSettings]):
    def has_delete_permission(self, request, obj=None):  # type: ignore[no-untyped-def]
        return False
