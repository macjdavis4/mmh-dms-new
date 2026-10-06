"""Settings for Playwright runs: production-like (DEBUG off, built frontend,
WhiteNoise, CSP) but over plain HTTP on localhost."""

from .base import *  # noqa: F403

APP_ENV = "e2e"
DEBUG = False
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
CSRF_TRUSTED_ORIGINS = ["http://localhost:8000", "http://127.0.0.1:8000"]
STORAGES["staticfiles"]["BACKEND"] = "whitenoise.storage.CompressedStaticFilesStorage"  # noqa: F405
WHITENOISE_USE_FINDERS = True
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"].update({"login": "1000/min", "otp": "1000/min"})  # type: ignore[attr-defined]  # noqa: F405
WHITENOISE_AUTOREFRESH = True  # pick up rebuilt frontend files without a restart

# Uploaded files on local disk for Playwright runs (CI has no MinIO). The S3
# storage path is used in development (MinIO) and production (Spaces).
STORAGES["default"] = {  # noqa: F405
    "BACKEND": "django.core.files.storage.FileSystemStorage",
    "OPTIONS": {"location": "/tmp/mmh-e2e-media"},  # noqa: S108 - throwaway test files
}
INVOICE_READ_INLINE = True  # no worker in Playwright runs
