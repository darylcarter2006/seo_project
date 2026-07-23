"""
app/models/match.py
"""

from datetime import datetime
from app.database.db import db


class Match(db.Model):
    __tablename__ = "match"

    id = db.Column(db.Integer, primary_key=True)
    user_a_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    user_b_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    score = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending")  # pending/confirmed/declined
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user_a = db.relationship("User", foreign_keys=[user_a_id])
    user_b = db.relationship("User", foreign_keys=[user_b_id])

    def to_dict(self):
        return {
            "id": self.id,
            "user_a": self.user_a.name,
            "user_b": self.user_b.name,
            "score": self.score,
            "status": self.status,
        }

    def __repr__(self):
        return f"<Match {self.user_a_id}-{self.user_b_id} score={self.score}>"
