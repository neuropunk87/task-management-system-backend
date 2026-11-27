"""Django settings for the task management service."""

import os
import ssl
from ipaddress import ip_network
from datetime import timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import dj_database_url
import environ
from django.core.exceptions import ImproperlyConfigured


BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env()
environ.Env.read_env(str(BASE_DIR / ".env"))


def csv_setting(name, default=""):
    return [item.strip() for item in env(name, default=default).split(",") if item.strip()]


IS_HEROKU = bool(os.environ.get("DYNO"))
ENVIRONMENT = env("DJANGO_ENV", default="production" if IS_HEROKU else "development").lower()
if ENVIRONMENT not in {"development", "test", "production"}:
    raise ImproperlyConfigured("DJANGO_ENV must be development, test or production.")
IS_PRODUCTION = ENVIRONMENT == "production"

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = csv_setting(
    "ALLOWED_HOSTS",
    default="" if IS_PRODUCTION else "localhost,127.0.0.1,[::1]",
)

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesBackend",
    "django.contrib.auth.backends.ModelBackend",
]
AUTH_USER_MODEL = "users.CustomUser"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "django_filters",
    "django_celery_beat",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "corsheaders",
    "axes",
    "users",
    "projects",
    "tasks.apps.TasksConfig",
    "notifications.apps.NotificationsConfig",
    "analytics.apps.AnalyticsConfig",
]

MIDDLEWARE = [
    "task_management_system.middleware.GetRemoteAddrMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "axes.middleware.AxesMiddleware",
    "task_management_system.middleware.RoleBasedAccessMiddleware",
    "task_management_system.middleware.PrivateAPIResponseMiddleware",
]

CORS_ALLOWED_ORIGINS = csv_setting("CORS_ALLOWED_ORIGINS")
CORS_ALLOW_CREDENTIALS = env.bool("CORS_ALLOW_CREDENTIALS", default=False)
CORS_ALLOW_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
CSRF_TRUSTED_ORIGINS = csv_setting("CSRF_TRUSTED_ORIGINS")

AXES_FAILURE_LIMIT = env.int("AXES_FAILURE_LIMIT", default=5)
AXES_COOLOFF_TIME = env.float("AXES_COOLOFF_TIME", default=1.0)
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_PARAMETERS = ["ip_address", "username"]
AXES_CLIENT_IP_CALLABLE = "task_management_system.middleware.client_ip"

TRUST_X_FORWARDED_FOR = env.bool("TRUST_X_FORWARDED_FOR", default=IS_HEROKU)
TRUSTED_PROXY_COUNT = max(1, env.int("TRUSTED_PROXY_COUNT", default=1))
TRUST_X_FORWARDED_PROTO = env.bool("TRUST_X_FORWARDED_PROTO", default=IS_HEROKU)
TRUSTED_PROXY_IPS = csv_setting(
    "TRUSTED_PROXY_IPS",
    default="10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,127.0.0.1,::1" if IS_HEROKU else "127.0.0.1,::1",
)
for network in TRUSTED_PROXY_IPS:
    try:
        ip_network(network)
    except ValueError as exc:
        raise ImproperlyConfigured("TRUSTED_PROXY_IPS must contain IPs or CIDR networks.") from exc

ROOT_URLCONF = "task_management_system.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            BASE_DIR / "task_management_system/templates",
            BASE_DIR / "analytics/templates",
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]
WSGI_APPLICATION = "task_management_system.wsgi.application"

database_url = env("DATABASE_URL", default="")
if database_url:
    DATABASES = {
        "default": dj_database_url.parse(
            database_url,
            conn_max_age=600,
            conn_health_checks=True,
            ssl_require=False,
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("POSTGRES_DB", default="task_management_db"),
            "USER": env("POSTGRES_USER", default="postgres"),
            "PASSWORD": env("POSTGRES_PASSWORD", default=""),
            "HOST": env("POSTGRES_HOST", default="127.0.0.1"),
            "PORT": env("POSTGRES_PORT", default="5432"),
            "CONN_MAX_AGE": 60,
            "CONN_HEALTH_CHECKS": True,
        }
    }

