"""
config.py
---------
Central place for all app settings. Everything here is pulled from
environment variables (see .env.example) so nobody hardcodes secrets
into the codebase.

Why this file exists: instead of scattering `os.environ.get(...)` calls
across routes and services, we read them all once here. If a teammate
needs to know "what env vars does this app need?", this file is the
single source of truth.
"""

import os
from dotenv import load_dotenv

# Loads variables from a local .env file into os.environ.
# In production (e.g. Render/Vercel) these would be set directly in the
# hosting platform's dashboard instead of a .env file.
load_dotenv()


class Config:
    # Flask needs this to sign session cookies. Without it, Flask sessions
    # (which we use to temporarily hold OAuth state) won't work securely.
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "dev-only-insecure-key")

    # --- Google OAuth (Calendar API) ---
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
    GOOGLE_REDIRECT_URI = os.environ.get(
        "GOOGLE_REDIRECT_URI", "http://localhost:5000/api/auth/google/callback"
    )

    # Scopes = what permissions we're asking the user for.
    # calendar.events lets us create/read events but NOT delete their whole calendar.
    # Always ask for the minimum scope you actually need.
    GOOGLE_SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

    # --- Database ---
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///study_partner.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False  # silences an unnecessary warning
