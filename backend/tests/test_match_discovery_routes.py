"""
tests/test_match_discovery_routes.py
GET /api/match/candidates and GET /api/match/history -- the routes
matches.html and dashboard.html actually fetch from.
"""

from app.services.persistence import get_or_create_course, save_match, email_domain
from tests.conftest import make_user


def test_email_domain_is_lowercased_part_after_at():
    assert email_domain("Alice@Example.EDU") == "example.edu"
    assert email_domain("bob@sub.school.edu") == "sub.school.edu"


def test_candidates_ranks_other_users_by_score(app):
    course = get_or_create_course("CS101", "Intro to CS")
    me = make_user("Alice", "alice@example.edu", [(0, 14, 16)], "quiet", 1, course)
    close_match = make_user("Bob", "bob@example.edu", [(0, 14, 16)], "quiet", 1, course)
    far_match = make_user("Cleo", "cleo@example.edu", [(1, 9, 11)], "discussion", 5)

    client = app.test_client()
    response = client.get(f"/api/match/candidates?user_id={me.id}")

    assert response.status_code == 200
    candidates = response.get_json()["candidates"]
    candidate_ids = [c["user"]["id"] for c in candidates]

    assert close_match.id in candidate_ids
    assert me.id not in candidate_ids  # never recommend yourself
    # find_best_matches() doesn't filter out zero scores -- it ranks
    # everyone -- so far_match still appears, just last.
    assert far_match.id in candidate_ids

    top = candidates[0]
    assert top["user"]["id"] == close_match.id
    assert top["score"] > 0
    assert "reasons" in top

    bottom = candidates[-1]
    assert bottom["user"]["id"] == far_match.id
    assert bottom["score"] == 0


def test_candidates_includes_same_domain_users(app):
    course = get_or_create_course("CS101", "Intro to CS")
    me = make_user("Alice", "alice@example.edu", [(0, 14, 16)], "quiet", 3, course)
    classmate = make_user("Bob", "bob@example.edu", [(0, 14, 16)], "quiet", 3, course)

    client = app.test_client()
    response = client.get(f"/api/match/candidates?user_id={me.id}")

    candidate_ids = [c["user"]["id"] for c in response.get_json()["candidates"]]
    assert classmate.id in candidate_ids


def test_candidates_excludes_different_domain_users_even_with_perfect_score(app):
    """A cross-school user with an otherwise-identical course/availability/
    style/pace (a perfect score if scored) must never appear -- the school
    filter is a hard filter, not a ranking signal."""
    course = get_or_create_course("CS101", "Intro to CS")
    me = make_user("Alice", "alice@example.edu", [(0, 14, 16)], "quiet", 3, course)
    other_school = make_user(
        "Zoe", "zoe@otherschool.edu", [(0, 14, 16)], "quiet", 3, course
    )

    client = app.test_client()
    response = client.get(f"/api/match/candidates?user_id={me.id}")

    candidate_ids = [c["user"]["id"] for c in response.get_json()["candidates"]]
    assert other_school.id not in candidate_ids


def test_candidates_missing_user_returns_404(app):
    client = app.test_client()
    response = client.get("/api/match/candidates?user_id=999999")
    assert response.status_code == 404


def test_history_returns_only_confirmed_matches_for_user(app):
    u1 = make_user("Alice", "alice@example.edu", [(0, 14, 16)], "quiet", 3)
    u2 = make_user("Bob", "bob@example.edu", [(0, 14, 16)], "quiet", 3)
    u3 = make_user("Cleo", "cleo@example.edu", [(0, 14, 16)], "quiet", 3)

    save_match(u1.id, u2.id, score=90.0, status="confirmed")
    save_match(u1.id, u3.id, score=40.0, status="pending")  # not confirmed -- excluded

    client = app.test_client()
    response = client.get(f"/api/match/history?user_id={u1.id}")

    assert response.status_code == 200
    matches = response.get_json()["matches"]
    assert len(matches) == 1
    assert matches[0]["partner_name"] == "Bob"
    assert matches[0]["partner_email"] == "bob@example.edu"
    assert matches[0]["score"] == 90.0


def test_history_missing_user_returns_404(app):
    client = app.test_client()
    response = client.get("/api/match/history?user_id=999999")
    assert response.status_code == 404
