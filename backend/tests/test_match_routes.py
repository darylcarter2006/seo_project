"""
tests/test_match_routes.py
Exercises POST /api/match/confirm end-to-end. Confirming a match now
requires both users to already exist in the DB (compatibility scoring
goes through app/services/recommendation_engine.py against real
Availability/Course/Preference rows), and a successful confirmation
persists a Match row via app/services/persistence.py.
"""

from unittest.mock import patch

from app.services.persistence import get_or_create_course, get_matches
from tests.conftest import make_user


def _compatible_pair():
    """Two users who share a course, availability, study style, and
    pace -- guaranteed a positive compatibility score."""
    course = get_or_create_course("CS101", "Intro to CS")
    user = make_user("Alice", "alice@example.edu", [(0, 14, 16)], "quiet", 3, course)
    partner = make_user("Bob", "bob@example.edu", [(0, 14, 16)], "quiet", 3, course)
    return user, partner


def _incompatible_pair():
    """No shared course, no overlapping availability, different study
    style, and max pace distance -- every sub-score is zero."""
    user = make_user("Cleo", "cleo@example.edu", [(0, 14, 16)], "quiet", 1)
    partner = make_user("Deja", "deja@example.edu", [(1, 9, 11)], "discussion", 5)
    return user, partner


def _payload(user_id, partner_id, **overrides):
    payload = {
        "user_id": user_id,
        "partner_id": partner_id,
        "start_time": "2026-07-22T14:00:00",
        "end_time": "2026-07-22T15:00:00",
    }
    payload.update(overrides)
    return payload


def _token_for_provider(google_token=None, notion_token=None):
    """get_valid_access_token is called once per provider in the route,
    so a single flat return_value can't tell Google and Notion apart -
    this builds a side_effect that answers based on the provider kwarg."""
    def side_effect(user_id, provider="google_calendar"):
        if provider == "google_calendar":
            return google_token
        if provider == "notion":
            return notion_token
        return None
    return side_effect


# Patched where the names are *used* (match_routes), not where they're
# defined - patching the original module wouldn't affect the reference
# match_routes already imported.
@patch("app.routes.match_routes.GoogleCalendarService.create_calendar_event")
@patch("app.routes.match_routes.get_valid_access_token")
def test_successful_confirmation_books_calendar_and_persists_match(
    mock_get_token, mock_create_event, app
):
    mock_get_token.side_effect = _token_for_provider(google_token="fake-access-token")
    mock_create_event.return_value = {"hangoutLink": "https://meet.google.com/abc-defg-hij"}

    user, partner = _compatible_pair()
    client = app.test_client()
    response = client.post("/api/match/confirm", json=_payload(user.id, partner.id))

    assert response.status_code == 200
    body = response.get_json()
    assert body["calendar_status"] == "booked"
    assert body["meet_link"] == "https://meet.google.com/abc-defg-hij"
    assert body["notion_status"] == "not connected"  # no notion token in this test
    assert body["score"] > 0

    matches = get_matches(user_id=user.id)
    assert len(matches) == 1
    assert matches[0].id == body["match_id"]
    assert matches[0].status == "confirmed"
    assert matches[0].score == body["score"]


@patch("app.routes.match_routes.GoogleCalendarService.create_calendar_event")
@patch("app.routes.match_routes.get_valid_access_token")
def test_calendar_failure_falls_back_gracefully(mock_get_token, mock_create_event, app):
    mock_get_token.side_effect = _token_for_provider(google_token="fake-access-token")
    mock_create_event.return_value = None  # simulates a Calendar API failure

    user, partner = _compatible_pair()
    client = app.test_client()
    response = client.post("/api/match/confirm", json=_payload(user.id, partner.id))

    assert response.status_code == 200  # match is still confirmed
    body = response.get_json()
    assert body["calendar_status"] == "pending calendar confirmation"
    assert "meet_link" not in body


def test_invalid_match_returns_400(app):
    user, partner = _incompatible_pair()
    client = app.test_client()
    response = client.post("/api/match/confirm", json=_payload(user.id, partner.id))

    assert response.status_code == 400
    assert "error" in response.get_json()


def test_unknown_user_returns_404(app):
    course = get_or_create_course("CS101", "Intro to CS")
    user = make_user("Alice", "alice@example.edu", [(0, 14, 16)], "quiet", 3, course)
    client = app.test_client()

    response = client.post("/api/match/confirm", json=_payload(user.id, 999999))

    assert response.status_code == 404


def test_same_user_and_partner_returns_400(app):
    course = get_or_create_course("CS101", "Intro to CS")
    user = make_user("Alice", "alice@example.edu", [(0, 14, 16)], "quiet", 3, course)
    client = app.test_client()

    response = client.post("/api/match/confirm", json=_payload(user.id, user.id))

    assert response.status_code == 400


@patch("app.routes.match_routes.NotionService.create_shared_page")
@patch("app.routes.match_routes.GoogleCalendarService.create_calendar_event")
@patch("app.routes.match_routes.get_valid_access_token")
def test_notion_page_created_when_connected(
    mock_get_token, mock_create_event, mock_create_page, app
):
    mock_get_token.side_effect = _token_for_provider(
        google_token="fake-google-token", notion_token="fake-notion-token"
    )
    mock_create_event.return_value = {"hangoutLink": "https://meet.google.com/abc-defg-hij"}
    mock_create_page.return_value = {"url": "https://notion.so/study-session-abc123"}

    user, partner = _compatible_pair()
    client = app.test_client()
    payload = _payload(
        user.id, partner.id, notion_parent_page_id="some-parent-page-id", topic="Calc II"
    )
    response = client.post("/api/match/confirm", json=payload)

    assert response.status_code == 200
    body = response.get_json()
    assert body["notion_status"] == "created"
    assert body["notes_page_url"] == "https://notion.so/study-session-abc123"
    mock_create_page.assert_called_once()


@patch("app.routes.match_routes.NotionService.create_shared_page")
@patch("app.routes.match_routes.GoogleCalendarService.create_calendar_event")
@patch("app.routes.match_routes.get_valid_access_token")
def test_notion_failure_does_not_block_match_confirmation(
    mock_get_token, mock_create_event, mock_create_page, app
):
    mock_get_token.side_effect = _token_for_provider(
        google_token="fake-google-token", notion_token="fake-notion-token"
    )
    mock_create_event.return_value = {"hangoutLink": "https://meet.google.com/abc-defg-hij"}
    mock_create_page.return_value = None  # simulates a Notion API failure

    user, partner = _compatible_pair()
    client = app.test_client()
    payload = _payload(user.id, partner.id, notion_parent_page_id="some-parent-page-id")
    response = client.post("/api/match/confirm", json=payload)

    assert response.status_code == 200  # match still confirmed
    body = response.get_json()
    assert body["notion_status"] == "pending notion confirmation"
    assert "notes_page_url" not in body
