"""
app/models/user.py
"""

from datetime import datetime
from app.database.db import db


class User(db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    courses = db.relationship("Course", secondary="user_courses", backref="students")
    availability_slots = db.relationship(
        "Availability", backref="user", cascade="all, delete-orphan"
    )
    preference = db.relationship(
        "Preference", backref="user", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<User {self.id} {self.name}>"

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "courses": [c.name for c in self.courses],
        }
