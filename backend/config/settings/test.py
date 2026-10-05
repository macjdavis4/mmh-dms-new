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
    "include_apps": ["accounts", "core", "ops"],
}

# Uploaded files live in memory during tests (no MinIO needed).
STORAGES["default"] = {"BACKEND": "django.core.files.storage.InMemoryStorage"}  # noqa: F405
