"""
app/routes/match_routes.py
----------------------------
Where the matching engine (Person 2) and the "propose a match -> both
people have to agree before anything's booked" flow (you, Person B)
connect.

Compatibility scoring is powered by app/services/recommendation_engine.py
(database schema + weighted scoring algorithm), not raw request-body data
-- confirming a match requires both users to already exist in the DB with
real Availability/Course/Preference rows.

A match starts as a "pending" invite (POST /confirm). It only becomes a
real Calendar event + Notion page once the invited partner accepts it via
POST /<match_id>/respond -- see that route's docstring for why.
"""

from datetime import datetime

from flask import Blueprint, request, jsonify

from app.routes.auth_routes import get_valid_access_token
from app.services.google_calendar_service import GoogleCalendarService
from app.services.notion_service import NotionService
from app.services.recommendation_engine import calculate_score, find_best_matches
from app.services.persistence import (
    get_user,
    get_all_users,
    get_matches,
    get_match,
    save_match,
    update_match_status,
    save_match_proposal,
    get_match_proposal,
    email_domain,
)

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
    confirmation time. Only matches that actually went through full
    acceptance (see /respond) show up here, not just proposed ones.
    Response:
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


@match_bp.route("/pending")
def pending():
    """
    GET /api/match/pending?user_id=2

    Invites waiting on this user to respond to -- matches where user_id is
    the invited partner (user_b_id) and status is still "pending". A match
    this user proposed themselves (where they're user_a) never appears
    here, even while pending -- it's not waiting on them.
    Response:
        {"pending": [{"match_id": 5, "partner_name": "Alice" (the proposer),
         "score": 82.5, "created_at": "..."}, ...]}
    """
    user_id = request.args.get("user_id", type=int)
    if user_id is None:
        return jsonify({"error": "user_id query param is required"}), 400

    user = get_user(user_id)
    if user is None:
        return jsonify({"error": "user_id must reference an existing user"}), 404

    invites = [m for m in get_matches(user_id=user_id, status="pending") if m.user_b_id == user_id]
    results = [{
        "match_id": m.id,
        "partner_name": m.user_a.name,
        "score": m.score,
        "created_at": m.created_at.isoformat(),
    } for m in invites]
    return jsonify({"pending": results}), 200


def _book_session(match, proposal):
    """
    Books the Calendar event + Notion page for a match that was just
    accepted, using the proposer's (match.user_a) OAuth connections and
    inviting the accepting partner (match.user_b) as a real Calendar
    attendee. Graceful degradation, same as the old confirm_match: a
    missing connection or failed API call never blocks acceptance --
    calendar_status/notion_status just reflect what actually happened.

    Returns (calendar_status, meet_link, notion_status, notes_page_url).
    """
    initiator_id = match.user_a_id
    partner = match.user_b

    access_token = get_valid_access_token(initiator_id, provider="google_calendar")

    calendar_status = "pending calendar confirmation"
    meet_link = None

    if access_token:
        event = GoogleCalendarService.create_calendar_event(
            access_token,
            summary="Study Session",
            start_time=proposal.start_time,
            end_time=proposal.end_time,
            attendee_emails=[partner.email],
        )
        if event:
            calendar_status = "booked"
            meet_link = event.get("hangoutLink")
        # else: create_calendar_event already logged why it failed; we fall
        # through with calendar_status left as "pending calendar confirmation"
    # else: initiator hasn't connected Google yet - same graceful-degrade
    # path as an API failure, so acceptance still succeeds either way.

    notion_token = get_valid_access_token(initiator_id, provider="notion")

    notion_status = "not connected"
    notes_page_url = None

    if notion_token and proposal.notion_parent_page_id:
        page = NotionService.create_shared_page(
            notion_token,
            parent_page_id=proposal.notion_parent_page_id,
            topic=proposal.topic or "Study Session",
            student_a_name=match.user_a.name,
            student_b_name=partner.name,
        )
        if page:
            notion_status = "created"
            notes_page_url = page.get("url")
        else:
            notion_status = "pending notion confirmation"
    elif notion_token and not proposal.notion_parent_page_id:
        notion_status = "pending notion confirmation"  # connected but no parent page given

    return calendar_status, meet_link, notion_status, notes_page_url


@match_bp.route("/confirm", methods=["POST"])
def confirm_match():
    """
    Proposes a study-pair match between two existing users -- a pending
    invite, not an immediate booking. Nothing gets booked on Calendar/Notion
    at this step; that only happens if/when partner_id accepts via
    POST /api/match/<match_id>/respond.

    Expected JSON body:
        {
          "user_id": 1,
          "partner_id": 2,
          "start_time": "2026-07-22T14:00:00",
          "end_time": "2026-07-22T15:00:00",
          "topic": "Calc II",                       # optional, for Notion page title later
          "notion_parent_page_id": "..."              # optional, used later if accepted
        }

    Response on success (200):
        {"status": "pending", "match_id": 5, "score": 82.5}

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

    # Don't propose a match unless the pair is actually compatible.
    score = calculate_score(user, partner)
    if score <= 0:
        return jsonify({
            "error": "students are not compatible (no availability/course overlap)"
        }), 400

    match = save_match(user_id, partner_id, score, status="pending")
    save_match_proposal(
        match.id,
        start_time,
        end_time,
        topic=data.get("topic"),
        notion_parent_page_id=data.get("notion_parent_page_id"),
    )

    return jsonify({"status": "pending", "match_id": match.id, "score": score}), 200


@match_bp.route("/<int:match_id>/respond", methods=["POST"])
def respond_to_match(match_id):
    """
    POST /api/match/<match_id>/respond

    Only the invited partner (match.user_b_id, i.e. the partner_id from the
    original proposal) can respond to a pending match.

    Expected JSON body:
        {"response": "accept", "responding_user_id": 2}
        {"response": "decline", "responding_user_id": 2}

    Response on decline (200):
        {"status": "declined"}

    Response on accept (200) -- this is where booking actually happens now:
        {"status": "confirmed", "match_id": 5, "calendar_status": "booked",
         "meet_link": "...", "notion_status": "created", "notes_page_url": "..."}

    404 if match_id doesn't exist. 400 if it's not currently pending
    (already responded to). 403 if responding_user_id isn't the invited
    partner.
    """
    data = request.get_json() or {}
    response_value = data.get("response")
    responding_user_id = data.get("responding_user_id")

    match = get_match(match_id)
    if match is None:
        return jsonify({"error": "match_id not found"}), 404

    if match.status != "pending":
        return jsonify({"error": "this match has already been responded to"}), 400

    if responding_user_id != match.user_b_id:
        return jsonify({"error": "only the invited partner can respond to this match"}), 403

    if response_value == "decline":
        update_match_status(match_id, "declined")
        return jsonify({"status": "declined"}), 200

    if response_value != "accept":
        return jsonify({"error": "response must be 'accept' or 'decline'"}), 400

    proposal = get_match_proposal(match_id)
    calendar_status, meet_link, notion_status, notes_page_url = _book_session(match, proposal)

    # Confirmed regardless of booking outcome -- booking failure never
    # blocks acceptance, same graceful-degrade philosophy as before.
    update_match_status(match_id, "confirmed")

    response = {
        "status": "confirmed",
        "match_id": match.id,
        "calendar_status": calendar_status,
        "notion_status": notion_status,
    }
    if meet_link:
        response["meet_link"] = meet_link
    if notes_page_url:
        response["notes_page_url"] = notes_page_url
    return jsonify(response), 200
