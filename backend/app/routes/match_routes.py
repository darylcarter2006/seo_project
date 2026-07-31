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
    set_match_proposal_event_id,
    save_booking_result,
    set_match_proposal_dismissed,
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


def _dismissed_by(proposal, match, user_id):
    """Whether this user has dismissed this match from their own view --
    checks the side (a/b) matching user_id, not a single shared flag, so
    one participant dismissing never hides it for the other."""
    if not proposal:
        return False
    return proposal.dismissed_by_user_a if user_id == match.user_a_id else proposal.dismissed_by_user_b


@match_bp.route("/history")
def history():
    """
    GET /api/match/history?user_id=1

    This user's confirmed and cancelled matches -- who with, the score at
    confirmation time, and the current status, so a cancellation is
    visible to both participants instead of one side's match silently
    vanishing from the other's dashboard. Only matches that actually went
    through full acceptance (see /respond) show up here, not just
    proposed ones. Also includes the Calendar/Notion booking outcome from
    accept time (pulled back out of MatchProposal, where /respond
    persists it), so this detail survives a re-fetch instead of only
    existing in the one-time /respond response. A match either
    participant has dismissed (see POST /<match_id>/dismiss) is excluded
    from their own results only.
    Response:
        {"matches": [{"match_id": 5, "partner_name": "Bob",
         "partner_email": "bob@example.edu", "score": 82.5,
         "status": "confirmed", "start_time": "...", "end_time": "...",
         "calendar_status": "booked", "meet_link": "...",
         "notion_status": "created", "notes_page_url": "..."}, ...]}
    """
    user_id = request.args.get("user_id", type=int)
    if user_id is None:
        return jsonify({"error": "user_id query param is required"}), 400

    user = get_user(user_id)
    if user is None:
        return jsonify({"error": "user_id must reference an existing user"}), 404

    relevant = [m for m in get_matches(user_id=user_id) if m.status in ("confirmed", "cancelled")]
    results = []
    for match in relevant:
        partner = match.user_b if match.user_a_id == user_id else match.user_a
        proposal = get_match_proposal(match.id)
        if _dismissed_by(proposal, match, user_id):
            continue
        results.append({
            "match_id": match.id,
            "partner_name": partner.name,
            "partner_email": partner.email,
            "score": match.score,
            "status": match.status,
            "created_at": match.created_at.isoformat(),
            "start_time": proposal.start_time.isoformat() if proposal else None,
            "end_time": proposal.end_time.isoformat() if proposal else None,
            "calendar_status": proposal.calendar_status if proposal else None,
            "meet_link": proposal.meet_link if proposal else None,
            "notion_status": proposal.notion_status if proposal else None,
            "notes_page_url": proposal.notes_page_url if proposal else None,
        })
    return jsonify({"matches": results}), 200


@match_bp.route("/pending")
def pending():
    """
    GET /api/match/pending?user_id=2

    Invites waiting on this user to respond to (status "pending"), plus
    ones they've already declined (status "declined") so declining isn't
    a silent disappearance -- matches where user_id is the invited partner
    (user_b_id). A match this user proposed themselves (where they're
    user_a) never appears here, even while pending -- it's not waiting on
    them. A dismissed invite (see POST /<match_id>/dismiss) is excluded.
    Response:
        {"pending": [{"match_id": 5, "partner_name": "Alice" (the proposer),
         "score": 82.5, "status": "pending", "created_at": "..."}, ...]}
    """
    user_id = request.args.get("user_id", type=int)
    if user_id is None:
        return jsonify({"error": "user_id query param is required"}), 400

    user = get_user(user_id)
    if user is None:
        return jsonify({"error": "user_id must reference an existing user"}), 404

    invites = [
        m for m in get_matches(user_id=user_id)
        if m.user_b_id == user_id and m.status in ("pending", "declined")
    ]
    results = []
    for m in invites:
        proposal = get_match_proposal(m.id)
        if _dismissed_by(proposal, m, user_id):
            continue
        results.append({
            "match_id": m.id,
            "partner_name": m.user_a.name,
            "score": m.score,
            "status": m.status,
            "created_at": m.created_at.isoformat(),
        })
    return jsonify({"pending": results}), 200


