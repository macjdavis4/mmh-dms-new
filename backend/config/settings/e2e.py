"""Settings for Playwright runs: production-like (DEBUG off, built frontend,
WhiteNoise, CSP) but over plain HTTP on localhost."""

from .base import *  # noqa: F403

APP_ENV = "e2e"
DEBUG = False
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
CSRF_TRUSTED_ORIGINS = ["http://localhost:8000", "http://127.0.0.1:8000"]
STORAGES["staticfiles"]["BACKEND"] = "whitenoise.storage.CompressedStaticFilesStorage"  # noqa: F405
WHITENOISE_USE_FINDERS = True
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {"login": "1000/min", "otp": "1000/min"}  # noqa: F405
