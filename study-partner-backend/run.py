"""
run.py
------
Entry point. Run this file to start the local dev server:

    python run.py

Everything else (routes, config, db) is wired together inside
app/__init__.py's create_app() function.
"""

from app import create_app, db

app = create_app()

if __name__ == "__main__":
    # Creates the SQLite tables on first run if they don't exist yet.
    # In a real deployment we'd use migrations (Flask-Migrate) instead,
    # but for a class project this is simpler and good enough.
    with app.app_context():
        db.create_all()

    app.run(debug=True, port=5000)
