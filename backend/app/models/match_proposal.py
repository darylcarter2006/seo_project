"""
app/models/match_proposal.py

Holds the session details (start_time/end_time/topic/notion_parent_page_id)
a proposer submits with a match, until the invited partner accepts and
those details are actually needed to book the Calendar event/Notion page.
Also holds the resulting google_calendar_event_id once booked, so a later
cancellation can delete the actual Calendar event, not just flip a status.
And, once accept-time booking runs, holds its outcome (calendar_status/
meet_link/notion_status/notes_page_url) so a later re-fetch of the match
(e.g. GET /api/match/history) doesn't lose that detail -- previously it
was only ever returned once, in the /respond response itself.
Also tracks per-side dismissal (dismissed_by_user_a/dismissed_by_user_b)
so each participant can independently clear a resolved match from their
own dashboard without affecting the other's view.

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
    google_calendar_event_id = db.Column(db.String(200), nullable=True)
    calendar_status = db.Column(db.String(50), nullable=True)
    meet_link = db.Column(db.String(500), nullable=True)
    notion_status = db.Column(db.String(50), nullable=True)
    notes_page_url = db.Column(db.String(500), nullable=True)
    dismissed_by_user_a = db.Column(db.Boolean, nullable=False, default=False)
    dismissed_by_user_b = db.Column(db.Boolean, nullable=False, default=False)

    match = db.relationship("Match")

    def __repr__(self):
        return f"<MatchProposal match_id={self.match_id}>"