if IS_PRODUCTION:
    if DATABASES["default"]["ENGINE"] != "django.db.backends.postgresql":
        raise ImproperlyConfigured("Production requires PostgreSQL.")
    db_sslmode = env("POSTGRES_SSLMODE", default=DATABASES["default"].get("OPTIONS", {}).get("sslmode", "require"))
    if db_sslmode not in {"require", "verify-ca", "verify-full"}:
        raise ImproperlyConfigured("Production PostgreSQL must use TLS.")
    DATABASES["default"].setdefault("OPTIONS", {})["sslmode"] = db_sslmode
    if env("POSTGRES_SSLROOTCERT", default=""):
        DATABASES["default"]["OPTIONS"]["sslrootcert"] = env("POSTGRES_SSLROOTCERT")

redis_url = env("REDIS_TLS_URL", default=env("REDIS_URL", default="redis://127.0.0.1:6379/0"))
CELERY_BROKER_URL = env("REDIS_BROKER_URL", default=redis_url)
CELERY_RESULT_BACKEND = env("REDIS_RESULT_BACKEND", default=redis_url)
CELERY_CACHE_BACKEND = env("REDIS_CACHE_BACKEND", default=redis_url)
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers.DatabaseScheduler"
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "Europe/Kyiv"
CELERY_ENABLE_UTC = True
CELERY_TASK_SOFT_TIME_LIMIT = 60
CELERY_TASK_TIME_LIMIT = 90
CELERY_RESULT_EXPIRES = 3600
CELERY_BROKER_CONNECTION_TIMEOUT = 5
CELERY_BROKER_TRANSPORT_OPTIONS = {"socket_connect_timeout": 5, "socket_timeout": 5}
CELERY_TASK_PUBLISH_RETRY_POLICY = {"max_retries": 2, "interval_start": 0, "interval_step": 0.5, "interval_max": 1}
CELERY_WORKER_ENABLE_REMOTE_CONTROL = False
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_WORKER_HIJACK_ROOT_LOGGER = False
CELERY_WORKER_REDIRECT_STDOUTS = False

HEROKU_REDIS_COMPATIBILITY = env.bool(
    "HEROKU_REDIS_COMPATIBILITY",
    # User-approved compatibility with the provider's self-signed certificate.
    default=IS_HEROKU and not env("REDIS_SSL_CA_CERTS", default=""),
)
if HEROKU_REDIS_COMPATIBILITY and not IS_HEROKU:
    raise ImproperlyConfigured("Heroku Redis compatibility is restricted to the Heroku runtime.")
REDIS_CERT_REQUIREMENTS = ssl.CERT_NONE if HEROKU_REDIS_COMPATIBILITY else ssl.CERT_REQUIRED
cache_options = {
    "CLIENT_CLASS": "django_redis.client.DefaultClient",
    "SOCKET_CONNECT_TIMEOUT": 5,
    "SOCKET_TIMEOUT": 5,
}
if CELERY_CACHE_BACKEND.startswith("rediss://"):
    cache_options["CONNECTION_POOL_KWARGS"] = {"ssl_cert_reqs": REDIS_CERT_REQUIREMENTS}
if CELERY_BROKER_URL.startswith("rediss://"):
    CELERY_BROKER_USE_SSL = {"ssl_cert_reqs": REDIS_CERT_REQUIREMENTS}
if CELERY_RESULT_BACKEND.startswith("rediss://"):
    CELERY_REDIS_BACKEND_USE_SSL = {"ssl_cert_reqs": REDIS_CERT_REQUIREMENTS}
redis_ca = env("REDIS_SSL_CA_CERTS", default="")
if redis_ca:
    cache_options.setdefault("CONNECTION_POOL_KWARGS", {})["ssl_ca_certs"] = redis_ca
    if CELERY_BROKER_URL.startswith("rediss://"):
        CELERY_BROKER_USE_SSL["ssl_ca_certs"] = redis_ca
    if CELERY_RESULT_BACKEND.startswith("rediss://"):
        CELERY_REDIS_BACKEND_USE_SSL["ssl_ca_certs"] = redis_ca

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": CELERY_CACHE_BACKEND,
        "OPTIONS": cache_options,
        "KEY_PREFIX": "task_management_system",
    }
}

EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = env("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", default=False)
EMAIL_TIMEOUT = env.int("EMAIL_TIMEOUT", default=15)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@localhost")

