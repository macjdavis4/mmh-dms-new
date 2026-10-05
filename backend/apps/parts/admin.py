from django.contrib import admin

from .models import Bin, CrossReference, Part


@admin.register(Part)
class PartAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["part_number", "manufacturer", "description", "category"]
    list_filter = ["category"]
    search_fields = ["part_number", "description"]


admin.site.register(Bin)
admin.site.register(CrossReference)
