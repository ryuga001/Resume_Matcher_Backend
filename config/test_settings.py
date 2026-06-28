from config.settings import *  # noqa: F401, F403

# Use in-memory SQLite so CI has no external DB dependency.
# MIGRATE: False tells the test runner to create the DB but skip all migrations
# and table creation — no VectorField SQL is ever sent to SQLite.
# Tests that touch the DB directly will fail with "no such table"; tests that
# don't touch the DB (pure unit tests) pass normally.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
        "TEST": {
            "MIGRATE": False,
        },
    }
}
