"""
tests/conftest.py
Shared fixtures for all test files in this directory. Pytest auto-discovers
this -- no need to import it manually in test_*.py files.
"""

import pytest
from app import create_app
from config import TestConfig
from app.services.persistence import (
    create_user, add_availability, set_preference, enroll_user_in_course,
)


@pytest.fixture
def app():
    app = create_app(config_class=TestConfig)
    with app.app_context():
        yield app


def make_user(name, email, slots, style, pace, course=None):
    """Helper: build a fully-populated user for engine/ranking tests.
    Available to any test file via `from tests.conftest import make_user`,
    or just redefine locally if you prefer not to import across test files."""
    from app.services.persistence import get_user
    user = create_user(name, email)
    for day, start, end in slots:
        add_availability(user.id, day, start, end)
    set_preference(user.id, style, pace)
    if course:
        enroll_user_in_course(user, course)
    return get_user(user.id)
