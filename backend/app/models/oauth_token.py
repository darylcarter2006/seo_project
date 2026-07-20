"""
app/models/oauth_token.py
--------------------------
Stores OAuth tokens per user, per provider (Google Calendar, etc).

Why a separate table instead of columns on the User model:
a user might eventually connect multiple services (Calendar, Classroom),
each with its own token. One row per (user, provider) keeps this clean
and lets you add a new provider later without changing the schema.
"""

from app import db
from datetime import datetime


class OAuthToken(db.Model):
    __tablename__ = "oauth_tokens"

    id = db.Column(db.Integer, primary_key=True)

    # TODO: add a foreign key to your User model once Person B (DB owner)
    # has it ready, e.g.:
    # user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    user_id = db.Column(db.Integer, nullable=False)

    # Which service this token is for: "google_calendar", "google_classroom", etc.
    # Lets one user have multiple tokens without multiple tables.
    provider = db.Column(db.String(50), nullable=False)

    # The short-lived token used to actually make API calls.
    # NOTE: access tokens expire (usually ~1 hour for Google). That's what
    # refresh_token is for below.
    access_token = db.Column(db.String(512), nullable=False)

    # The long-lived token used to get a new access_token once it expires.
    # Google only sends this on the FIRST authorization — if you don't
    # store it then, you'll have to force the user to re-consent later.
    refresh_token = db.Column(db.String(512), nullable=True)

    # When the current access_token expires. Compare against this before
    # making an API call so you know whether to refresh first.
    expires_at = db.Column(db.DateTime, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def is_expired(self):
        """
        TODO: return True if self.expires_at is in the past, else False.
        Hint: compare against datetime.utcnow().
        """
        pass

    def __repr__(self):
        return f"<OAuthToken user_id={self.user_id} provider={self.provider}>"
