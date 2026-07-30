"""
app/routes/match_routes.py
----------------------------
Where the matching engine (Person 2) and the "confirm a match -> book it
on Calendar" flow (you, Person B) connect.

Compatibility scoring is powered by app/services/recommendation_engine.py
(database schema + weighted scoring algorithm), not raw request-body data
-- confirming a match requires both users to already exist in the DB with
real Availability/Course/Preference rows.
"""

from datetime import datetime

from flask import Blueprint, request, jsonify

from app.routes.auth_routes import get_valid_access_token
from app.services.google_calendar_service import GoogleCalendarService
from app.services.notion_service import NotionService
from app.services.recommendation_engine import calculate_score, find_best_matches
from app.services.persistence import get_user, save_match, get_all_users, get_matches, email_domain

match_bp = Blueprint("match", __name__)


@match_bp.route("/ping")
def ping():
    """Sanity check route: hit /api/match/ping to confirm the blueprint
    is registered and the server is running."""
    return jsonify({"status": "match blueprint alive"})


@match_bp.route("/candidates")
def candidates():
    """
    GET /api/match/candidates?user_id=1

    Ranked list of the best-scoring other users for this user, powered by
    recommendation_engine.find_best_matches(). Hard-scoped to users whose
    email domain matches the requester's (a "same school" proxy -- see
    README for why) before scoring -- cross-domain users never appear here,
    regardless of how well their course/availability/style/pace overlap.
    Response:
        {"candidates": [{"user": {...}, "score": 82.5, "reasons": [...],
         "overlapping_availability": [{"day": "monday", "start": "14:00",
         "end": "16:00"}, ...]}, ...]}
    """
    user_id = request.args.get("user_id", type=int)
    if user_id is None:
        return jsonify({"error": "user_id query param is required"}), 400

    user = get_user(user_id)
    if user is None:
        return jsonify({"error": "user_id must reference an existing user"}), 404

    same_school = [u for u in get_all_users() if email_domain(u.email) == email_domain(user.email)]
    return jsonify({"candidates": find_best_matches(user, same_school)}), 200


@match_bp.route("/history")
def history():
    """
    GET /api/match/history?user_id=1

    This user's confirmed matches -- who with, and the score at
    confirmation time. Response:
        {"matches": [{"match_id": 5, "partner_name": "Bob", "score": 82.5}, ...]}
    """
    user_id = request.args.get("user_id", type=int)
    if user_id is None:
        return jsonify({"error": "user_id query param is required"}), 400

    user = get_user(user_id)
    if user is None:
        return jsonify({"error": "user_id must reference an existing user"}), 404

    confirmed = get_matches(user_id=user_id, status="confirmed")
    results = []
    for match in confirmed:
        partner = match.user_b if match.user_a_id == user_id else match.user_a
        results.append({
            "match_id": match.id,
            "partner_name": partner.name,
            "score": match.score,
            "created_at": match.created_at.isoformat(),
        })
    return jsonify({"matches": results}), 200


