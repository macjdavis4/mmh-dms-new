from django.apps import AppConfig


class ServiceConfig(AppConfig):
    name = "apps.service"
    label = "service"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from apps.search import registry

        from .search import search_work_orders

        registry.register("work_order", search_work_orders)
