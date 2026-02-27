from __future__ import annotations

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from .settings import *  # noqa: F403,F401


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or str(value).strip() == "":
        raise ImproperlyConfigured(f"Missing required environment variable: {name}")
    return value


def _require_bool(name: str) -> bool:
    raw = _require_env(name)
    return raw.strip().lower() in ("1", "true", "yes", "on")


DEBUG = False
ENVIRONMENT = "production"

BASE_DIR = Path(__file__).resolve().parent.parent  # noqa: F405

SECRET_KEY = _require_env("DJANGO_SECRET_KEY")
WASSLA_BASE_DOMAIN = _require_env("WASSLA_BASE_DOMAIN").strip().lower()
ALLOWED_HOSTS = [h.strip() for h in _require_env("DJANGO_ALLOWED_HOSTS").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [h.strip() for h in _require_env("DJANGO_CSRF_TRUSTED_ORIGINS").split(",") if h.strip()]

# Ensure custom domain policies use the production base domain.
CUSTOM_DOMAIN_BLOCKED_DOMAINS = [WASSLA_BASE_DOMAIN]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": _require_env("PG_DB_NAME"),
        "USER": _require_env("PG_DB_USER"),
        "PASSWORD": _require_env("PG_DB_PASSWORD"),
        "HOST": _require_env("PG_DB_HOST"),
        "PORT": _require_env("PG_DB_PORT"),
    }
}

STATIC_URL = "/static/"
STATIC_ROOT = Path(_require_env("DJANGO_STATIC_ROOT"))
MEDIA_URL = "/media/"
MEDIA_ROOT = Path(_require_env("DJANGO_MEDIA_ROOT"))

EMAIL_BACKEND = _require_env("EMAIL_BACKEND")
EMAIL_HOST = _require_env("EMAIL_HOST")
EMAIL_PORT = int(_require_env("EMAIL_PORT"))
EMAIL_USE_TLS = _require_bool("EMAIL_USE_TLS")
EMAIL_HOST_USER = _require_env("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = _require_env("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = _require_env("DEFAULT_FROM_EMAIL")
SERVER_EMAIL = _require_env("SERVER_EMAIL")

SECURE_SSL_REDIRECT = _require_bool("DJANGO_SECURE_SSL_REDIRECT")
SESSION_COOKIE_SECURE = _require_bool("DJANGO_SESSION_COOKIE_SECURE")
CSRF_COOKIE_SECURE = _require_bool("DJANGO_CSRF_COOKIE_SECURE")
SECURE_HSTS_SECONDS = int(_require_env("DJANGO_SECURE_HSTS_SECONDS"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = _require_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS")
SECURE_HSTS_PRELOAD = _require_bool("DJANGO_SECURE_HSTS_PRELOAD")
SECURE_REFERRER_POLICY = _require_env("DJANGO_SECURE_REFERRER_POLICY")
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = _require_env("DJANGO_X_FRAME_OPTIONS")

CELERY_BROKER_URL = _require_env("CELERY_BROKER_URL")
CELERY_RESULT_BACKEND = _require_env("CELERY_RESULT_BACKEND")

LOG_LEVEL = _require_env("LOG_LEVEL")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "apps.observability.logging.JSONFormatter",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": LOG_LEVEL,
    },
    "loggers": {
        "wasla.request": {
            "handlers": ["console"],
            "level": os.getenv("WASLA_REQUEST_LOG_LEVEL", LOG_LEVEL),
            "propagate": False,
        },
        "wasla.performance": {
            "handlers": ["console"],
            "level": os.getenv("WASLA_PERFORMANCE_LOG_LEVEL", LOG_LEVEL),
            "propagate": False,
        },
    },
}
