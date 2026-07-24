"""
run.py
------
Entry point. Run this file to start the local dev server:

    python run.py

Everything else (routes, config, db) is wired together inside
app/__init__.py's create_app() function, including table creation via
init_db() -- no manual db.create_all() needed here.
"""

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000, host="127.0.0.1")
