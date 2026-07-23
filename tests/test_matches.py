"""
tests/test_matches.py
Match-specific persistence behavior: saving, filtering, updating status,
deleting, and matches produced from real scored users.
"""

from app.services.persistence import (
    create_user, save_match, get_matches, get_match, delete_match,
    update_match_status, get_or_create_course,
)
from app.services.recommendation_engine import explain_match
from tests.conftest import make_user


def test_delete_match(app):
    u1 = create_user("Ava", "ava@example.edu")
    u2 = create_user("Ben", "ben@example.edu")
    match = save_match(u1.id, u2.id, score=50.0)
    assert delete_match(match.id) is True
    assert get_match(match.id) is None
    assert delete_match(999) is False  # deleting a nonexistent match returns False, not an error


def test_get_matches_filters_by_user(app):
    u1 = create_user("Ava", "ava@example.edu")
    u2 = create_user("Ben", "ben@example.edu")
    u3 = create_user("Cleo", "cleo@example.edu")
    save_match(u1.id, u2.id, score=80.0)
    save_match(u2.id, u3.id, score=40.0)

    u1_matches = get_matches(user_id=u1.id)
    assert len(u1_matches) == 1

    u2_matches = get_matches(user_id=u2.id)
    assert len(u2_matches) == 2  # appears as both user_a and user_b across matches


def test_get_matches_filters_by_status(app):
    u1 = create_user("Ava", "ava@example.edu")
    u2 = create_user("Ben", "ben@example.edu")
    save_match(u1.id, u2.id, score=80.0, status="confirmed")

    confirmed = get_matches(status="confirmed")
    pending = get_matches(status="pending")
    assert len(confirmed) == 1
    assert len(pending) == 0


def test_update_match_status(app):
    u1 = create_user("Ava", "ava@example.edu")
    u2 = create_user("Ben", "ben@example.edu")
    match = save_match(u1.id, u2.id, score=80.0)
    updated = update_match_status(match.id, "confirmed")
    assert updated.status == "confirmed"


def test_saved_match_score_matches_engine_output(app):
    """Integration check: the score saved to the DB should match what
    the recommendation engine actually calculates for those two users."""
    course = get_or_create_course("CS101", "Intro to CS")
    u1 = make_user("Ava", "ava@example.edu", [(0, 14, 16)], "quiet", 3, course)
    u2 = make_user("Ben", "ben@example.edu", [(0, 14, 16)], "quiet", 3, course)

    result = explain_match(u1, u2)
    match = save_match(u1.id, u2.id, score=result["score"])

    assert get_match(match.id).score == result["score"]
