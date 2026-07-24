"""
tests/test_database.py
Priority 1 verification: create/save/query a user, create/retrieve a match.
"""

from app.services.persistence import create_user, get_user
from app.services.persistence import save_match, get_match


def test_create_and_save_user(app):
    user = create_user("Ava Chen", "ava@example.edu")
    assert user.id is not None
    assert user.name == "Ava Chen"


def test_query_user(app):
    created = create_user("Ben Ortiz", "ben@example.edu")
    fetched = get_user(created.id)
    assert fetched is not None
    assert fetched.email == "ben@example.edu"


def test_query_nonexistent_user_returns_none(app):
    assert get_user(999) is None


def test_create_and_retrieve_match(app):
    u1 = create_user("Ava", "ava@example.edu")
    u2 = create_user("Ben", "ben@example.edu")
    match = save_match(u1.id, u2.id, score=75.0)
    fetched = get_match(match.id)
    assert fetched is not None
    assert fetched.score == 75.0
    assert fetched.status == "pending"
