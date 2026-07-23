"""
app/__init__.py
Flask application factory.
"""

from flask import Flask
from app.database.db import db
from app.database.migrations import init_db
from config import Config


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)

    # Ensure models are registered on db.metadata before creating tables
    from app.models import User, Course, Availability, Preference, Match  # noqa: F401

    init_db(app)

    # Register blueprints here once routes/*.py define them, e.g.:
    # from app.routes.match_routes import match_bp
    # app.register_blueprint(match_bp)

    return app