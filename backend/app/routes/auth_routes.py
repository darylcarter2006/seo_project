from flask import Blueprint, redirect, request, session, jsonify

from app import db
from app.services.google_calendar_service import GoogleCalendarService
from app.models.oauth_token import OAuthToken

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/google/login")
def google_login():
    auth_url, state = GoogleCalendarService.get_authorization_url()
    session["oauth_state"] = state
    return redirect(auth_url)


@auth_bp.route("/google/callback")
def google_callback():
    code = request.args.get("code")
    if not code:
        return jsonify({"error": "Google did not return a code"}), 400

    if request.args.get("state") != session.get("oauth_state"):
        return jsonify({"error": "Invalid state parameter"}), 400

    tokens = GoogleCalendarService.exchange_code_for_tokens(code)

    user_id = 1  # TODO: replace with real logged-in user once auth exists

    token = OAuthToken.query.filter_by(user_id=user_id, provider="google_calendar").first()

    if token:
        token.access_token = tokens["access_token"]
        token.refresh_token = tokens["refresh_token"]
        token.expires_at = tokens["expires_at"]
    else:
        token = OAuthToken(
            user_id=user_id,
            provider="google_calendar",
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            expires_at=tokens["expires_at"],
        )
        db.session.add(token)

    db.session.commit()

    return jsonify({"status": "connected"})


def get_valid_access_token(user_id, provider="google_calendar"):
    token = OAuthToken.query.filter_by(user_id=user_id, provider=provider).first()
    if not token:
        return None

    if not token.is_expired():
        return token.access_token

    refreshed = GoogleCalendarService.refresh_access_token(token.refresh_token)
    if refreshed is None:
        return None

    token.access_token = refreshed["access_token"]
    token.expires_at = refreshed["expires_at"]
    db.session.commit()

    return token.access_token