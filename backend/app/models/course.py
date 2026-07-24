"""
app/models/course.py
"""

from app.database.db import db

# Join table for many-to-many User <-> Course.
# Lives here (not in user.py) since it's conceptually "which users take
# this course" -- avoids circular-looking imports either way, but this
# keeps course-related structure together.
user_courses = db.Table(
    "user_courses",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
    db.Column("course_id", db.Integer, db.ForeignKey("course.id"), primary_key=True),
)


class Course(db.Model):
    __tablename__ = "course"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)  # e.g. "CS101"

    def __repr__(self):
        return f"<Course {self.code}>"
