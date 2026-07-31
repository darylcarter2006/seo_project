"""
app/routes/user_routes.py
---------------------------
Creates/updates a study-profile: a real User row plus its Availability,
Course enrollment, and Preference, from the shape the frontend's
profile.html form actually collects.

There's no login system yet, so "which user is this" is decided purely by
looking the submitted email up in the DB -- resubmitting the profile form
with the same email updates that user instead of creating a duplicate.
"""

from flask import Blueprint, request, jsonify

from app.database.db import db
from app.routes.auth_routes import get_valid_access_token
from app.services.scoring import DAY_NAMES
from app.services.persistence import (
    get_user,
    get_user_by_email,
    create_user,
    clear_availability,
    add_availability,
    get_or_create_course,
    set_preference,
)

user_bp = Blueprint("users", __name__)

DAY_NAME_TO_INDEX = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def _parse_hour(time_str):
    """'14:00' -> 14. Availability is integer-hour granularity by design
    (see app/models/availability.py) -- minutes are intentionally dropped."""
    return int(time_str.split(":")[0])


@user_bp.route("", methods=["POST"])
def create_or_update_profile():
    """
    Expected JSON body:
        {
          "name": "Alice",
          "email": "alice@example.edu",
          "course_code": "CS101",
          "availability": {"monday": [["14:00", "16:00"]], ...},
          "study_style": "quiet",   # optional, defaults to "discussion"
          "pace": 3                 # optional, defaults to 3
        }

    Response (200): {"user_id": 5}
    """
    data = request.get_json() or {}

    name = data.get("name")
    email = data.get("email")
    course_code = data.get("course_code")
    availability = data.get("availability")

    if not name or not email or not course_code:
        return jsonify({"error": "name, email, and course_code are required"}), 400

    if not isinstance(availability, dict):
        return jsonify({"error": "availability must be an object keyed by weekday"}), 400

    parsed_slots = []
    for day, blocks in availability.items():
        day_index = DAY_NAME_TO_INDEX.get(day.lower())
        if day_index is None:
            return jsonify({"error": f"unknown weekday: {day}"}), 400
        if not isinstance(blocks, list):
            return jsonify({"error": f"availability.{day} must be a list of [start, end] pairs"}), 400
        for block in blocks:
            try:
                start_str, end_str = block
                start_hour, end_hour = _parse_hour(start_str), _parse_hour(end_str)
            except (ValueError, TypeError):
                return jsonify({"error": f"invalid time block in availability.{day}"}), 400
            if not (0 <= start_hour < end_hour <= 24):
                return jsonify({"error": f"invalid time range in availability.{day}"}), 400
            parsed_slots.append((day_index, start_hour, end_hour))

    user = get_user_by_email(email)
    if user is None:
        user = create_user(name, email)
    elif user.name != name:
        user.name = name
        db.session.commit()

    clear_availability(user.id)
    for day_index, start_hour, end_hour in parsed_slots:
        add_availability(user.id, day_index, start_hour, end_hour)

    # The frontend only collects a single "current" course, so resubmitting
    # the profile form should replace the enrollment, not accumulate a new
    # one alongside old ones -- enroll_user_in_course() only appends, so we
    # reset the list directly here rather than growing it forever.
    course = get_or_create_course(course_code, course_code)
    if list(user.courses) != [course]:
        user.courses = [course]
        db.session.commit()

    set_preference(user.id, data.get("study_style") or "discussion", data.get("pace") or 3)

    return jsonify({"user_id": user.id}), 200


@user_bp.route("/<int:user_id>")
def get_profile(user_id):
    """
    GET /api/users/<user_id>

    Authoritative snapshot of this user's saved profile. Used by
    profile.html's explicit "Load my saved profile" button instead of
    trusting whatever's sitting in localStorage -- see README for why
    auto-prefilling from localStorage was a problem.
    Response: {"name": "...", "email": "...", "course_code": "...",
     "availability": {"monday": [["14:00", "16:00"]], ...},
     "study_style": "quiet", "pace": 3}
    404 if user_id doesn't exist.
    """
    user = get_user(user_id)
    if user is None:
        return jsonify({"error": "user_id must reference an existing user"}), 404

    availability = {}
    for slot in user.availability_slots:
        day = DAY_NAMES[slot.day_of_week]
        availability.setdefault(day, []).append(
            [f"{slot.start_hour:02d}:00", f"{slot.end_hour:02d}:00"]
        )

    return jsonify({
        "name": user.name,
        "email": user.email,
        "course_code": user.courses[0].code if user.courses else "",
        "availability": availability,
        "study_style": user.preference.study_style if user.preference else "discussion",
        "pace": user.preference.pace if user.preference else 3,
    }), 200


@user_bp.route("/<int:user_id>/connections")
def connection_status(user_id):
    """
    GET /api/users/<user_id>/connections

    Which OAuth providers this user currently has a valid connection for,
    reusing get_valid_access_token() (already handles the expired/refresh
    case) rather than just checking whether a token row exists.
    Response: {"google_calendar": true, "notion": false}
    """
    if get_user(user_id) is None:
        return jsonify({"error": "user_id must reference an existing user"}), 404

    return jsonify({
        "google_calendar": get_valid_access_token(user_id, provider="google_calendar") is not None,
        "notion": get_valid_access_token(user_id, provider="notion") is not None,
    }), 200
