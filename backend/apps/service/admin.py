from django.contrib import admin

from apps.core.admin import NoDeleteAdmin

from .models import LaborLine, WorkOrder


class LaborInline(admin.TabularInline):  # type: ignore[type-arg]
    model = LaborLine
    extra = 0
    can_delete = False


@admin.register(WorkOrder)
class WorkOrderAdmin(NoDeleteAdmin):
    list_display = ["number", "unit", "customer", "status", "opened_on"]
    list_filter = ["status", "kind"]
    search_fields = ["number", "unit__serial_number"]
    inlines = [LaborInline]
