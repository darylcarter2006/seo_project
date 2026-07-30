"""
tests/test_match_routes.py
Exercises POST /api/match/confirm -- now a *proposal*, not an immediate
booking. Confirming a match requires both users to already exist in the DB
(compatibility scoring goes through app/services/recommendation_engine.py
against real Availability/Course/Preference rows), creates a
status="pending" Match, and does NOT call Calendar/Notion until the
invited partner accepts via POST /api/match/<id>/respond -- see
test_match_respond.py for the accept/decline half of this flow.
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


@patch("app.routes.match_routes.NotionService.create_shared_page")
@patch("app.routes.match_routes.GoogleCalendarService.create_calendar_event")
def test_proposing_a_match_creates_pending_match_and_books_nothing(
    mock_create_event, mock_create_page, app
):
    user, partner = _compatible_pair()
    client = app.test_client()
    response = client.post("/api/match/confirm", json=_payload(user.id, partner.id))

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "pending"
    assert body["score"] > 0
    assert "calendar_status" not in body
    assert "notion_status" not in body
    assert "meet_link" not in body
    assert "notes_page_url" not in body

    matches = get_matches(user_id=user.id)
    assert len(matches) == 1
    assert matches[0].id == body["match_id"]
    assert matches[0].status == "pending"
    assert matches[0].score == body["score"]

    mock_create_event.assert_not_called()
    mock_create_page.assert_not_called()


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


def test_missing_start_time_returns_400(app):
    user, partner = _compatible_pair()
    client = app.test_client()
    payload = _payload(user.id, partner.id)
    del payload["start_time"]

    response = client.post("/api/match/confirm", json=payload)

    assert response.status_code == 400


def test_end_time_before_start_time_returns_400(app):
    user, partner = _compatible_pair()
    client = app.test_client()
    payload = _payload(
        user.id, partner.id,
        start_time="2026-07-22T15:00:00", end_time="2026-07-22T14:00:00",
    )

    response = client.post("/api/match/confirm", json=payload)

    assert response.status_code == 400
