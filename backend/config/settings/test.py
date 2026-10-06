from .base import *  # noqa: F403

APP_ENV = "test"
SECRET_KEY = "test-only-secret-key-not-for-production-use-0123456789"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # fast tests
STORAGES["staticfiles"]["BACKEND"] = "django.contrib.staticfiles.storage.StaticFilesStorage"  # noqa: F405
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
LOGGING["root"]["level"] = "WARNING"  # noqa: F405
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]

INSTALLED_APPS = [*INSTALLED_APPS, "django_migration_linter"]  # noqa: F405
MIGRATION_LINTER_OPTIONS = {
    # Only our apps; third-party migrations are their maintainers' business.
    "include_apps": [
        "accounts",
        "core",
        "ops",
        "customers",
        "units",
        "imports",
        "service",
        "sales",
        "parts",
        "reports",
    ],
    # Initial migrations only create brand-new tables, which no running code
    # uses yet. (The linter also misreads GIN indexes in customers/0001.)
    # parts/0008 only adds an expression index to a new, empty table.
    "ignore_name": ["0001_initial", "0008_invoice_unique"],
}

# Uploaded files live in memory during tests (no MinIO needed).
STORAGES["default"] = {"BACKEND": "django.core.files.storage.InMemoryStorage"}  # noqa: F405
PDF_COMPRESS = False  # PDF text readable in tests
INVOICE_READ_INLINE = True
