"""
app/routes/auth_routes.py
---------------------------
HTTP routes for the OAuth flow. These should stay THIN — all the actual
OAuth logic lives in GoogleCalendarService. Routes just:
  1. call the service
  2. save/read from the DB
  3. return a response

Endpoints:
    GET  /api/auth/google/login     -> redirects user to Google consent screen
    GET  /api/auth/google/callback  -> Google redirects here after consent
"""

from flask import Blueprint, redirect, request, session, jsonify

from app import db
from app.services.google_calendar_service import GoogleCalendarService
from app.models.oauth_token import OAuthToken

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/google/login")
def google_login():
    """
    Step 1 of OAuth: send the user to Google's consent screen.

    TODO:
    1. Call GoogleCalendarService.get_authorization_url() to get
       (auth_url, state).
    2. Store `state` in the Flask session (session["oauth_state"] = state).
       We'll check this in the callback to make sure the request wasn't
       forged by someone else.
    3. Return redirect(auth_url).
    """
    pass


@auth_bp.route("/google/callback")
def google_callback():
    """
    Step 2 of OAuth: Google redirects the browser back here after the user
    approves (or denies) access. The URL will look like:
        /api/auth/google/callback?state=...&code=...

    TODO:
    1. Get `code` from request.args.get("code"). If it's missing, the user
       probably denied access — handle that gracefully (redirect to some
       "connection failed" page/response instead of crashing).
    2. (Optional but good practice) verify request.args.get("state")
       matches session.get("oauth_state") to prevent CSRF.
    3. Call GoogleCalendarService.exchange_code_for_tokens(code) to get
       the token dict.
    4. Figure out which user this belongs to. For now, since we may not
       have full auth/login built yet, you can hardcode a test user_id
       (e.g. user_id = 1) — just leave a clear TODO to replace this once
       Person B's user model/session login exists.
    5. Save the tokens: create an OAuthToken row (or update the existing
       one if this user already has a google_calendar token) and
       db.session.commit().
    6. Return something simple confirming success, e.g.
       jsonify({"status": "connected"}).
    """
    pass


def get_valid_access_token(user_id, provider="google_calendar"):
    """
    Helper used by OTHER routes (like match confirmation) whenever they
    need a guaranteed-valid access token for a user.

    This is where the "design for failure" / token refresh logic lives.

    TODO:
    1. Look up the OAuthToken row for (user_id, provider).
       If none exists, return None (user hasn't connected yet).
    2. Check token.is_expired().
       - If NOT expired, just return token.access_token.
       - If expired, call GoogleCalendarService.refresh_access_token(
         token.refresh_token).
         - If that succeeds, update the row's access_token and expires_at
           in the DB, commit, and return the new access_token.
         - If it returns None (refresh failed), return None so the caller
           knows the user needs to reconnect their account.

    Returns:
        str (a valid access token) or None
    """
    pass
