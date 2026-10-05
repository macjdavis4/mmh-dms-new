from django.apps import AppConfig


class PartsConfig(AppConfig):
    name = "apps.parts"
    label = "parts"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from apps.search import registry

        from .search import search_parts

        registry.register("part", search_parts)
