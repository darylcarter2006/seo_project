"""
app/database/seed.py
Populates the database with demo users so the app is presentation-ready
without manually clicking through the profile form repeatedly.

Run with: python -m app.database.seed

Safely re-runnable: each user is looked up by email and updated in place
(name, availability, courses, preference all replaced with the values
below) rather than duplicated, and this does NOT wipe the database first
(unlike reset_db()) -- anything else in the DB (OAuth tokens, matches you
confirmed by hand while testing) is left alone.

All ten users share the @example.edu domain so they're mutually visible to
each other under the "same school" email-domain scoping in
GET /api/match/candidates (see backend/README.md). Courses/availability/
style/pace are deliberately varied in clusters so querying candidates for
any one of them returns a realistic mix of high, medium, and low scores --
not a uniform wall of 100%s or 0%s.
"""

from app import create_app
from app.database.db import db
from app.database.migrations import init_db
from app.services.persistence import (
    get_user_by_email,
    create_user,
    clear_availability,
    add_availability,
    set_preference,
    get_or_create_course,
)

# name, email, [(day, start, end)], study_style, pace, [course_codes]
#
# Clusters (by design, so scoring produces a spread):
#   Ava/Ben/Evan   - CS101, overlapping Mon/Wed afternoons, "quiet" -> high scores with each other
#   Cleo           - CS101 + MATH210, Tuesday morning, "discussion" -> bridges two clusters at medium
#   Deja           - MATH210 only, Monday evening, "flashcards", pace 5 -> mostly low scores (isolated)
#   Farah/Grace    - BIO150, identical Tuesday slot, "discussion" -> high scores with each other
#   Henry/Iris     - PSYCH101 (+Iris also ENG205), overlapping Thursday, different style/pace -> medium
#   Jay            - ENG205 only, Friday morning, "flashcards", pace 1 -> mostly low scores (isolated)
SAMPLE_USERS = [
    ("Ava Chen", "ava@example.edu", [(0, 14, 16), (2, 14, 16)], "quiet", 3, ["CS101"]),
    ("Ben Ortiz", "ben@example.edu", [(0, 14, 17), (2, 15, 17)], "quiet", 4, ["CS101"]),
    ("Evan Kim", "evan@example.edu", [(0, 14, 15), (2, 14, 15)], "quiet", 3, ["CS101"]),
    ("Cleo Nash", "cleo@example.edu", [(1, 9, 11)], "discussion", 2, ["CS101", "MATH210"]),
    ("Deja Wright", "deja@example.edu", [(0, 18, 20)], "flashcards", 5, ["MATH210"]),
    ("Farah Ali", "farah@example.edu", [(1, 10, 12)], "discussion", 3, ["BIO150"]),
    ("Grace Liu", "grace@example.edu", [(1, 10, 12)], "discussion", 3, ["BIO150"]),
    ("Henry Park", "henry@example.edu", [(3, 13, 15)], "quiet", 2, ["PSYCH101"]),
    ("Iris Novak", "iris@example.edu", [(3, 13, 16)], "discussion", 4, ["PSYCH101", "ENG205"]),
    ("Jay Thomas", "jay@example.edu", [(4, 10, 12)], "flashcards", 1, ["ENG205"]),
]

COURSES = {
    "CS101": "Intro to Computer Science",
    "MATH210": "Linear Algebra",
    "BIO150": "Intro to Biology",
    "PSYCH101": "Intro to Psychology",
    "ENG205": "British Literature",
}


def _upsert_user(name, email, slots, style, pace, course_codes, course_objs):
    user = get_user_by_email(email)
    if user is None:
        user = create_user(name, email)
    elif user.name != name:
        user.name = name
        db.session.commit()

    clear_availability(user.id)
    for day, start, end in slots:
        add_availability(user.id, day, start, end)

    set_preference(user.id, style, pace)

    courses = [course_objs[code] for code in course_codes]
    if list(user.courses) != courses:
        user.courses = courses
        db.session.commit()

    return user


def run():
    app = create_app()
    init_db(app)  # idempotent create_all() -- does NOT wipe existing data

    with app.app_context():
        course_objs = {
            code: get_or_create_course(code, name) for code, name in COURSES.items()
        }

        for name, email, slots, style, pace, course_codes in SAMPLE_USERS:
            _upsert_user(name, email, slots, style, pace, course_codes, course_objs)

        print(f"Seeded/updated {len(SAMPLE_USERS)} users and {len(COURSES)} courses.")


if __name__ == "__main__":
    run()
