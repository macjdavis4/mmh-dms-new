from django.apps import AppConfig


class CustomersConfig(AppConfig):
    name = "apps.customers"
    label = "customers"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from apps.search import registry

        from .search import search_customers

        registry.register("customer", search_customers)
