"""
config.py
Flask configuration. Swap SQLALCHEMY_DATABASE_URI for Postgres/MySQL
later without touching any other file -- everything else reads config
through the app, not a hardcoded connection string.
"""

import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///study_matcher.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class TestConfig(Config):
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    TESTING = True
