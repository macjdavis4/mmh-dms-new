from django.urls import URLPattern, URLResolver, path
from rest_framework.routers import SimpleRouter

from apps.accounts.admin_api import UserAdminViewSet

from . import views

router = SimpleRouter(trailing_slash=False)
router.register("admin/users", UserAdminViewSet, basename="admin-users")

urlpatterns: list[URLPattern | URLResolver] = [
    path("system/status", views.SystemStatusView.as_view(), name="system-status"),
    path("feature-flags", views.FeatureFlagsView.as_view(), name="feature-flags"),
    path("admin/site-settings", views.SiteSettingsView.as_view(), name="site-settings"),
    path("admin/audit-log", views.AuditLogListView.as_view(), name="audit-log"),
    path("admin/health", views.AdminHealthView.as_view(), name="admin-health"),
]
urlpatterns += router.urls
