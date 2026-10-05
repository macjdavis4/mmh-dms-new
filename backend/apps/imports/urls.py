from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter(trailing_slash=False)
router.register("imports/batches", views.ImportBatchViewSet, basename="import-batches")
router.register("admin/api-keys", views.ApiKeyViewSet, basename="api-keys")

urlpatterns = [
    *router.urls,
    # Versioned, API-key authenticated import API (for the scanning app).
    path("import/v1/units", views.ApiImportUnitsView.as_view(), name="import-api-units"),
    path("import/v1/batches/<uuid:pk>", views.ApiBatchView.as_view(), name="import-api-batch"),
    path(
        "import/v1/batches/<uuid:pk>/files",
        views.ApiBatchFilesView.as_view(),
        name="import-api-files",
    ),
    path(
        "import/v1/batches/<uuid:pk>/apply",
        views.ApiBatchApplyView.as_view(),
        name="import-api-apply",
    ),
    path("import/v1/schema.json", views.ApiSchemaView.as_view(), name="import-api-schema"),
]
