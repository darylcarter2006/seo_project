"""
tests/test_auth_routes.py
Confirms the user_id query param on /api/auth/*/login flows through the
session into the callback, since there's no real login system yet -- this
is a temporary stand-in (see README), not real authentication.
"""

from datetime import datetime, timedelta
from unittest.mock import patch

from app.models.oauth_token import OAuthToken
from app.services.persistence import create_user


@patch("app.routes.auth_routes.GoogleCalendarService.exchange_code_for_tokens")
@patch("app.routes.auth_routes.GoogleCalendarService.get_authorization_url")
def test_google_login_user_id_query_param_flows_to_callback(mock_auth_url, mock_exchange, app):
    create_user("Alice", "alice@example.edu")  # gets the fallback id -- not who we're testing
    partner = create_user("Bob", "bob@example.edu")

    mock_auth_url.return_value = ("http://accounts.google.com/fake", "fake-state")
    mock_exchange.return_value = {
        "access_token": "fake-access-token",
        "refresh_token": "fake-refresh-token",
        "expires_at": datetime.utcnow() + timedelta(hours=1),
    }

    client = app.test_client()
    client.get(f"/api/auth/google/login?user_id={partner.id}")
    response = client.get("/api/auth/google/callback?code=fake-code&state=fake-state")

    assert response.status_code == 200
    token = OAuthToken.query.filter_by(provider="google_calendar").first()
    assert token.user_id == partner.id


@patch("app.routes.auth_routes.NotionService.exchange_code_for_tokens")
def test_notion_login_defaults_to_user_id_1_when_missing(mock_exchange, app):
    create_user("Alice", "alice@example.edu")  # becomes id=1, the fallback target

    mock_exchange.return_value = {"access_token": "fake-notion-token"}

    client = app.test_client()
    client.get("/api/auth/notion/login")  # no user_id query param

    with client.session_transaction() as sess:
        state = sess["notion_oauth_state"]

    response = client.get(f"/api/auth/notion/callback?code=fake-code&state={state}")

    assert response.status_code == 200
    token = OAuthToken.query.filter_by(provider="notion").first()
    assert token.user_id == 1
