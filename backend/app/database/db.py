"""
app/database/db.py
Single shared SQLAlchemy instance. Import this everywhere instead of
creating a new SQLAlchemy() per file, or you'll get separate metadata
registries and confusing "table not found" errors.
"""

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
