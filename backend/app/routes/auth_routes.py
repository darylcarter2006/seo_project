from datetime import datetime
import secrets

from flask import Blueprint, redirect, request, session, jsonify

from app.database.db import db
from app.services.google_calendar_service import GoogleCalendarService
from app.services.notion_service import NotionService
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

    try:
        tokens = GoogleCalendarService.exchange_code_for_tokens(code)
    except Exception:
        return jsonify({"error": "Google token exchange failed"}), 502

    user_id = 1  # TODO: replace with real logged-in user once auth exists

    token = OAuthToken.query.filter_by(user_id=user_id, provider="google_calendar").first()

    if token:
        token.access_token = tokens["access_token"]
        if tokens.get("refresh_token"):
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


@auth_bp.route("/notion/login")
def notion_login():
    state = secrets.token_urlsafe(32)
    session["notion_oauth_state"] = state
    auth_url = NotionService.get_authorization_url(state)
    return redirect(auth_url)


@auth_bp.route("/notion/callback")
def notion_callback():
    if request.args.get("state") != session.get("notion_oauth_state"):
        return jsonify({"error": "Invalid state parameter"}), 400

    code = request.args.get("code")
    if not code:
        return jsonify({"error": "Notion did not return a code"}), 400

    try:
        tokens = NotionService.exchange_code_for_tokens(code)
    except Exception:
        return jsonify({"error": "Notion token exchange failed"}), 502

    user_id = 1  # TODO: replace with real logged-in user once auth exists

    # Notion access tokens don't expire, so refresh_token/expires_at stay
    # None/far-future here - is_expired() on the model will just always
    # report "not expired" for this provider since there's nothing to expire.
    token = OAuthToken.query.filter_by(user_id=user_id, provider="notion").first()

    if token:
        token.access_token = tokens["access_token"]
    else:
        token = OAuthToken(
            user_id=user_id,
            provider="notion",
            access_token=tokens["access_token"],
            refresh_token=None,
            expires_at=datetime.max,
        )
        db.session.add(token)

    db.session.commit()

    return jsonify({"status": "connected"})