"""
tests/test_match_dismiss.py
Exercises POST /api/match/<match_id>/dismiss -- a per-side flag on
MatchProposal that clears a match from just the dismissing user's own
dashboard view (pending/sent/history), regardless of the match's status,
without affecting the other participant's view at all.
"""

from app.services.persistence import (
    get_or_create_course,
    save_match,
    save_match_proposal,
    get_match_proposal,
)
from tests.conftest import make_user


def _compatible_pair():
    course = get_or_create_course("CS101", "Intro to CS")
    user = make_user("Alice", "alice@example.edu", [(0, 14, 16)], "quiet", 3, course)
    partner = make_user("Bob", "bob@example.edu", [(0, 14, 16)], "quiet", 3, course)
    return user, partner


def _propose(user, partner):
    from datetime import datetime
    match = save_match(user.id, partner.id, 90.0, status="pending")
    save_match_proposal(
        match.id,
        start_time=datetime(2026, 7, 22, 14, 0, 0),
        end_time=datetime(2026, 7, 22, 15, 0, 0),
    )
    return match


def test_dismiss_works_regardless_of_match_status(app):
    user, partner = _compatible_pair()
    match = _propose(user, partner)  # still "pending"

    client = app.test_client()
    response = client.post(f"/api/match/{match.id}/dismiss", json={"user_id": partner.id})

    assert response.status_code == 200
    assert response.get_json() == {"status": "dismissed", "match_id": match.id}

    proposal = get_match_proposal(match.id)
    assert proposal.dismissed_by_user_b is True
    assert proposal.dismissed_by_user_a is False


def test_dismiss_only_affects_dismissing_users_own_view(app):
    user, partner = _compatible_pair()
    match = _propose(user, partner)

    client = app.test_client()
    # partner is the invited side -- dismiss it from their /pending view
    client.post(f"/api/match/{match.id}/dismiss", json={"user_id": partner.id})

    assert client.get(f"/api/match/pending?user_id={partner.id}").get_json()["pending"] == []
    # proposer's /sent view is untouched
    sent = client.get(f"/api/match/sent?user_id={user.id}").get_json()["sent"]
    assert len(sent) == 1
    assert sent[0]["match_id"] == match.id


def test_dismiss_by_non_participant_returns_403(app):
    user, partner = _compatible_pair()
    match = _propose(user, partner)
    other = make_user("Cleo", "cleo@example.edu", [(0, 14, 16)], "quiet", 3)

    client = app.test_client()
    response = client.post(f"/api/match/{match.id}/dismiss", json={"user_id": other.id})

    assert response.status_code == 403
    proposal = get_match_proposal(match.id)
    assert proposal.dismissed_by_user_a is False
    assert proposal.dismissed_by_user_b is False


def test_dismiss_unknown_match_returns_404(app):
    client = app.test_client()
    response = client.post("/api/match/999999/dismiss", json={"user_id": 1})
    assert response.status_code == 404
