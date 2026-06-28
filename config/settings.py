import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
DEBUG = os.getenv("DEBUG")
ALLOWED_HOSTS = ["*"]
APPEND_SLASH = False

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "rest_framework",
    "corsheaders",
    "users",
    "resumes",
    "analysis",
    "courses",
    "embeddings",
    "common",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"

CORS_ALLOWED_ORIGINS = [os.getenv("FRONTEND_URI")]
CORS_ALLOW_CREDENTIALS = True

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": "db.sqlite3",
    }
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
}

# ── Celery ────────────────────────────────────────────────────────────────────
CELERY_BROKER_URL        = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND    = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_TASK_SERIALIZER   = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT    = ["json"]
CELERY_TIMEZONE          = "UTC"
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_SOFT_TIME_LIMIT = 360   # 6 min per subtopic task
CELERY_TASK_TIME_LIMIT      = 420
