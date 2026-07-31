"""
tests/test_match_history_booking_details.py
Exercises that the Calendar/Notion booking outcome from accepting a match
(POST /api/match/<id>/respond) is persisted on MatchProposal and survives
a later re-fetch via GET /api/match/history -- previously it only ever
existed in the one-time /respond response body.
"""

from datetime import datetime
from unittest.mock import patch

from app.services.persistence import (
    get_or_create_course,
    save_match,
    save_match_proposal,
)
from tests.conftest import make_user


def _compatible_pair():
    course = get_or_create_course("CS101", "Intro to CS")
    user = make_user("Alice", "alice@example.edu", [(0, 14, 16)], "quiet", 3, course)
    partner = make_user("Bob", "bob@example.edu", [(0, 14, 16)], "quiet", 3, course)
    return user, partner


def _propose(user, partner, topic=None, notion_parent_page_id=None):
    match = save_match(user.id, partner.id, 90.0, status="pending")
    save_match_proposal(
        match.id,
        start_time=datetime(2026, 7, 22, 14, 0, 0),
        end_time=datetime(2026, 7, 22, 15, 0, 0),
        topic=topic,
        notion_parent_page_id=notion_parent_page_id,
    )
    return match


def _token_for_provider(google_token=None, notion_token=None):
    def side_effect(user_id, provider="google_calendar"):
        if provider == "google_calendar":
            return google_token
        if provider == "notion":
            return notion_token
        return None
    return side_effect


@patch("app.routes.match_routes.NotionService.create_shared_page")
@patch("app.routes.match_routes.GoogleCalendarService.create_calendar_event")
@patch("app.routes.match_routes.get_valid_access_token")
def test_history_includes_booking_details_after_full_acceptance(
    mock_get_token, mock_create_event, mock_create_page, app
):
    user, partner = _compatible_pair()
    match = _propose(user, partner, topic="Calc II", notion_parent_page_id="some-parent-page-id")

    mock_get_token.side_effect = _token_for_provider(
        google_token="fake-google-token", notion_token="fake-notion-token"
    )
    mock_create_event.return_value = {"hangoutLink": "https://meet.google.com/abc-defg-hij"}
    mock_create_page.return_value = {"url": "https://notion.so/study-session-abc123"}

    client = app.test_client()
    respond = client.post(
        f"/api/match/{match.id}/respond",
        json={"response": "accept", "responding_user_id": partner.id},
    )
    assert respond.status_code == 200

    for viewer_id in (user.id, partner.id):
        history = client.get(f"/api/match/history?user_id={viewer_id}")
        assert history.status_code == 200
        entry = history.get_json()["matches"][0]
        assert entry["calendar_status"] == "booked"
        assert entry["meet_link"] == "https://meet.google.com/abc-defg-hij"
        assert entry["notion_status"] == "created"
        assert entry["notes_page_url"] == "https://notion.so/study-session-abc123"


@patch("app.routes.match_routes.GoogleCalendarService.create_calendar_event")
@patch("app.routes.match_routes.get_valid_access_token")
def test_history_persists_partial_booking_result_accurately(
    mock_get_token, mock_create_event, app
):
    """Calendar connected and booked, but Notion never connected -- the
    partial result must be persisted and returned as-is, not dropped or
    silently upgraded/downgraded."""
    user, partner = _compatible_pair()
    match = _propose(user, partner)

    mock_get_token.side_effect = _token_for_provider(google_token="fake-google-token")
    mock_create_event.return_value = {"hangoutLink": "https://meet.google.com/abc-defg-hij"}

    client = app.test_client()
    respond = client.post(
        f"/api/match/{match.id}/respond",
        json={"response": "accept", "responding_user_id": partner.id},
    )
    assert respond.status_code == 200

    history = client.get(f"/api/match/history?user_id={user.id}")
    entry = history.get_json()["matches"][0]
    assert entry["calendar_status"] == "booked"
    assert entry["meet_link"] == "https://meet.google.com/abc-defg-hij"
    assert entry["notion_status"] == "not connected"
    assert entry["notes_page_url"] is None


def test_history_does_not_include_still_pending_matches(app):
    user, partner = _compatible_pair()
    _propose(user, partner)

    client = app.test_client()
    history = client.get(f"/api/match/history?user_id={user.id}")

    assert history.status_code == 200
    assert history.get_json()["matches"] == []
