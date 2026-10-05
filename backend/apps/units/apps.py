from django.apps import AppConfig


class UnitsConfig(AppConfig):
    name = "apps.units"
    label = "units"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from apps.search import registry

        from .search import search_units

        registry.register("unit", search_units)