@match_bp.route("/confirm", methods=["POST"])
def confirm_match():
    """
    Confirms a proposed study-pair match between two existing users. If the
    requesting user has a connected Google account, books a Calendar event
    with a Meet link; if they also have a connected Notion account (and a
    parent page to create under), creates a shared study-notes page too.
    Neither integration blocks match confirmation if it's missing or fails.

    Expected JSON body:
        {
          "user_id": 1,
          "partner_id": 2,
          "start_time": "2026-07-22T14:00:00",
          "end_time": "2026-07-22T15:00:00",
          "topic": "Calc II",                       # optional, for Notion page title
          "notion_parent_page_id": "..."              # optional, required for Notion page creation
        }

    Response on success, everything booked (200):
        {"status": "confirmed", "match_id": 5, "score": 82.5,
         "calendar_status": "booked", "meet_link": "...",
         "notion_status": "created", "notes_page_url": "..."}

    Response on success, calendar/notion not booked (200) - the match is
    still saved, it's just flagged so the frontend can prompt the user to
    connect an account or retry later instead of losing the match entirely:
        {"status": "confirmed", "match_id": 5, "score": 82.5,
         "calendar_status": "pending calendar confirmation",
         "notion_status": "not connected"}

    Response on invalid match (400):
        {"error": "students are not compatible (no availability/course overlap)"}
    """
    data = request.get_json() or {}

    user_id = data.get("user_id")
    partner_id = data.get("partner_id")
    start_time_raw = data.get("start_time")
    end_time_raw = data.get("end_time")

    if user_id is None or partner_id is None or not start_time_raw or not end_time_raw:
        return jsonify({"error": "Missing required fields"}), 400

    if user_id == partner_id:
        return jsonify({"error": "user_id and partner_id must be different users"}), 400

    user = get_user(user_id)
    partner = get_user(partner_id)
    if user is None or partner is None:
        return jsonify({"error": "user_id/partner_id must reference existing users"}), 404

    try:
        start_time = datetime.fromisoformat(start_time_raw.replace("Z", "+00:00"))
        end_time = datetime.fromisoformat(end_time_raw.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return jsonify({"error": "Invalid start_time/end_time (expected ISO-8601)"}), 400

    if end_time <= start_time:
        return jsonify({"error": "end_time must be after start_time"}), 400

    # Step 1: don't book anything unless the pair is actually compatible.
    score = calculate_score(user, partner)
    if score <= 0:
        return jsonify({
            "error": "students are not compatible (no availability/course overlap)"
        }), 400

    # Step 2: try to book the Calendar event. create_calendar_event already
    # catches its own exceptions and returns None on failure, so we don't
    # need a try/except here - just check the result.
    access_token = get_valid_access_token(user_id, provider="google_calendar")

    calendar_status = "pending calendar confirmation"
    meet_link = None

    if access_token:
        event = GoogleCalendarService.create_calendar_event(
            access_token,
            summary="Study Session",
            start_time=start_time,
            end_time=end_time,
            attendee_emails=[],  # TODO: populate with real emails once auth exists
        )
        if event:
            calendar_status = "booked"
            meet_link = event.get("hangoutLink")
        # else: create_calendar_event already logged why it failed; we fall
        # through with calendar_status left as "pending calendar confirmation"
    # else: user hasn't connected Google yet - same graceful-degrade path
    # as an API failure, so the match still gets confirmed either way.

    # Step 3: try to create a shared Notion study-notes page. Same
    # graceful-degrade pattern as Calendar above - a missing connection or
    # a failed API call never blocks match confirmation.
    notion_token = get_valid_access_token(user_id, provider="notion")
    notion_parent_page_id = data.get("notion_parent_page_id")

    notion_status = "not connected"
    notes_page_url = None

    if notion_token and notion_parent_page_id:
        page = NotionService.create_shared_page(
            notion_token,
            parent_page_id=notion_parent_page_id,
            topic=data.get("topic", "Study Session"),
            student_a_name=user.name,
            student_b_name=partner.name,
        )
        if page:
            notion_status = "created"
            notes_page_url = page.get("url")
        else:
            notion_status = "pending notion confirmation"
    elif notion_token and not notion_parent_page_id:
        notion_status = "pending notion confirmation"  # connected but no parent page given

    # Step 4: persist the match. Match only stores user_a_id/user_b_id/score/
    # status today -- calendar_status/meet_link/notion_status/notes_page_url
    # are returned in the response but not persisted (known gap, would need
    # new nullable columns on Match to survive a re-fetch).
    match = save_match(user_id, partner_id, score, status="confirmed")

    response = {
        "status": "confirmed",
        "match_id": match.id,
        "score": score,
        "calendar_status": calendar_status,
        "notion_status": notion_status,
    }
    if meet_link:
        response["meet_link"] = meet_link
    if notes_page_url:
        response["notes_page_url"] = notes_page_url
    return jsonify(response), 200