@match_bp.route("/sent")
def sent():
    """
    GET /api/match/sent?user_id=1

    Invites this user proposed that are still waiting on the other person
    to respond (status "pending"), plus ones that got declined (status
    "declined") so a decline isn't a silent disappearance -- matches where
    user_id is the proposer (user_a_id). The mirror image of /pending. A
    dismissed invite (see POST /<match_id>/dismiss) is excluded.
    Response:
        {"sent": [{"match_id": 5, "partner_name": "Bob" (the invited person),
         "score": 82.5, "status": "pending", "created_at": "..."}, ...]}
    """
    user_id = request.args.get("user_id", type=int)
    if user_id is None:
        return jsonify({"error": "user_id query param is required"}), 400

    user = get_user(user_id)
    if user is None:
        return jsonify({"error": "user_id must reference an existing user"}), 404

    proposed = [
        m for m in get_matches(user_id=user_id)
        if m.user_a_id == user_id and m.status in ("pending", "declined")
    ]
    results = []
    for m in proposed:
        proposal = get_match_proposal(m.id)
        if _dismissed_by(proposal, m, user_id):
            continue
        results.append({
            "match_id": m.id,
            "partner_name": m.user_b.name,
            "score": m.score,
            "status": m.status,
            "created_at": m.created_at.isoformat(),
        })
    return jsonify({"sent": results}), 200


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
            if event.get("id"):
                set_match_proposal_event_id(match.id, event.get("id"))
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
    save_booking_result(match_id, calendar_status, meet_link, notion_status, notes_page_url)

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


@match_bp.route("/<int:match_id>/cancel", methods=["POST"])
def cancel_match(match_id):
    """
    POST /api/match/<match_id>/cancel

    Either participant (user_a or user_b) can cancel a confirmed match.
    Body: {"user_id": 2}

    Best-effort deletes the actual Google Calendar event too, using the
    event id captured at accept time (MatchProposal.google_calendar_event_id)
    -- but a missing event id, missing connection, or failed delete never
    blocks cancellation; it's just noted in the response.

    Response (200):
        {"status": "cancelled", "match_id": 5, "calendar_event_deleted": true}

    404 if match_id doesn't exist. 403 if user_id isn't a participant.
    400 if the match isn't currently confirmed.
    """
    data = request.get_json() or {}
    user_id = data.get("user_id")

    match = get_match(match_id)
    if match is None:
        return jsonify({"error": "match_id not found"}), 404

    if user_id not in (match.user_a_id, match.user_b_id):
        return jsonify({"error": "only a participant in this match can cancel it"}), 403

    if match.status != "confirmed":
        return jsonify({"error": "only a confirmed match can be cancelled"}), 400

    # Best-effort: the initiator (user_a) is whose calendar the event lives
    # on, same as _book_session() -- a missing token/event id/API failure
    # never blocks cancelling the match in our own DB.
    calendar_event_deleted = False
    proposal = get_match_proposal(match_id)
    if proposal and proposal.google_calendar_event_id:
        access_token = get_valid_access_token(match.user_a_id, provider="google_calendar")
        if access_token:
            deleted = GoogleCalendarService.delete_calendar_event(
                access_token, proposal.google_calendar_event_id
            )
            calendar_event_deleted = bool(deleted)

    update_match_status(match_id, "cancelled")

    return jsonify({
        "status": "cancelled",
        "match_id": match.id,
        "calendar_event_deleted": calendar_event_deleted,
    }), 200


@match_bp.route("/<int:match_id>/dismiss", methods=["POST"])
def dismiss_match(match_id):
    """
    POST /api/match/<match_id>/dismiss

    Clears this match from user_id's own dashboard view (pending/sent/
    history) -- a per-side flag on MatchProposal, so the other
    participant's view is completely unaffected. Works regardless of the
    match's current status (pending, confirmed, declined, cancelled);
    dismissing is just "stop showing me this," not a state transition.
    Body: {"user_id": 2}

    Response (200): {"status": "dismissed", "match_id": 5}

    404 if match_id doesn't exist. 403 if user_id isn't a participant.
    """
    data = request.get_json() or {}
    user_id = data.get("user_id")

    match = get_match(match_id)
    if match is None:
        return jsonify({"error": "match_id not found"}), 404

    if user_id not in (match.user_a_id, match.user_b_id):
        return jsonify({"error": "only a participant in this match can dismiss it"}), 403

    side = "a" if user_id == match.user_a_id else "b"
    set_match_proposal_dismissed(match_id, side)

    return jsonify({"status": "dismissed", "match_id": match.id}), 200
