from django.urls import path

from .views import PaperBackupFileView, PaperBackupListView

urlpatterns = [
    path("admin/paper-backups", PaperBackupListView.as_view(), name="paper-backups"),
    path(
        "admin/paper-backups/<uuid:pk>/<str:name>",
        PaperBackupFileView.as_view(),
        name="paper-backup-file",
    ),
]
