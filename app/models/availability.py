"""
app/models/availability.py

One row = one block of free time for a user.
day_of_week: 0=Monday ... 6=Sunday
start_hour / end_hour: 0-23, integer hour granularity (good enough for
matching; could move to datetime ranges later if finer precision is needed)
"""

from app.database.db import db


class Availability(db.Model):
    __tablename__ = "availability"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    day_of_week = db.Column(db.Integer, nullable=False)
    start_hour = db.Column(db.Integer, nullable=False)
    end_hour = db.Column(db.Integer, nullable=False)

    def __repr__(self):
        return f"<Availability user={self.user_id} day={self.day_of_week} {self.start_hour}-{self.end_hour}>"
