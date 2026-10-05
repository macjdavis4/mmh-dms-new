from django.contrib import admin
from django.urls import include, path, re_path
from django_otp.admin import OTPAdminSite

from apps.core import health
from apps.core.views import spa_index

# The Django admin requires a 2FA code, not just a password.
admin.site.__class__ = OTPAdminSite

urlpatterns = [
    path("healthz", health.healthz, name="healthz"),
    path("readyz", health.readyz, name="readyz"),
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.core.urls")),
    path("api/v1/search", include("apps.search.urls")),
    path("api/v1/", include("apps.customers.urls")),
    path("api/v1/", include("apps.units.urls")),
    path("api/v1/", include("apps.imports.urls")),
    path("api/v1/", include("apps.service.urls")),
    # Django admin is kept as an emergency tool for admins (2FA enforced).
    path("django-admin/", admin.site.urls),
    # Everything else is the React app; it handles its own routing and 404s.
    re_path(r"^(?!api/|static/|django-admin/).*$", spa_index, name="spa"),
]
