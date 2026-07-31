"""
tests/test_user_routes.py
POST /api/users -- creates/updates a profile from the shape profile.html
actually submits: name, email, course_code, availability (day name ->
list of [start, end] HH:MM strings).
"""

from datetime import datetime, timedelta

from app.database.db import db
from app.models.availability import Availability
from app.models.preference import Preference
from app.models.oauth_token import OAuthToken
from app.services.persistence import get_user_by_email, create_user


def test_create_profile_persists_user_availability_course_and_preference(app):
    client = app.test_client()
    payload = {
        "name": "Alice",
        "email": "alice@example.edu",
        "course_code": "CS101",
        "availability": {"monday": [["14:00", "16:00"]], "wednesday": [["09:00", "11:00"]]},
        "study_style": "quiet",
        "pace": 4,
    }

    response = client.post("/api/users", json=payload)

    assert response.status_code == 200
    user_id = response.get_json()["user_id"]

    user = get_user_by_email("alice@example.edu")
    assert user.id == user_id
    assert [c.code for c in user.courses] == ["CS101"]

    slots = Availability.query.filter_by(user_id=user_id).all()
    assert len(slots) == 2
    monday = next(s for s in slots if s.day_of_week == 0)
    assert (monday.start_hour, monday.end_hour) == (14, 16)

    pref = Preference.query.filter_by(user_id=user_id).first()
    assert pref.study_style == "quiet"
    assert pref.pace == 4


def test_create_profile_defaults_preference_when_omitted(app):
    client = app.test_client()
    payload = {
        "name": "Bob",
        "email": "bob@example.edu",
        "course_code": "CS101",
        "availability": {},
    }

    response = client.post("/api/users", json=payload)

    assert response.status_code == 200
    user_id = response.get_json()["user_id"]
    pref = Preference.query.filter_by(user_id=user_id).first()
    assert pref.study_style == "discussion"
    assert pref.pace == 3


def test_resubmitting_same_email_updates_instead_of_duplicating(app):
    client = app.test_client()
    first = {
        "name": "Cleo",
        "email": "cleo@example.edu",
        "course_code": "CS101",
        "availability": {"monday": [["14:00", "16:00"]]},
    }
    second = {
        "name": "Cleo Nash",
        "email": "cleo@example.edu",
        "course_code": "MATH210",
        "availability": {"tuesday": [["09:00", "10:00"]]},
    }

    first_id = client.post("/api/users", json=first).get_json()["user_id"]
    second_id = client.post("/api/users", json=second).get_json()["user_id"]

    assert first_id == second_id

    user = get_user_by_email("cleo@example.edu")
    assert user.name == "Cleo Nash"
    assert [c.code for c in user.courses] == ["MATH210"]

    slots = Availability.query.filter_by(user_id=user.id).all()
    assert len(slots) == 1
    assert slots[0].day_of_week == 1  # tuesday -- old monday slot was replaced, not appended


def test_missing_required_field_returns_400(app):
    client = app.test_client()
    response = client.post("/api/users", json={"name": "No Email"})
    assert response.status_code == 400


def test_unknown_weekday_returns_400(app):
    client = app.test_client()
    payload = {
        "name": "Dan",
        "email": "dan@example.edu",
        "course_code": "CS101",
        "availability": {"funday": [["14:00", "16:00"]]},
    }
    response = client.post("/api/users", json=payload)
    assert response.status_code == 400


def test_invalid_time_range_returns_400(app):
    client = app.test_client()
    payload = {
        "name": "Eve",
        "email": "eve@example.edu",
        "course_code": "CS101",
        "availability": {"monday": [["16:00", "14:00"]]},
    }
    response = client.post("/api/users", json=payload)
    assert response.status_code == 400


def test_connections_reports_false_for_both_providers_when_none_connected(app):
    user = create_user("Frank", "frank@example.edu")
    client = app.test_client()

    response = client.get(f"/api/users/{user.id}/connections")

    assert response.status_code == 200
    assert response.get_json() == {"google_calendar": False, "notion": False}


def test_connections_reports_true_for_provider_with_valid_token(app):
    user = create_user("Grace", "grace@example.edu")
    db.session.add(OAuthToken(
        user_id=user.id,
        provider="google_calendar",
        access_token="fake-token",
        refresh_token="fake-refresh",
        expires_at=datetime.utcnow() + timedelta(hours=1),
    ))
    db.session.commit()

    client = app.test_client()
    response = client.get(f"/api/users/{user.id}/connections")

    assert response.status_code == 200
    assert response.get_json() == {"google_calendar": True, "notion": False}


def test_connections_unknown_user_returns_404(app):
    client = app.test_client()
    response = client.get("/api/users/999999/connections")
    assert response.status_code == 404


def test_get_profile_returns_saved_profile(app):
    client = app.test_client()
    payload = {
        "name": "Henry",
        "email": "henry@example.edu",
        "course_code": "CS101",
        "availability": {"monday": [["14:00", "16:00"]], "wednesday": [["09:00", "11:00"]]},
        "study_style": "quiet",
        "pace": 4,
    }
    user_id = client.post("/api/users", json=payload).get_json()["user_id"]

    response = client.get(f"/api/users/{user_id}")

    assert response.status_code == 200
    assert response.get_json() == {
        "name": "Henry",
        "email": "henry@example.edu",
        "course_code": "CS101",
        "availability": {"monday": [["14:00", "16:00"]], "wednesday": [["09:00", "11:00"]]},
        "study_style": "quiet",
        "pace": 4,
    }


def test_get_profile_unknown_user_returns_404(app):
    client = app.test_client()
    response = client.get("/api/users/999999")
    assert response.status_code == 404
