from django.contrib import admin

from apps.core.admin import NoDeleteAdmin

from .models import Address, Contact, Customer


@admin.register(Customer)
class CustomerAdmin(NoDeleteAdmin):
    list_display = ["name", "account_number", "phone", "kind"]
    search_fields = ["name", "account_number", "phone"]


admin.site.register(Contact, NoDeleteAdmin)
admin.site.register(Address, NoDeleteAdmin)
