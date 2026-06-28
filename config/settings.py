import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
ALLOWED_HOSTS = ["*"]
APPEND_SLASH = False
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "rest_framework",
    "corsheaders",
    "pgvector.django",
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

CORS_ALLOWED_ORIGINS = [os.getenv("FRONTEND_URI", "http://localhost:3000")]
CORS_ALLOW_CREDENTIALS = True

# ── PostgreSQL ────────────────────────────────────────────────────────────────
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME":     os.getenv("POSTGRES_DB",       "sahara"),
        "USER":     os.getenv("POSTGRES_USER",     "postgres"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "postgres"),
        "HOST":     os.getenv("POSTGRES_HOST",     "localhost"),
        "PORT":     os.getenv("POSTGRES_PORT",     "5432"),
    }
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
}

# ── RabbitMQ ──────────────────────────────────────────────────────────────────
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
