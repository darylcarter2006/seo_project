"""
app/__init__.py
----------------
This is the "app factory." Instead of creating the Flask app as a global
variable at import time, we build it inside a function (create_app).

Why this matters for the team: it means each person's routes/services
don't have to import a shared `app` object directly, they register
themselves onto whatever app instance gets passed in. This avoids a
common beginner bug where circular imports break the whole project.

How to run this app (from the project root):
    pip install -r requirements.txt
    cp .env.example .env      # then fill in real values
    python run.py
"""

from flask import Flask, request

from app.config import Config
from app.database.db import db
from app.database.migrations import init_db


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Wire the database to this specific app instance.
    db.init_app(app)

    # Import every model so it's registered on db.metadata before
    # init_db()'s create_all() runs.
    from app.models import OAuthToken, User, Course, Availability, Preference, Match  # noqa: F401

    init_db(app)

    # --- CORS ---
    # The frontend is static HTML with no build/serve step (opened via
    # file:// or a plain static server), so every fetch() to this API is
    # cross-origin. Dev-permissive only -- no cookies/credentials cross
    # origin, since every request carries an explicit user_id instead of
    # relying on a session, so allowing any origin here doesn't expose
    # anything a same-origin request wouldn't. Not meant for production.
    @app.after_request
    def add_cors_headers(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return response

    @app.before_request
    def handle_preflight():
        if request.method == "OPTIONS":
            return "", 204

    # --- Register routes ---
    # Each teammate's routes live in their own file under app/routes/.
    # We import them here (not at the top of the file) to avoid circular
    # imports, since those route files import `db` and models from us.
    from app.routes.auth_routes import auth_bp
    from app.routes.match_routes import match_bp
    from app.routes.user_routes import user_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(match_bp, url_prefix="/api/match")
    app.register_blueprint(user_bp, url_prefix="/api/users")

    return app
