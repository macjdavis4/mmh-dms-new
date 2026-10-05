from django.contrib import admin

from .models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin[User]):
    list_display = ["email", "first_name", "last_name", "role", "is_active", "last_login"]
    list_filter = ["role", "is_active"]
    search_fields = ["email", "first_name", "last_name"]
    fields = ["email", "first_name", "last_name", "phone", "role", "is_active"]

    def has_delete_permission(self, request, obj=None):  # type: ignore[no-untyped-def]
        return False
