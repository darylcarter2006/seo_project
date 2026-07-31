"""
tests/test_seed.py
Sanity checks on app/database/seed.py's demo data and its re-run
(upsert-by-email) behavior, exercised against the in-memory TestConfig db
via the `app` fixture rather than seed.run() itself (which always calls
create_app() against the real Config/DATABASE_URL, not a test db).
"""

from app.database.seed import SAMPLE_USERS, COURSES, _upsert_user
from app.services.persistence import get_or_create_course, get_all_users, email_domain
from app.models.availability import Availability


def _seed_all():
    course_objs = {code: get_or_create_course(code, name) for code, name in COURSES.items()}
    for name, email, slots, style, pace, course_codes in SAMPLE_USERS:
        _upsert_user(name, email, slots, style, pace, course_codes, course_objs)
    return course_objs


def test_sample_users_all_share_example_edu_domain():
    assert len(SAMPLE_USERS) >= 9
    for _, email, *_ in SAMPLE_USERS:
        assert email_domain(email) == "example.edu"


def test_seeding_creates_all_users(app):
    _seed_all()
    assert len(get_all_users()) == len(SAMPLE_USERS)


def test_reseeding_updates_instead_of_duplicating(app):
    _seed_all()
    _seed_all()  # run twice, same as re-running the script

    assert len(get_all_users()) == len(SAMPLE_USERS)


def test_reseeding_replaces_availability_instead_of_appending(app):
    course_objs = _seed_all()
    ava_before = next(u for u in get_all_users() if u.email == "ava@example.edu")
    slots_before = Availability.query.filter_by(user_id=ava_before.id).count()

    # Re-seed with the same fixed data -- availability row count should be
    # identical, not doubled.
    for name, email, slots, style, pace, course_codes in SAMPLE_USERS:
        _upsert_user(name, email, slots, style, pace, course_codes, course_objs)

    slots_after = Availability.query.filter_by(user_id=ava_before.id).count()
    assert slots_after == slots_before
