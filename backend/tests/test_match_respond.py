"""
tests/test_match_respond.py
Exercises POST /api/match/<match_id>/respond and GET /api/match/pending --
the accept/decline half of the two-sided match confirmation flow. Booking
(Calendar/Notion) now only happens here, on accept, not at proposal time
(see test_match_routes.py for that).
"""

from datetime import datetime
from unittest.mock import patch

from app.services.persistence import (
    get_or_create_course,
    save_match,
    save_match_proposal,
    get_match,
)
from tests.conftest import make_user


def _compatible_pair():
    course = get_or_create_course("CS101", "Intro to CS")
    user = make_user("Alice", "alice@example.edu", [(0, 14, 16)], "quiet", 3, course)
    partner = make_user("Bob", "bob@example.edu", [(0, 14, 16)], "quiet", 3, course)
    return user, partner


def _propose(user, partner, score=90.0, topic=None, notion_parent_page_id=None):
    """Creates a pending Match + MatchProposal directly, bypassing the
    /confirm HTTP call -- these tests are about /respond, not proposing."""
    match = save_match(user.id, partner.id, score, status="pending")
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


@patch("app.routes.match_routes.GoogleCalendarService.create_calendar_event")
@patch("app.routes.match_routes.get_valid_access_token")
def test_accepting_books_calendar_with_partner_email_and_confirms(
    mock_get_token, mock_create_event, app
):
    user, partner = _compatible_pair()
    match = _propose(user, partner)

    mock_get_token.side_effect = _token_for_provider(google_token="fake-access-token")
    mock_create_event.return_value = {"hangoutLink": "https://meet.google.com/abc-defg-hij"}

    client = app.test_client()
    response = client.post(
        f"/api/match/{match.id}/respond",
        json={"response": "accept", "responding_user_id": partner.id},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "confirmed"
    assert body["calendar_status"] == "booked"
    assert body["meet_link"] == "https://meet.google.com/abc-defg-hij"

    assert get_match(match.id).status == "confirmed"

    _, kwargs = mock_create_event.call_args
    assert kwargs["attendee_emails"] == [partner.email]


@patch("app.routes.match_routes.GoogleCalendarService.create_calendar_event")
@patch("app.routes.match_routes.get_valid_access_token")
def test_accept_with_no_calendar_connection_still_confirms(mock_get_token, mock_create_event, app):
    user, partner = _compatible_pair()
    match = _propose(user, partner)

    mock_get_token.side_effect = _token_for_provider()  # nothing connected

    client = app.test_client()
    response = client.post(
        f"/api/match/{match.id}/respond",
        json={"response": "accept", "responding_user_id": partner.id},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "confirmed"
    assert body["calendar_status"] == "pending calendar confirmation"
    assert "meet_link" not in body
    assert get_match(match.id).status == "confirmed"
    mock_create_event.assert_not_called()


@patch("app.routes.match_routes.NotionService.create_shared_page")
@patch("app.routes.match_routes.GoogleCalendarService.create_calendar_event")
@patch("app.routes.match_routes.get_valid_access_token")
def test_accepting_creates_notion_page_when_connected(
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
    response = client.post(
        f"/api/match/{match.id}/respond",
        json={"response": "accept", "responding_user_id": partner.id},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["notion_status"] == "created"
    assert body["notes_page_url"] == "https://notion.so/study-session-abc123"
    mock_create_page.assert_called_once()


@patch("app.routes.match_routes.GoogleCalendarService.create_calendar_event")
@patch("app.routes.match_routes.NotionService.create_shared_page")
def test_declining_sets_declined_and_never_calls_calendar_or_notion(
    mock_create_page, mock_create_event, app
):
    user, partner = _compatible_pair()
    match = _propose(user, partner)

    client = app.test_client()
    response = client.post(
        f"/api/match/{match.id}/respond",
        json={"response": "decline", "responding_user_id": partner.id},
    )

    assert response.status_code == 200
    assert response.get_json() == {"status": "declined"}
    assert get_match(match.id).status == "declined"

    mock_create_event.assert_not_called()
    mock_create_page.assert_not_called()


def test_wrong_responding_user_gets_403(app):
    user, partner = _compatible_pair()
    match = _propose(user, partner)

    client = app.test_client()
    response = client.post(
        f"/api/match/{match.id}/respond",
        # the proposer trying to respond to their own invite, not the partner
        json={"response": "accept", "responding_user_id": user.id},
    )

    assert response.status_code == 403
    assert get_match(match.id).status == "pending"


def test_responding_to_unknown_match_returns_404(app):
    client = app.test_client()
    response = client.post(
        "/api/match/999999/respond",
        json={"response": "accept", "responding_user_id": 1},
    )
    assert response.status_code == 404


def test_responding_twice_returns_400(app):
    user, partner = _compatible_pair()
    match = _propose(user, partner)

    client = app.test_client()
    client.post(
        f"/api/match/{match.id}/respond",
        json={"response": "decline", "responding_user_id": partner.id},
    )
    second = client.post(
        f"/api/match/{match.id}/respond",
        json={"response": "accept", "responding_user_id": partner.id},
    )

    assert second.status_code == 400


def test_pending_only_returns_matches_where_user_is_invited_partner(app):
    course = get_or_create_course("CS101", "Intro to CS")
    alice = make_user("Alice", "alice@example.edu", [(0, 14, 16)], "quiet", 3, course)
    bob = make_user("Bob", "bob@example.edu", [(0, 14, 16)], "quiet", 3, course)
    cleo = make_user("Cleo", "cleo@example.edu", [(0, 14, 16)], "quiet", 3, course)

    _propose(alice, bob)   # bob is invited (user_b)
    _propose(cleo, alice)  # alice is invited here (user_b)
    # alice is also the proposer of the first match (user_a) -- it must
    # not show up in her own pending list.

    client = app.test_client()
    response = client.get(f"/api/match/pending?user_id={alice.id}")

    assert response.status_code == 200
    pending = response.get_json()["pending"]
    assert len(pending) == 1
    assert pending[0]["partner_name"] == "Cleo"
    assert pending[0]["match_id"] is not None


def test_pending_missing_user_returns_404(app):
    client = app.test_client()
    response = client.get("/api/match/pending?user_id=999999")
    assert response.status_code == 404
