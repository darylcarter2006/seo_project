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

from flask import Flask
from flask_sqlalchemy import SQLAlchemy

from app.config import Config

# db is created here but not attached to an app yet (that happens in
# create_app via db.init_app(app)). This "lazy init" pattern is what lets
# Person B (models) import `db` without needing the app to exist yet.
db = SQLAlchemy()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Wire the database to this specific app instance.
    db.init_app(app)

    # --- Register routes ---
    # Each teammate's routes live in their own file under app/routes/.
    # We import them here (not at the top of the file) to avoid circular
    # imports, since those route files import `db` and models from us.
    from app.routes.auth_routes import auth_bp
    from app.routes.match_routes import match_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(match_bp, url_prefix="/api/match")

    return app
