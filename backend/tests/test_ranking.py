"""
tests/test_ranking.py
Priority 2 verification: rank_candidates / find_best_matches ordering,
plus the explainable-recommendation upgrade.
"""

from app.services.ranking import rank_candidates
from app.services.recommendation_engine import find_best_matches, explain_match
from tests.conftest import make_user


def test_ranking_returns_highest_score_first(app):
    target = make_user("Ava", "ava@example.edu", [(0, 14, 16)], "quiet", 3)
    close_match = make_user("Ben", "ben@example.edu", [(0, 14, 16)], "quiet", 3)
    far_match = make_user("Cleo", "cleo@example.edu", [(5, 6, 7)], "flashcards", 5)

    ranked = rank_candidates(target, [close_match, far_match])

    assert ranked[0]["user"].id == close_match.id
    assert ranked[0]["score"] >= ranked[1]["score"]


def test_ranking_excludes_current_user(app):
    target = make_user("Ava", "ava@example.edu", [(0, 14, 16)], "quiet", 3)
    other = make_user("Ben", "ben@example.edu", [(0, 14, 16)], "quiet", 3)

    ranked = rank_candidates(target, [target, other])
    ranked_ids = [entry["user"].id for entry in ranked]
    assert target.id not in ranked_ids


def test_find_best_matches_respects_top_n(app):
    target = make_user("Ava", "ava@example.edu", [(0, 14, 16)], "quiet", 3)
    others = [
        make_user(f"User{i}", f"user{i}@example.edu", [(0, 14, 16)], "quiet", 3)
        for i in range(5)
    ]
    all_users = [target] + others
    results = find_best_matches(target, all_users, top_n=2)
    assert len(results) == 2


def test_find_best_matches_includes_explainable_reasons(app):
    target = make_user("Ava", "ava@example.edu", [(0, 14, 16)], "quiet", 3)
    other = make_user("Ben", "ben@example.edu", [(0, 14, 16)], "quiet", 3)
    results = find_best_matches(target, [target, other], top_n=1)
    assert "reasons" in results[0]
    assert len(results[0]["reasons"]) > 0


def test_explain_match_includes_score_and_reasons(app):
    course_user_a = make_user("Ava", "ava@example.edu", [(0, 14, 16)], "quiet", 3)
    course_user_b = make_user("Ben", "ben@example.edu", [(0, 14, 16)], "quiet", 3)
    result = explain_match(course_user_a, course_user_b)
    assert "score" in result
    assert isinstance(result["reasons"], list)
