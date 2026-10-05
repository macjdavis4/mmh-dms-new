from django.contrib import admin

from apps.core.admin import NoDeleteAdmin

from .models import (
    HourMeterReading,
    OwnershipRecord,
    Unit,
    UnitAttachment,
    UnitComponent,
    UnitFile,
    UnitFork,
)


@admin.register(Unit)
class UnitAdmin(NoDeleteAdmin):
    list_display = ["make", "model", "serial_number", "stock_status", "needs_review"]
    list_filter = ["stock_status", "condition", "needs_review"]
    search_fields = ["serial_number", "stock_number", "model"]


for model in (UnitComponent, UnitFork, UnitAttachment, HourMeterReading, OwnershipRecord, UnitFile):
    admin.site.register(model, NoDeleteAdmin)
