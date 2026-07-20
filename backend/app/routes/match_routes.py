"""
app/routes/match_routes.py
----------------------------
Placeholder for now. This is where the matching engine (Person 2) and
the "confirm a match -> book it on Calendar" flow (you, Person B) will
connect.

Left as a minimal stub so `create_app()` has something to register and
the server actually runs on Day 1. Fill in real logic on Day 2/3.
"""

from flask import Blueprint, jsonify

match_bp = Blueprint("match", __name__)


@match_bp.route("/ping")
def ping():
    """Sanity check route: hit /api/match/ping to confirm the blueprint
    is registered and the server is running."""
    return jsonify({"status": "match blueprint alive"})


# TODO (Day 2/3): add a route like POST /api/match/confirm that:
#   1. Takes a matched pair of user_ids + a proposed time slot
#   2. Calls get_valid_access_token() from auth_routes for the requesting user
#   3. If a token exists, calls GoogleCalendarService.create_calendar_event(...)
#   4. If create_calendar_event returns None (API failure), still save the
#      match in the DB but flag it as "pending calendar confirmation"
#      instead of failing the whole request — this is the graceful-
#      degradation story from the rubric notes.
