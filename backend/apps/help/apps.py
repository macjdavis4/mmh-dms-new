from django.apps import AppConfig


class HelpConfig(AppConfig):
    name = "apps.help"
    label = "help"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from apps.search import registry

        from .search import search_help

        registry.register("help", search_help)
