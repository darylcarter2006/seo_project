"""
app/models/preference.py

study_style: free text for now (e.g. "quiet", "discussion", "flashcards")
pace: 1 (relaxed) - 5 (fast/intensive)
"""

from app.database.db import db


class Preference(db.Model):
    __tablename__ = "preference"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True, nullable=False)
    study_style = db.Column(db.String(50), nullable=False, default="discussion")
    pace = db.Column(db.Integer, nullable=False, default=3)

    def __repr__(self):
        return f"<Preference user={self.user_id} style={self.study_style} pace={self.pace}>"
