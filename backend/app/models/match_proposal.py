"""
app/models/match_proposal.py

Holds the session details (start_time/end_time/topic/notion_parent_page_id)
a proposer submits with a match, until the invited partner accepts and
those details are actually needed to book the Calendar event/Notion page.

Deliberately a separate table rather than new columns on Match -- Match's
schema is owned by Manuel and stays untouched; this is purely additive.
"""

from app.database.db import db


class MatchProposal(db.Model):
    __tablename__ = "match_proposal"

    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey("match.id"), unique=True, nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    topic = db.Column(db.String(200), nullable=True)
    notion_parent_page_id = db.Column(db.String(200), nullable=True)

    match = db.relationship("Match")

    def __repr__(self):
        return f"<MatchProposal match_id={self.match_id}>"