TELEGRAM_BOT_TOKEN = env("TELEGRAM_BOT_TOKEN", default="")
TELEGRAM_BOT_USERNAME = env("TELEGRAM_BOT_USERNAME", default="").lstrip("@")
TELEGRAM_LINK_TOKEN_TTL_MINUTES = max(
    1, min(env.int("TELEGRAM_LINK_TOKEN_TTL_MINUTES", default=10), 60)
)

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Europe/Kyiv"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
WHITENOISE_ROOT = BASE_DIR / "public"
STATICFILES_DIRS = [("branding", WHITENOISE_ROOT)]
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}
DATA_UPLOAD_MAX_MEMORY_SIZE = 2_621_440
FILE_UPLOAD_MAX_MEMORY_SIZE = 2_621_440
FILE_UPLOAD_HANDLERS = [
    "task_management_system.uploads.LimitedUploadHandler",
    "django.core.files.uploadhandler.MemoryFileUploadHandler",
    "django.core.files.uploadhandler.TemporaryFileUploadHandler",
]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

if IS_PRODUCTION:
    SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31_536_000)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool(
        "SECURE_HSTS_INCLUDE_SUBDOMAINS", default=True
    )
    SECURE_HSTS_PRELOAD = env.bool("SECURE_HSTS_PRELOAD", default=True)
    if TRUST_X_FORWARDED_PROTO:
        SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

REST_FRAMEWORK = {
    "NUM_PROXIES": 0,
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PARSER_CLASSES": ["task_management_system.parsers.LimitedJSONParser"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "30/minute",
        "user": "300/minute",
        "login": "10/minute",
        "registration": "5/hour",
        "refresh": "30/minute",
        "credential_change": "5/hour",
        "avatar_upload": "10/hour",
        "telegram_link": "5/hour",
    },
}

JWT_REVOCATION_CHECK_ENABLED = True
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": False,
    "CHECK_REVOKE_TOKEN": JWT_REVOCATION_CHECK_ENABLED,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Task Management API",
    "DESCRIPTION": "API documentation for the Task Management system",
    "VERSION": "1.0.0",
    "SWAGGER_UI_FAVICON_HREF": "/favicon.ico",
    "SERVE_INCLUDE_SCHEMA": False,
    "ENUM_NAME_OVERRIDES": {
        "ProjectStatusEnum": "projects.models.Project.Status",
        "TaskStatusEnum": "tasks.models.Task.Status",
    },
}

API_DOCS_PUBLIC = env.bool("API_DOCS_PUBLIC", default=not IS_PRODUCTION)
ENABLE_API_DOCS = env.bool("ENABLE_API_DOCS", default=not IS_PRODUCTION)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"safe": {"()": "task_management_system.logging.RedactingFormatter"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "safe"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", default="INFO")},
    "loggers": {
        "django": {
            "handlers": ["console"], "level": env("LOG_LEVEL", default="INFO"),
            "propagate": False,
        },
        "django.server": {
            "handlers": ["console"], "level": env("LOG_LEVEL", default="INFO"),
            "propagate": False,
        },
        "httpx": {"level": "WARNING"},
        "httpcore": {"level": "WARNING"},
    },
}

if EMAIL_USE_TLS and EMAIL_USE_SSL:
    raise ImproperlyConfigured("EMAIL_USE_TLS and EMAIL_USE_SSL cannot both be true.")
if IS_PRODUCTION:
    if DEBUG:
        raise ImproperlyConfigured("DEBUG must be false in production.")
    if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
        raise ImproperlyConfigured("ALLOWED_HOSTS must be configured in production.")
    if not database_url and not DATABASES["default"]["PASSWORD"]:
        raise ImproperlyConfigured(
            "DATABASE_URL or POSTGRES_PASSWORD must be configured in production."
        )
    insecure_redis = [
        name
        for name, value in {
            "REDIS_BROKER_URL": CELERY_BROKER_URL,
            "REDIS_RESULT_BACKEND": CELERY_RESULT_BACKEND,
            "REDIS_CACHE_BACKEND": CELERY_CACHE_BACKEND,
        }.items()
        if not value.startswith("rediss://")
    ]
    if insecure_redis:
        raise ImproperlyConfigured(
            f"TLS is required for production Redis URLs: {', '.join(insecure_redis)}."
        )
    for redis_connection_url in (CELERY_BROKER_URL, CELERY_RESULT_BACKEND, CELERY_CACHE_BACKEND):
        cert_mode = parse_qs(urlsplit(redis_connection_url).query).get("ssl_cert_reqs", ["required"])[0]
        if not HEROKU_REDIS_COMPATIBILITY and cert_mode.lower() not in {"required", "cert_required", "2"}:
            raise ImproperlyConfigured("Redis TLS certificate verification cannot be disabled.")
