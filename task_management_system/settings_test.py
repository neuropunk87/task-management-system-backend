import os


os.environ.setdefault(
    "DJANGO_SECRET_KEY",
    "test-only-secret-key-not-valid-for-any-real-deployment-123456789",
)
os.environ.setdefault("DJANGO_ENV", "test")

from task_management_system.settings import *  # noqa: F403, E402


if os.environ.get("AUDIT_TEST_DATABASE_URL"):
    import dj_database_url

    DATABASES = {"default": dj_database_url.parse(os.environ["AUDIT_TEST_DATABASE_URL"])}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "task-management-tests",
    }
}
if os.environ.get("AUDIT_TEST_REDIS_URL"):
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": os.environ["AUDIT_TEST_REDIS_URL"],
            "KEY_PREFIX": "tms_isolated_audit",
        }
    }
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
CELERY_TASK_ALWAYS_EAGER = os.environ.get("AUDIT_CELERY_EAGER", "True").lower() == "true"
CELERY_TASK_EAGER_PROPAGATES = True
AXES_ENABLED = False
TRUST_X_FORWARDED_FOR = False
API_DOCS_PUBLIC = False
MEDIA_ROOT = BASE_DIR / ".test-media"  # noqa: F405
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
    },
}
