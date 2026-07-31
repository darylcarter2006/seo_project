"""
tests/test_match_cancel.py
Exercises POST /api/match/<match_id>/cancel -- cancelling a confirmed
match, with a best-effort attempt to delete the actual Google Calendar
event via its stored event id (MatchProposal.google_calendar_event_id).
"""

from datetime import datetime
from unittest.mock import patch

from app.services.persistence import (
    get_or_create_course,
    save_match,
    save_match_proposal,
    set_match_proposal_event_id,
    get_match,
)
from tests.conftest import make_user


def _confirmed_pair(event_id=None):
    course = get_or_create_course("CS101", "Intro to CS")
    user = make_user("Alice", "alice@example.edu", [(0, 14, 16)], "quiet", 3, course)
    partner = make_user("Bob", "bob@example.edu", [(0, 14, 16)], "quiet", 3, course)

    match = save_match(user.id, partner.id, score=90.0, status="confirmed")
    save_match_proposal(
        match.id,
        start_time=datetime(2026, 7, 22, 14, 0, 0),
        end_time=datetime(2026, 7, 22, 15, 0, 0),
    )
    if event_id:
        set_match_proposal_event_id(match.id, event_id)

    return match, user, partner


@patch("app.routes.match_routes.GoogleCalendarService.delete_calendar_event")
@patch("app.routes.match_routes.get_valid_access_token")
def test_either_participant_can_cancel_and_calendar_event_is_deleted(
    mock_get_token, mock_delete_event, app
):
    match, user, partner = _confirmed_pair(event_id="fake-google-event-id")
    mock_get_token.return_value = "fake-access-token"
    mock_delete_event.return_value = True

    client = app.test_client()
    response = client.post(f"/api/match/{match.id}/cancel", json={"user_id": partner.id})

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "cancelled"
    assert body["calendar_event_deleted"] is True
    assert get_match(match.id).status == "cancelled"

    mock_delete_event.assert_called_once_with("fake-access-token", "fake-google-event-id")


@patch("app.routes.match_routes.GoogleCalendarService.delete_calendar_event")
@patch("app.routes.match_routes.get_valid_access_token")
def test_cancel_still_succeeds_with_no_stored_event_id(mock_get_token, mock_delete_event, app):
    match, user, partner = _confirmed_pair()  # no event id ever stored
    mock_get_token.return_value = "fake-access-token"

    client = app.test_client()
    response = client.post(f"/api/match/{match.id}/cancel", json={"user_id": user.id})

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "cancelled"
    assert body["calendar_event_deleted"] is False
    assert get_match(match.id).status == "cancelled"
    mock_delete_event.assert_not_called()


@patch("app.routes.match_routes.GoogleCalendarService.delete_calendar_event")
@patch("app.routes.match_routes.get_valid_access_token")
def test_cancel_succeeds_even_if_calendar_delete_fails(mock_get_token, mock_delete_event, app):
    match, user, partner = _confirmed_pair(event_id="fake-google-event-id")
    mock_get_token.return_value = "fake-access-token"
    mock_delete_event.return_value = None  # simulates a delete failure

    client = app.test_client()
    response = client.post(f"/api/match/{match.id}/cancel", json={"user_id": user.id})

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "cancelled"
    assert body["calendar_event_deleted"] is False
    assert get_match(match.id).status == "cancelled"


def test_cancel_by_non_participant_returns_403(app):
    match, user, partner = _confirmed_pair()
    other = make_user("Cleo", "cleo@example.edu", [(0, 14, 16)], "quiet", 3)

    client = app.test_client()
    response = client.post(f"/api/match/{match.id}/cancel", json={"user_id": other.id})

    assert response.status_code == 403
    assert get_match(match.id).status == "confirmed"


def test_cancel_unknown_match_returns_404(app):
    client = app.test_client()
    response = client.post("/api/match/999999/cancel", json={"user_id": 1})
    assert response.status_code == 404


def test_cancel_non_confirmed_match_returns_400(app):
    course = get_or_create_course("CS101", "Intro to CS")
    user = make_user("Alice", "alice@example.edu", [(0, 14, 16)], "quiet", 3, course)
    partner = make_user("Bob", "bob@example.edu", [(0, 14, 16)], "quiet", 3, course)
    match = save_match(user.id, partner.id, score=90.0, status="pending")

    client = app.test_client()
    response = client.post(f"/api/match/{match.id}/cancel", json={"user_id": user.id})

    assert response.status_code == 400
    assert get_match(match.id).status == "pending"


@patch("app.routes.match_routes.GoogleCalendarService.delete_calendar_event")
@patch("app.routes.match_routes.get_valid_access_token")
def test_cancelled_match_is_visible_to_both_participants_until_each_dismisses(
    mock_get_token, mock_delete_event, app
):
    match, user, partner = _confirmed_pair()
    mock_get_token.return_value = None  # no calendar connection needed for this

    client = app.test_client()
    cancel = client.post(f"/api/match/{match.id}/cancel", json={"user_id": user.id})
    assert cancel.status_code == 200

    user_history = client.get(f"/api/match/history?user_id={user.id}").get_json()["matches"]
    partner_history = client.get(f"/api/match/history?user_id={partner.id}").get_json()["matches"]
    assert len(user_history) == 1 and user_history[0]["status"] == "cancelled"
    assert len(partner_history) == 1 and partner_history[0]["status"] == "cancelled"

    # user dismisses their own view -- partner's view is untouched
    dismiss = client.post(f"/api/match/{match.id}/dismiss", json={"user_id": user.id})
    assert dismiss.status_code == 200

    assert client.get(f"/api/match/history?user_id={user.id}").get_json()["matches"] == []
    partner_history_after = client.get(f"/api/match/history?user_id={partner.id}").get_json()["matches"]
    assert len(partner_history_after) == 1

    # partner independently dismisses their own view
    client.post(f"/api/match/{match.id}/dismiss", json={"user_id": partner.id})
    assert client.get(f"/api/match/history?user_id={partner.id}").get_json()["matches"] == []


def test_cancel_already_cancelled_match_returns_400(app):
    match, user, partner = _confirmed_pair()
    client = app.test_client()

    with patch("app.routes.match_routes.get_valid_access_token", return_value=None):
        first = client.post(f"/api/match/{match.id}/cancel", json={"user_id": user.id})
        assert first.status_code == 200

        second = client.post(f"/api/match/{match.id}/cancel", json={"user_id": partner.id})
        assert second.status_code == 400
