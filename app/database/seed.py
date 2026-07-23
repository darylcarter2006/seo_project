"""
app/database/seed.py
Populates the database with sample users so the demo works without
manual signup. Run with: python -m app.database.seed
"""

from app import create_app
from app.database.migrations import reset_db
from app.services.persistence import (
    create_user,
    add_availability,
    set_preference,
    get_or_create_course,
    enroll_user_in_course,
)

SAMPLE_USERS = [
    # name, email, [(day, start, end)], study_style, pace, [course_codes]
    ("Ava Chen", "ava@example.edu", [(0, 14, 16), (2, 14, 16)], "quiet", 3, ["CS101"]),
    ("Ben Ortiz", "ben@example.edu", [(0, 14, 17), (2, 15, 17)], "quiet", 4, ["CS101"]),
    ("Cleo Nash", "cleo@example.edu", [(1, 9, 11)], "discussion", 2, ["CS101", "MATH210"]),
    ("Deja Wright", "deja@example.edu", [(0, 18, 20)], "flashcards", 5, ["MATH210"]),
    ("Evan Kim", "evan@example.edu", [(0, 14, 15), (2, 14, 15)], "quiet", 3, ["CS101"]),
]

COURSES = {
    "CS101": "Intro to Computer Science",
    "MATH210": "Linear Algebra",
}


def run():
    app = create_app()
    reset_db(app)

    with app.app_context():
        course_objs = {
            code: get_or_create_course(code, name) for code, name in COURSES.items()
        }

        for name, email, slots, style, pace, course_codes in SAMPLE_USERS:
            user = create_user(name, email)
            for day, start, end in slots:
                add_availability(user.id, day, start, end)
            set_preference(user.id, style, pace)
            for code in course_codes:
                enroll_user_in_course(user, course_objs[code])

        print(f"Seeded {len(SAMPLE_USERS)} users and {len(COURSES)} courses.")


if __name__ == "__main__":
    run()
