"""
app/database/migrations.py

Lightweight table setup -- this is NOT Alembic/Flask-Migrate, just a
create_all() wrapper. Fine for a class project where the schema won't
need versioned migrations. If that changes, swap this out for
Flask-Migrate without touching any calling code, since init_db(app) is
the only function anything else calls.
"""

from app.database.db import db
# Import models so they're registered on db.metadata before create_all()
from app.models import User, Course, Availability, Preference, Match  # noqa: F401


def init_db(app):
    """Creates all tables inside the given app's context. Idempotent --
    safe to call every time the app starts."""
    with app.app_context():
        db.create_all()


def reset_db(app):
    """Drops and recreates all tables. Use for seeding/demo resets only --
    never call this against real data."""
    with app.app_context():
        db.drop_all()
        db.create_all()
