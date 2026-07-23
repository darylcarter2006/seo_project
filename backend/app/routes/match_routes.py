"""
app/routes/match_routes.py
----------------------------
Where the matching engine (Person 2) and the "confirm a match -> book it
on Calendar" flow (you, Person B) connect.
"""

from datetime import datetime

from flask import Blueprint, request, jsonify

from app.routes.auth_routes import get_valid_access_token
from app.services.google_calendar_service import GoogleCalendarService
from app.services.notion_service import NotionService
from app.services.matching_service import calculate_compatibility_score

match_bp = Blueprint("match", __name__)


@match_bp.route("/ping")
def ping():
    """Sanity check route: hit /api/match/ping to confirm the blueprint
    is registered and the server is running."""
    return jsonify({"status": "match blueprint alive"})


@match_bp.route("/confirm", methods=["POST"])
def confirm_match():
    """
    Confirms a proposed study-pair match. If the requesting user has a
    connected Google account, books a Calendar event with a Meet link;
    if they also have a connected Notion account (and a parent page to
    create under), creates a shared study-notes page too. Neither
    integration blocks match confirmation if it's missing or fails.

    Expected JSON body:
        {
          "user_id": 1,
          "partner_id": 2,
          "start_time": "2026-07-22T14:00:00",
          "end_time": "2026-07-22T15:00:00",
          "student_a": {"course_id": 101, "availability": {...}},
          "student_b": {"course_id": 101, "availability": {...}},
          "topic": "Calc II",                       # optional, for Notion page title
          "student_a_name": "Alice",                 # optional, for Notion page body
          "student_b_name": "Bob",                   # optional, for Notion page body
          "notion_parent_page_id": "..."              # optional, required for Notion page creation
        }

    Response on success, everything booked (200):
        {"status": "confirmed", "calendar_status": "booked", "meet_link": "...",
         "notion_status": "created", "notes_page_url": "..."}

    Response on success, calendar/notion not booked (200) - the match is
    still saved, it's just flagged so the frontend can prompt the user to
    connect an account or retry later instead of losing the match entirely:
        {"status": "confirmed", "calendar_status": "pending calendar confirmation",
         "notion_status": "not connected"}

    Response on invalid match (400):
        {"error": "students are not compatible (different course or no availability overlap)"}
    """
    data = request.get_json() or {}

    user_id = data.get("user_id")
    partner_id = data.get("partner_id")
    student_a = data.get("student_a")
    student_b = data.get("student_b")
    start_time_raw = data.get("start_time")
    end_time_raw = data.get("end_time")

    if (user_id is None or partner_id is None or student_a is None or student_b is None
            or not start_time_raw or not end_time_raw):
        return jsonify({"error": "Missing required fields"}), 400

    if not isinstance(student_a, dict) or not isinstance(student_b, dict):
        return jsonify({"error": "student_a and student_b must be objects"}), 400

    required_student_keys = {"course_id", "availability"}
    if (not required_student_keys.issubset(student_a) or
            not required_student_keys.issubset(student_b)):
        return jsonify({
            "error": "student_a/student_b must include course_id and availability"
        }), 400

    if (not isinstance(student_a.get("availability"), dict) or
            not isinstance(student_b.get("availability"), dict)):
        return jsonify({"error": "availability must be an object keyed by weekday"}), 400

    # Step 1: don't book anything unless the pair is actually compatible.
    try:
        score = calculate_compatibility_score(student_a, student_b)
    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "Invalid student availability format"}), 400

    if score <= 0.0:
        return jsonify({
            "error": "students are not compatible (different course or no availability overlap)"
        }), 400

    try:
        start_time = datetime.fromisoformat(start_time_raw.replace("Z", "+00:00"))
        end_time = datetime.fromisoformat(end_time_raw.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return jsonify({"error": "Invalid start_time/end_time (expected ISO-8601)"}), 400

    if end_time <= start_time:
        return jsonify({"error": "end_time must be after start_time"}), 400

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
            attendee_emails=[],  # TODO: populate with real emails once a Student model exists
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
            student_a_name=data.get("student_a_name", "Student A"),
            student_b_name=data.get("student_b_name", "Student B"),
        )
        if page:
            notion_status = "created"
            notes_page_url = page.get("url")
        else:
            notion_status = "pending notion confirmation"
    elif notion_token and not notion_parent_page_id:
        notion_status = "pending notion confirmation"  # connected but no parent page given

    # Step 4: persist the match.
    #
    # TODO: no Student/Availability/Match schema exists yet (a teammate
    # owns the DB models). Once it's delivered, save a row here roughly
    # shaped like:
    #   match = Match(user_id=user_id, partner_id=partner_id,
    #                  start_time=start_time, end_time=end_time,
    #                  calendar_status=calendar_status, meet_link=meet_link,
    #                  notion_status=notion_status, notes_page_url=notes_page_url)
    #   db.session.add(match)
    #   db.session.commit()

    response = {
        "status": "confirmed",
        "calendar_status": calendar_status,
        "notion_status": notion_status,
    }
    if meet_link:
        response["meet_link"] = meet_link
    if notes_page_url:
        response["notes_page_url"] = notes_page_url
    return jsonify(response), 200
