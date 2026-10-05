"""Settings shared by every environment.

Everything that differs between environments comes from environment
variables. Secrets are never committed; see docs/MANUAL_STEPS.md.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import dj_database_url
import django_stubs_ext
from django.core.exceptions import ImproperlyConfigured

django_stubs_ext.monkeypatch()

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if value is None:
        raise ImproperlyConfigured(f"Environment variable {name} is required")
    return value


def env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


# --- Core -------------------------------------------------------------------

SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-only-insecure-key-change-me")
DEBUG = False
APP_ENV = env("APP_ENV", "development")  # development | test | staging | production
APP_VERSION = env("APP_VERSION", "dev")
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "rest_framework",
    "django_otp",
    "django_otp.plugins.otp_totp",
    "django_otp.plugins.otp_static",
    "axes",
    "csp",
    "procrastinate.contrib.django",
    "apps.core",
    "apps.accounts",
    "apps.search",
    "apps.ops",
]

MIDDLEWARE = [
    "apps.core.middleware.RequestContextMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "apps.core.middleware.SecurityHeadersMiddleware",
    "csp.middleware.CSPMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "apps.core.middleware.AuditActorMiddleware",
    "apps.accounts.middleware.RequireAdminTwoFactorMiddleware",
    "apps.core.middleware.ReadOnlyModeMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Axes must be last so it sees the final response of a failed login.
    "axes.middleware.AxesMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "csp.context_processors.nonce",
            ],
        },
    },
]

# --- Database ---------------------------------------------------------------
# The web app talks to Postgres through DigitalOcean's connection pooler
# (PgBouncer, transaction mode). The worker sets DATABASE_URL to the direct
# connection instead. CONN_HEALTH_CHECKS lets the app reconnect cleanly after
# a database restart or failover.

DATABASES = {
    "default": dj_database_url.parse(
        env("DATABASE_URL", "postgres://mmh:mmh@localhost:5432/mmh"),
        conn_max_age=int(env("DB_CONN_MAX_AGE", "60")),
        conn_health_checks=True,
    )
}
DATABASES["default"].setdefault("OPTIONS", {})
DATABASES["default"]["OPTIONS"]["connect_timeout"] = 5
if os.environ.get("DATABASE_SSLROOTCERT"):
    DATABASES["default"]["OPTIONS"]["sslmode"] = env("DATABASE_SSLMODE", "require")
    DATABASES["default"]["OPTIONS"]["sslrootcert"] = env("DATABASE_SSLROOTCERT")
# PgBouncer in transaction mode cannot hold server-side cursors open.
DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = env_bool("DB_BEHIND_POOLER", False)
DATABASES["default"]["ATOMIC_REQUESTS"] = False

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Used for login throttling (DRF) and anything else that needs a shared cache.
# Database-backed so the app stays stateless and Redis-free.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "django_cache",
    }
}

# --- Auth -------------------------------------------------------------------

AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_NAME = "mmh_session"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 60 * 60 * 12  # one working day
SESSION_SAVE_EVERY_REQUEST = True  # sliding expiry while people are active
CSRF_COOKIE_NAME = "mmh_csrftoken"
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_HEADER_NAME = "HTTP_X_CSRFTOKEN"

# Lock an account for 15 minutes after 5 failed logins.
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 0.25  # hours
AXES_LOCKOUT_PARAMETERS = ["username"]
AXES_USERNAME_FORM_FIELD = "username"
AXES_USERNAME_CALLABLE = "apps.accounts.authentication.axes_username"
AXES_RESET_ON_SUCCESS = True
AXES_ENABLE_ACCESS_FAILURE_LOG = True
AXES_LOCKOUT_CALLABLE = "apps.accounts.views.lockout_response"
AXES_IPWARE_META_PRECEDENCE_ORDER = ["HTTP_X_REAL_IP", "REMOTE_ADDR"]

OTP_TOTP_ISSUER = "Maine Material Handling DMS"
# Pre-2FA login state (password accepted, code pending) expires after this.
LOGIN_OTP_WINDOW_SECONDS = 300

# --- REST framework -----------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.accounts.authentication.CsrfSessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "apps.accounts.permissions.IsAuthenticatedAndVerified",
    ],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.StandardPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_THROTTLE_RATES": {
        "login": "10/min",
        "otp": "10/min",
    },
    "EXCEPTION_HANDLER": "apps.core.exceptions.exception_handler",
    "UNAUTHENTICATED_USER": "django.contrib.auth.models.AnonymousUser",
}

# --- Static files and the React app ------------------------------------------
# Vite builds the frontend into frontend_dist/ with base "/static/".
# WhiteNoise serves it from the same origin as the API.

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [d for d in [BASE_DIR / "frontend_dist"] if d.exists()]
STORAGES: dict[str, dict[str, Any]] = {
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": env("MEDIA_BUCKET", "mmh-media"),
            "endpoint_url": env("S3_ENDPOINT_URL", "http://localhost:9000"),
            "access_key": env("S3_ACCESS_KEY_ID", "minioadmin"),
            "secret_key": env("S3_SECRET_ACCESS_KEY", "minioadmin"),
            "region_name": env("S3_REGION", "us-east-1"),
            "default_acl": "private",
            "querystring_auth": True,
            "querystring_expire": 900,
            "file_overwrite": False,
        },
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
WHITENOISE_MAX_AGE = 60 * 60 * 24 * 365

# --- Background jobs and backups ---------------------------------------------

PROCRASTINATE_IMPORT_PATHS = ["apps.ops.tasks"]
BACKUP_BUCKET = env("BACKUP_BUCKET", "mmh-backups")
BACKUP_S3_ENDPOINT_URL = env(
    "BACKUP_S3_ENDPOINT_URL", env("S3_ENDPOINT_URL", "http://localhost:9000")
)
BACKUP_S3_REGION = env("BACKUP_S3_REGION", env("S3_REGION", "us-east-1"))
BACKUP_S3_ACCESS_KEY_ID = env("BACKUP_S3_ACCESS_KEY_ID", env("S3_ACCESS_KEY_ID", "minioadmin"))
BACKUP_S3_SECRET_ACCESS_KEY = env(
    "BACKUP_S3_SECRET_ACCESS_KEY", env("S3_SECRET_ACCESS_KEY", "minioadmin")
)
# age public key (age1...). Backups are encrypted to it; the matching private
# key is kept offline and in the restore-test GitHub environment only.
BACKUP_AGE_RECIPIENT = env("BACKUP_AGE_RECIPIENT", "")
# A dedicated direct (non-pooled) connection string used by pg_dump.
BACKUP_DATABASE_URL = env(
    "BACKUP_DATABASE_URL", env("DATABASE_URL", "postgres://mmh:mmh@localhost:5432/mmh")
)

# --- Security headers ---------------------------------------------------------

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

SENTRY_DSN = env("SENTRY_DSN", "")
SENTRY_FRONTEND_DSN = env("SENTRY_FRONTEND_DSN", SENTRY_DSN)


def _sentry_origin(dsn: str) -> list[str]:
    if not dsn:
        return []
    parsed = urlparse(dsn)
    return [f"{parsed.scheme}://{parsed.hostname}"]


CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": ["'self'"],
        "script-src": ["'self'"],
        "style-src": ["'self'"],
        "img-src": ["'self'", "data:", "blob:", *env_list("CSP_IMG_SRC_EXTRA")],
        "font-src": ["'self'"],
        "connect-src": ["'self'", *_sentry_origin(SENTRY_FRONTEND_DSN)],
        "frame-ancestors": ["'none'"],
        "form-action": ["'self'"],
        "base-uri": ["'self'"],
        "object-src": ["'none'"],
    }
}

# --- Logging ------------------------------------------------------------------
# One JSON object per line on stdout. Docker ships it to the DO monitoring
# agent / journald. Each line carries the request ID.

LOG_LEVEL = env("LOG_LEVEL", "INFO")
LOGGING: dict[str, Any] = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"request_context": {"()": "apps.core.logging.RequestContextFilter"}},
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.json.JsonFormatter",
            "fmt": "%(asctime)s %(levelname)s %(name)s %(message)s",
            "rename_fields": {"asctime": "ts", "levelname": "level", "name": "logger"},
        },
    },
    "handlers": {
        "stdout": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "filters": ["request_context"],
        },
    },
    "root": {"handlers": ["stdout"], "level": LOG_LEVEL},
    "loggers": {
        "django.request": {"level": "ERROR"},
        "django.server": {"level": "WARNING"},
        "axes": {"level": "WARNING"},
    },
}

# --- Internationalization -----------------------------------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = "America/New_York"
USE_I18N = False
USE_TZ = True

SILENCED_SYSTEM_CHECKS = [
    # Email uniqueness is enforced case-insensitively by a database constraint
    # (user_email_unique_ci), which Django's check does not recognise.
    "auth.W004",
    # Accounts lock by email. Locking by IP too would lock the whole shop
    # (one office IP) after a few typos; per-IP rate limiting on the login
    # endpoint (DRF throttle) and Cloudflare cover IP-based abuse instead.
    "axes.W006",
]
